import threading
import time

import paho.mqtt.client as client
from paho.mqtt.enums import CallbackAPIVersion, _ConnectionState


class CountingSockpair:
    def __init__(self):
        self.sends = 0
        self._pending = 0

    def send(self, data):
        self.sends += 1
        self._pending += len(data)
        return len(data)

    def recv(self, size):
        if self._pending <= 0:
            raise BlockingIOError()
        n = min(size, self._pending)
        self._pending -= n
        return b"\x00" * n

    def close(self):
        return None

    def fileno(self):
        return 1

    def setblocking(self, flag):
        return None


class PartialSendSocket:
    """Accepts at most `chunk` bytes per send to exercise partial writes."""

    def __init__(self, chunk=4):
        self.chunk = chunk
        self.bytes_sent = 0
        self.calls = 0

    def recv(self, size):
        return b""

    def send(self, data):
        self.calls += 1
        n = min(self.chunk, len(data))
        self.bytes_sent += n
        return n

    def close(self):
        return None

    def fileno(self):
        return 1

    def setblocking(self, flag):
        return None


class FakeSendSocket:
    def __init__(self):
        self.bytes_sent = 0
        self.calls = 0

    def recv(self, size):
        return b""

    def send(self, data):
        self.calls += 1
        self.bytes_sent += len(data)
        return len(data)

    def close(self):
        return None

    def fileno(self):
        return 1

    def setblocking(self, flag):
        return None


def test_message_info_condition_is_lazy():
    info = client.MQTTMessageInfo(1)

    assert info._condition is None
    assert info.is_published() is False
    assert info._condition is None

    info._set_as_published()
    assert info._condition is None
    assert info.is_published() is True

    info.wait_for_publish(timeout=0.01)
    assert info._condition is None


def test_wait_for_publish_creates_condition_and_wakes():
    info = client.MQTTMessageInfo(7)
    started = threading.Event()
    done = threading.Event()

    def waiter():
        started.set()
        info.wait_for_publish(timeout=1.0)
        done.set()

    thread = threading.Thread(target=waiter)
    thread.start()
    assert started.wait(1.0)
    for _ in range(50):
        if info._condition is not None:
            break
        time.sleep(0.01)

    assert info._condition is not None
    info._set_as_published()
    assert done.wait(1.0)
    thread.join(1.0)


def test_wait_for_publish_does_not_miss_concurrent_set_as_published():
    """Race: waiter and publisher must not lose the published notification."""
    failures = []

    for _ in range(200):
        info = client.MQTTMessageInfo(1)
        barrier = threading.Barrier(2)
        done = threading.Event()

        def waiter():
            barrier.wait()
            info.wait_for_publish(timeout=1.0)
            if not info.is_published():
                failures.append("waiter returned unpublished")
            done.set()

        def publisher():
            barrier.wait()
            info._set_as_published()

        threads = [
            threading.Thread(target=waiter),
            threading.Thread(target=publisher),
        ]
        for thread in threads:
            thread.start()
        assert done.wait(2.0), "wait_for_publish timed out under race"
        for thread in threads:
            thread.join(1.0)

    assert failures == []


def test_packet_queue_coalesces_sockpair_wakeups():
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    sockpair = CountingSockpair()
    mqttc._sockpairW = sockpair
    mqttc._sockpairR = sockpair
    mqttc._thread = threading.Thread(target=lambda: None)
    mqttc._thread_terminate = True

    for mid in range(100):
        rc = mqttc._packet_queue(client.PUBLISH, b"x", mid, 0)
        assert rc == client.MQTT_ERR_SUCCESS

    assert sockpair.sends == 1
    assert mqttc._sockpair_wakeup_pending is True

    with mqttc._sockpair_wakeup_mutex:
        sockpair.recv(10000)
        mqttc._sockpair_wakeup_pending = False

    rc = mqttc._packet_queue(client.PUBLISH, b"y", 101, 0)
    assert rc == client.MQTT_ERR_SUCCESS
    assert sockpair.sends == 2


