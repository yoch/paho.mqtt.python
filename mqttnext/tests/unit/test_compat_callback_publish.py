"""publish() from a callback must not deadlock (fire-and-forget path)."""

from __future__ import annotations

import asyncio

from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.codec.primitives import pack_u16
from mqttnext.compat.paho import CallbackAPIVersion, Client
from mqttnext.enums import PacketType, QoS
from mqttnext.packets import PubAckPacket, PublishPacket, encode_frame


class FakeBrokerTransport:
    def __init__(self) -> None:
        self._rx: asyncio.Queue[bytes] = asyncio.Queue()
        self._decoder = IncrementalDecoder()
        self._closing = False
        self.published: list[PublishPacket] = []

    async def write(self, data: bytes) -> None:
        self._decoder.feed(data)
        for raw in self._decoder.drain_packets():
            if raw.packet_type is PacketType.CONNECT:
                self._rx.put_nowait(encode_frame(PacketType.CONNACK, 0, b"\x00\x00"))
            elif raw.packet_type is PacketType.PUBLISH:
                pub = PublishPacket.decode(raw.flags, raw.remaining)
                self.published.append(pub)
                if pub.qos == QoS.AT_LEAST_ONCE and pub.mid is not None:
                    self._rx.put_nowait(PubAckPacket(mid=pub.mid).encode())

    async def read(self, n: int = 65536) -> bytes:
        return await self._rx.get()

    async def close(self) -> None:
        self._closing = True
        self._rx.put_nowait(b"")

    def is_closing(self) -> bool:
        return self._closing

    def push_publish(self, topic: str, payload: bytes) -> None:
        pkt = PublishPacket(
            topic=topic, payload=payload, qos=QoS.AT_MOST_ONCE, retain=False, dup=False
        )
        self._rx.put_nowait(pkt.encode())


def test_publish_from_on_message_no_deadlock() -> None:
    fake = FakeBrokerTransport()
    client = Client(CallbackAPIVersion.VERSION2, client_id="cb-pub")

    async def factory(host: str, port: int, *, ssl: object = None) -> FakeBrokerTransport:
        return fake

    client._async._transport_factory = factory
    import threading

    done = threading.Event()
    errors: list[BaseException] = []

    def on_message(c, userdata, message):
        try:
            # Publish from inside the callback — must not raise/deadlock.
            info = c.publish("out/echo", b"reply:" + message.payload, qos=1)
            assert info.mid is not None
            done.set()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            done.set()

    client.on_message = on_message
    client.loop_start()
    try:
        assert client.connect("fake", 1883) == 0
        fake.push_publish("in/t", b"hello")
        assert done.wait(timeout=3.0), "callback publish deadlocked"
        assert not errors
        # Allow the fire-and-forget flush to reach the broker.
        import time

        deadline = time.monotonic() + 2.0
        while not any(p.topic == "out/echo" for p in fake.published) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert any(p.topic == "out/echo" for p in fake.published)
    finally:
        client.disconnect()
        client.loop_stop()
