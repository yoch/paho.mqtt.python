from __future__ import annotations

from pathlib import Path


TARGET = Path("mqttnext/src/mqttnext/compat/paho.py")
TEST = Path("mqttnext/tests/unit/test_compat_confinement.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


text = TARGET.read_text()
text = replace_once(
    text,
    """    def user_data_set(self, userdata: Any) -> None:
        self._userdata = userdata

    def username_pw_set(self, username: str, password: bytes | str | None = None) -> None:
        pwd = password.encode("utf-8") if isinstance(password, str) else password
        self._async._engine.config.username = username
        self._async._engine.config.password = pwd
""",
    """    def user_data_set(self, userdata: Any) -> None:
        self._run_loop_mutation(lambda: setattr(self, "_userdata", userdata))

    def username_pw_set(self, username: str, password: bytes | str | None = None) -> None:
        pwd = password.encode("utf-8") if isinstance(password, str) else password

        def _set_credentials() -> None:
            self._async._engine.config.username = username
            self._async._engine.config.password = pwd

        self._run_loop_mutation(_set_credentials)
""",
    "credential confinement",
)
text = replace_once(
    text,
    """        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        self._async._engine.config.will = Message(
            topic=topic,
            payload=data,
            qos=QoS(qos),
            retain=retain,
        )

    def message_callback_add(self, sub: str, callback: Callable[..., Any]) -> None:
        self._topic_callbacks[sub] = callback

    def message_callback_remove(self, sub: str) -> None:
        try:
            del self._topic_callbacks[sub]
        except KeyError:
            pass
""",
    """        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        message = Message(
            topic=topic,
            payload=data,
            qos=QoS(qos),
            retain=retain,
        )
        self._run_loop_mutation(
            lambda: setattr(self._async._engine.config, "will", message)
        )

    def message_callback_add(self, sub: str, callback: Callable[..., Any]) -> None:
        self._run_loop_mutation(lambda: self._topic_callbacks.__setitem__(sub, callback))

    def message_callback_remove(self, sub: str) -> None:
        def _remove() -> None:
            try:
                del self._topic_callbacks[sub]
            except KeyError:
                pass

        self._run_loop_mutation(_remove)
""",
    "will and matcher confinement",
)
text = replace_once(
    text,
    """    @property
    def is_connected(self) -> bool:
        return self._async.is_connected
""",
    """    @property
    def is_connected(self) -> bool:
        return bool(self._run_loop_mutation(lambda: self._async.is_connected))
""",
    "connected state confinement",
)
text = replace_once(
    text,
    """    def _queue_loop_command(self, command: Callable[[], Any]) -> Any:
""",
    """    def _run_loop_mutation(self, mutation: Callable[[], Any]) -> Any:
        """Run a short synchronous mutation on the network loop when active."""
        loop = self._loop
        thread = self._thread
        if loop is None or not loop.is_running() or thread is None:
            return mutation()
        if threading.current_thread() is thread:
            return mutation()

        handoff: dict[str, Any] = {}
        done = threading.Event()

        def _run() -> None:
            try:
                handoff["result"] = mutation()
            except BaseException as exc:
                handoff["error"] = exc
            finally:
                done.set()

        loop.call_soon_threadsafe(_run)
        if not done.wait(timeout=5.0):
            raise RuntimeError("mutation handoff to event loop timed out")
        error = handoff.get("error")
        if error is not None:
            raise error
        return handoff.get("result")

    def _queue_loop_command(self, command: Callable[[], Any]) -> Any:
""",
    "loop mutation helper",
)
text = replace_once(
    text,
    """    def connect(self, host: str, port: int = 1883, keepalive: int = 60) -> int:
        self._async._engine.config.keepalive = keepalive
        self._submit(self._async.connect(host, port))
        return 0

    def reconnect(self) -> int:
        host = self._async._host
        port = self._async._port
        if not host:
            raise RuntimeError("reconnect() called before connect()")
        return self.connect(host, port, keepalive=self._async._engine.config.keepalive)
""",
    """    def connect(self, host: str, port: int = 1883, keepalive: int = 60) -> int:
        self._run_loop_mutation(
            lambda: setattr(self._async._engine.config, "keepalive", keepalive)
        )
        self._submit(self._async.connect(host, port))
        return 0

    def reconnect(self) -> int:
        host, port, keepalive = self._run_loop_mutation(
            lambda: (
                self._async._host,
                self._async._port,
                self._async._engine.config.keepalive,
            )
        )
        if not host:
            raise RuntimeError("reconnect() called before connect()")
        return self.connect(host, port, keepalive=keepalive)
""",
    "connect configuration confinement",
)
TARGET.write_text(text)

TEST.write_text(
    '''"""Thread confinement for the synchronous compatibility façade."""

from __future__ import annotations

import threading

from mqttnext.compat.paho import CallbackAPIVersion, Client
from mqttnext.enums import QoS


def test_mutation_handoff_runs_on_network_thread() -> None:
    client = Client(CallbackAPIVersion.VERSION2)
    caller = threading.get_ident()
    client.loop_start()
    try:
        loop_thread = client._run_loop_mutation(threading.get_ident)
        assert client._thread is not None
        assert loop_thread == client._thread.ident
        assert loop_thread != caller
    finally:
        client.loop_stop()


def test_configuration_setters_are_safe_after_loop_start() -> None:
    client = Client(CallbackAPIVersion.VERSION2)
    callback = lambda *args: None
    client.loop_start()
    try:
        client.user_data_set({"key": "value"})
        client.username_pw_set("user", "secret")
        client.will_set("will/topic", "payload", qos=1, retain=True)
        client.message_callback_add("sensor/+", callback)

        values = client._run_loop_mutation(
            lambda: (
                client._userdata,
                client._async._engine.config.username,
                client._async._engine.config.password,
                client._async._engine.config.will,
                list(client._topic_callbacks.iter_match("sensor/1")),
            )
        )
        userdata, username, password, will, callbacks = values
        assert userdata == {"key": "value"}
        assert username == "user"
        assert password == b"secret"
        assert will is not None
        assert will.topic == "will/topic"
        assert will.payload == b"payload"
        assert will.qos is QoS.AT_LEAST_ONCE
        assert will.retain is True
        assert callbacks == [callback]

        client.message_callback_remove("sensor/+")
        assert client._run_loop_mutation(
            lambda: list(client._topic_callbacks.iter_match("sensor/1"))
        ) == []
    finally:
        client.loop_stop()


def test_mutation_from_network_thread_does_not_deadlock() -> None:
    client = Client(CallbackAPIVersion.VERSION2)
    client.loop_start()
    try:
        done = threading.Event()
        errors: list[BaseException] = []

        def run_on_loop() -> None:
            try:
                client.username_pw_set("callback-user", b"pw")
                client.message_callback_add("inside/#", lambda *args: None)
            except BaseException as exc:
                errors.append(exc)
            finally:
                done.set()

        assert client._loop is not None
        client._loop.call_soon_threadsafe(run_on_loop)
        assert done.wait(timeout=2.0)
        assert errors == []
    finally:
        client.loop_stop()
'''
)
