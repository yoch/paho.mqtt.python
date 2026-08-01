"""Minimal Paho-compatible sync façade over AsyncClient (phase 3).

Only CallbackAPIVersion.VERSION2 is supported. A dedicated thread runs an
asyncio loop that owns one AsyncClient.
"""

from __future__ import annotations

import asyncio
import enum
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mqttnext.api.async_client import AsyncClient
from mqttnext.api.models import PublishReceipt
from mqttnext.dispatch.matcher import TopicMatcher
from mqttnext.enums import MQTTProtocolVersion, QoS
from mqttnext.packets import ConnAckPacket
from mqttnext.types import Message


class CallbackAPIVersion(enum.Enum):
    VERSION2 = 2


@dataclass
class MQTTMessageInfo:
    """Paho-like publish handle."""

    mid: int | None
    _receipt: PublishReceipt | None = field(default=None, repr=False)
    _loop: asyncio.AbstractEventLoop | None = field(default=None, repr=False)
    rc: int = 0

    def wait_for_publish(self, timeout: float | None = None) -> bool:
        if self._receipt is None or self._receipt.is_done():
            return True
        if self._loop is None:
            return False
        fut = asyncio.run_coroutine_threadsafe(self._receipt.wait(), self._loop)
        try:
            fut.result(timeout)
            return True
        except Exception:
            return False

    def is_published(self) -> bool:
        return self._receipt is None or self._receipt.is_done()


class MQTTMessage:
    """Paho-like inbound message."""

    __slots__ = ("topic", "payload", "qos", "retain", "mid")

    def __init__(self, msg: Message) -> None:
        self.topic = msg.topic.encode("utf-8")
        self.payload = msg.payload
        self.qos = int(msg.qos)
        self.retain = msg.retain
        self.mid = msg.mid or 0


class Client:
    """Sync Paho-shaped wrapper around ``AsyncClient`` (VERSION2 only)."""

    def __init__(
        self,
        callback_api_version: CallbackAPIVersion = CallbackAPIVersion.VERSION2,
        client_id: str = "",
        *,
        userdata: Any = None,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
        clean_session: bool | None = None,
        clean_start: bool = True,
    ) -> None:
        if callback_api_version is not CallbackAPIVersion.VERSION2:
            raise ValueError("mqttnext.compat.paho only supports CallbackAPIVersion.VERSION2")
        if clean_session is not None:
            clean_start = bool(clean_session)
        self._userdata = userdata
        self._async = AsyncClient(
            client_id=client_id,
            protocol=protocol,
            clean_start=clean_start,
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._topic_callbacks = TopicMatcher()

        self.on_connect: Callable[..., Any] | None = None
        self.on_disconnect: Callable[..., Any] | None = None
        self.on_message: Callable[..., Any] | None = None
        self.on_publish: Callable[..., Any] | None = None

        self._async.on_connect = self._dispatch_connect
        self._async.on_disconnect = self._dispatch_disconnect
        self._async.on_message = self._dispatch_message

    def user_data_set(self, userdata: Any) -> None:
        self._userdata = userdata

    def username_pw_set(self, username: str, password: bytes | str | None = None) -> None:
        pwd = password.encode("utf-8") if isinstance(password, str) else password
        self._async._engine.config.username = username
        self._async._engine.config.password = pwd

    def will_set(
        self,
        topic: str,
        payload: bytes | str = b"",
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
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

    @property
    def is_connected(self) -> bool:
        return self._async.is_connected

    def loop_start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._started.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="mqttnext-paho-loop", daemon=True
        )
        self._thread.start()
        if not self._started.wait(timeout=5.0):
            raise RuntimeError("Failed to start background loop")

    def loop_stop(self) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._loop = None

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._started.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def _submit(self, coro: Any, timeout: float | None = 30.0) -> Any:
        if self._loop is None:
            self.loop_start()
        assert self._loop is not None
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout)

    def connect(self, host: str, port: int = 1883, keepalive: int = 60) -> int:
        self._async._engine.config.keepalive = keepalive
        self._submit(self._async.connect(host, port))
        return 0

    def reconnect(self) -> int:
        host = self._async._host
        port = self._async._port
        if not host:
            raise RuntimeError("reconnect() called before connect()")
        return self.connect(host, port, keepalive=self._async._engine.config.keepalive)

    def disconnect(self) -> int:
        try:
            self._submit(self._async.disconnect(), timeout=10.0)
        except Exception:
            return 1
        return 0

    def publish(
        self,
        topic: str,
        payload: bytes | str = b"",
        qos: int = 0,
        retain: bool = False,
    ) -> MQTTMessageInfo:
        receipt: PublishReceipt = self._submit(
            self._async.publish(topic, payload, qos=qos, retain=retain)
        )
        info = MQTTMessageInfo(mid=receipt.mid, _receipt=receipt, _loop=self._loop)
        if self.on_publish is not None and receipt.qos == QoS.AT_MOST_ONCE:
            self.on_publish(self, self._userdata, receipt.mid, 0, None)
        elif receipt.qos != QoS.AT_MOST_ONCE and self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._watch_publish(receipt), self._loop)
        return info

    async def _watch_publish(self, receipt: PublishReceipt) -> None:
        try:
            await receipt.wait()
            if self.on_publish is not None:
                self.on_publish(self, self._userdata, receipt.mid, 0, None)
        except Exception:
            if self.on_publish is not None:
                self.on_publish(self, self._userdata, receipt.mid, 1, None)

    def subscribe(self, topic: str, qos: int = 0) -> tuple[int, int]:
        result = self._submit(self._async.subscribe(topic, qos=qos))
        return (0, result.mid)

    def unsubscribe(self, topic: str) -> tuple[int, int]:
        result = self._submit(self._async.unsubscribe(topic))
        return (0, result.mid)

    def _dispatch_connect(self, connack: ConnAckPacket) -> None:
        cb = self.on_connect
        if cb is None:
            return
        flags = {"session present": bool(connack.session_present)}
        cb(self, self._userdata, flags, connack.reason_code, connack.properties)

    def _dispatch_disconnect(self, exc: BaseException | None) -> None:
        cb = self.on_disconnect
        if cb is None:
            return
        rc = 0 if exc is None else 1
        cb(self, self._userdata, rc, None)

    def _dispatch_message(self, msg: Message) -> None:
        wrapped = MQTTMessage(msg)
        for cb in self._topic_callbacks.iter_match(msg.topic):
            cb(self, self._userdata, wrapped)
        if self.on_message is not None:
            self.on_message(self, self._userdata, wrapped)