def test_partial_socket_writes_preserve_packet_and_publish_state():
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    mqttc._sock = PartialSendSocket(chunk=3)
    mqttc._state = _ConnectionState.MQTT_CS_CONNECTED
    # Force queue path so publish() does not drain immediately.
    mqttc._thread = threading.Thread(target=lambda: None)

    info = mqttc.publish("a/b", b"0123456789", qos=0)
    assert info.rc == client.MQTT_ERR_SUCCESS
    assert info.is_published() is False
    assert mqttc.want_write() is True

    # Drain across many partial writes.
    for _ in range(100):
        rc = mqttc.loop_write()
        assert rc in (client.MQTT_ERR_SUCCESS, client.MQTT_ERR_AGAIN)
        if info.is_published():
            break

    assert info.is_published() is True
    assert mqttc.want_write() is False
    assert mqttc._sock.bytes_sent > 0


def test_qos0_on_publish_ordering():
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    mqttc._sock = FakeSendSocket()
    mqttc._state = _ConnectionState.MQTT_CS_CONNECTED
    seen = []

    def on_publish(mqttc, userdata, mid, reason_code, properties):
        seen.append(mid)

    mqttc.on_publish = on_publish

    infos = [mqttc.publish("t/{}".format(i), b"x", qos=0) for i in range(5)]
    assert [info.mid for info in infos] == seen
    assert all(info.is_published() for info in infos)


def test_external_loop_register_write_on_packet_queue():
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    registered = []

    def on_register(mqttc, userdata, sock):
        registered.append(sock)

    mqttc.on_socket_register_write = on_register
    # External-loop mode: no network thread, register callback set, so
    # _packet_queue must not call loop_write() immediately.
    mqttc._thread = None
    mqttc._sock = FakeSendSocket()
    mqttc._registered_write = False

    rc = mqttc._packet_queue(client.PUBLISH, b"payload", 1, 0)
    assert rc == client.MQTT_ERR_SUCCESS
    assert registered == [mqttc._sock]
    assert mqttc.want_write() is True
    assert len(mqttc._out_packet) == 1


def test_loop_start_clears_stale_sockpair_wakeup_pending(monkeypatch):
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    mqttc._sockpair_wakeup_pending = True
    sock_r = CountingSockpair()
    sock_w = CountingSockpair()

    monkeypatch.setattr(client, "_socketpair_compat", lambda: (sock_r, sock_w))

    def fake_thread_main():
        return None

    monkeypatch.setattr(mqttc, "_thread_main", fake_thread_main)

    assert mqttc.loop_start() == client.MQTT_ERR_SUCCESS
    assert mqttc._sockpair_wakeup_pending is False
    assert mqttc._sockpairR is sock_r
    assert mqttc._sockpairW is sock_w
    mqttc.loop_stop()


def test_loop_start_does_not_lose_wakeup_to_concurrent_packet_queue(monkeypatch):
    """Publish during sockpair swap must not leave pending=True on an empty pair."""
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    old_r = CountingSockpair()
    old_w = CountingSockpair()
    new_r = CountingSockpair()
    new_w = CountingSockpair()
    mqttc._sockpairR = old_r
    mqttc._sockpairW = old_w
    # Avoid immediate loop_write() while _thread is still None during loop_start.
    mqttc.on_socket_register_write = lambda *args: None

    release = threading.Event()

    def slow_socketpair():
        release.wait(1.0)
        return new_r, new_w

    monkeypatch.setattr(client, "_socketpair_compat", slow_socketpair)
    monkeypatch.setattr(mqttc, "_thread_main", lambda: None)

    starter = threading.Thread(target=mqttc.loop_start)
    starter.start()
    time.sleep(0.01)
    for mid in range(20):
        mqttc._packet_queue(client.PUBLISH, b"x", mid, 0)
    release.set()
    starter.join(2.0)

    assert mqttc._sockpairR is new_r
    assert mqttc._sockpairW is new_w
    assert len(mqttc._out_packet) == 20
    assert new_w.sends == 1
    assert mqttc._sockpair_wakeup_pending is True
    mqttc.loop_stop()
