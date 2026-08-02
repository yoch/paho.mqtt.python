from __future__ import annotations

from pathlib import Path


TARGET = Path("mqttnext/src/mqttnext/api/async_client.py")
TEST_TARGET = Path("mqttnext/tests/unit/test_effect_atomicity.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_section(text: str, start: str, end: str, new: str, label: str) -> str:
    start_pos = text.find(start)
    if start_pos < 0:
        raise RuntimeError(f"{label}: start marker not found")
    end_pos = text.find(end, start_pos)
    if end_pos < 0:
        raise RuntimeError(f"{label}: end marker not found")
    return text[:start_pos] + new + text[end_pos:]


text = TARGET.read_text()

text = replace_once(
    text,
    """import ssl
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
""",
    """import ssl
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
""",
    "deque import",
)
text = replace_once(
    text,
    """    EffectKind,
    EngineConfig,
    ProtocolEngine,
""",
    """    EffectKind,
    EngineConfig,
    EngineEffect,
    ProtocolEngine,
""",
    "EngineEffect import",
)
text = replace_once(
    text,
    """        self._reconnect_task: asyncio.Task[None] | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._outbound: asyncio.Queue[WriteItem] = asyncio.Queue()
""",
    """        self._reconnect_task: asyncio.Task[None] | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._engine_lock = asyncio.Lock()
        self._effect_flush_lock = asyncio.Lock()
        self._pending_effects: deque[EngineEffect] = deque()
        self._callback_tasks: set[asyncio.Task[Any]] = set()
        self._outbound: asyncio.Queue[WriteItem] = asyncio.Queue()
""",
    "atomicity state",
)

publish = '''    async def publish(
        self,
        topic: str,
        payload: bytes | str = b"",
        *,
        qos: int | QoS = 0,
        retain: bool = False,
        properties: Properties | None = None,
        nowait: bool = False,
    ) -> PublishReceipt:
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        async with self._engine_lock:
            handle = self._engine.queue_publish(
                topic,
                data,
                qos=qos,
                retain=retain,
                properties=properties,
            )
            if handle.qos == QoS.AT_MOST_ONCE:
                receipt = PublishReceipt(mid=None, qos=handle.qos, _event=None)
            else:
                assert handle.mid is not None
                receipt = PublishReceipt(
                    mid=handle.mid,
                    qos=handle.qos,
                    _event=asyncio.Event(),
                )
                self._receipts[handle.mid] = receipt
            self._collect_effects_locked()
        await self._drain_effects(nowait=nowait)
        return receipt

'''
text = replace_section(text, "    async def publish(\n", "    async def auth(\n", publish, "publish")

auth = '''    async def auth(
        self,
        reason_code: int = 0x19,
        properties: Properties | None = None,
    ) -> None:
        """Send a client AUTH packet (MQTT 5 continue / re-authenticate)."""
        async with self._engine_lock:
            self._engine.config.accept_auth = True
            self._engine.queue_auth(reason_code=reason_code, properties=properties)
            self._collect_effects_locked()
        await self._drain_effects()

'''
text = replace_section(
    text,
    "    async def auth(\n",
    "    def set_auth_handler(\n",
    auth,
    "auth",
)

subscribe = '''    async def subscribe(
        self,
        topics: str | Iterable[str | tuple[str, SubscribeOptions | int | QoS]],
        *,
        qos: int | QoS = 0,
        properties: Properties | None = None,
        timeout: float | None = None,
    ) -> SubscribeResult:
        loop = asyncio.get_running_loop()
        async with self._engine_lock:
            mid = self._engine.queue_subscribe(
                topics,
                qos=qos,
                properties=properties,
            )
            fut: asyncio.Future[SubscribeResult] = loop.create_future()
            self._sub_futs[mid] = fut
            self._collect_effects_locked()
        await self._drain_effects()
        try:
            return await asyncio.wait_for(
                fut, timeout=timeout if timeout is not None else self._ack_timeout
            )
        except TimeoutError as exc:
            self._sub_futs.pop(mid, None)
            raise MQTTTimeoutError(f"SUBACK timed out for mid={mid}") from exc

'''
text = replace_section(
    text,
    "    async def subscribe(\n",
    "    async def unsubscribe(\n",
    subscribe,
    "subscribe",
)

unsubscribe = '''    async def unsubscribe(
        self,
        topics: str | Iterable[str],
        *,
        timeout: float | None = None,
    ) -> UnsubscribeResult:
        loop = asyncio.get_running_loop()
        async with self._engine_lock:
            mid = self._engine.queue_unsubscribe(topics)
            fut: asyncio.Future[UnsubscribeResult] = loop.create_future()
            self._unsub_futs[mid] = fut
            self._collect_effects_locked()
        await self._drain_effects()
        try:
            return await asyncio.wait_for(
                fut, timeout=timeout if timeout is not None else self._ack_timeout
            )
        except TimeoutError as exc:
            self._unsub_futs.pop(mid, None)
            raise MQTTTimeoutError(f"UNSUBACK timed out for mid={mid}") from exc

'''
text = replace_section(
    text,
    "    async def unsubscribe(\n",
    "    async def messages(\n",
    unsubscribe,
    "unsubscribe",
)

ack = '''    async def ack(self, message: Message) -> None:
        """Acknowledge an inbound QoS>0 message when ``manual_ack=True``.

        Defers PUBACK (QoS 1) or PUBCOMP (QoS 2). PUBREC is always immediate.
        """
        if message.mid is None:
            return
        async with self._engine_lock:
            self._engine.ack(message.mid)
            self._collect_effects_locked()
        await self._drain_effects()

'''
text = replace_section(text, "    async def ack(\n", "    async def _read_loop(\n", ack, "ack")

text = replace_once(
    text,
    """                handled = 0
                while True:
                    n = self._decoder.process_packets(
                        self._engine.handle_raw, limit=256
                    )
                    if n == 0:
                        break
                    handled += n
                if handled:
                    await self._flush_effects()
""",
    """                handled = 0
                async with self._engine_lock:
                    while True:
                        n = self._decoder.process_packets(
                            self._engine.handle_raw, limit=256
                        )
                        if n == 0:
                            break
                        handled += n
                    if handled:
                        self._collect_effects_locked()
                if handled:
                    await self._drain_effects()
""",
    "reader effect collection",
)
text = replace_once(
    text,
    """        finally:
            self._engine.notify_transport_closed()
            try:
                await self._flush_effects()
""",
    """        finally:
            async with self._engine_lock:
                self._engine.notify_transport_closed()
                self._collect_effects_locked()
            try:
                await self._drain_effects()
""",
    "reader close effects",
)
text = replace_once(
    text,
    """            self._engine.notify_transport_closed()
            await self._flush_effects()
            self._closed.set()
""",
    """            async with self._engine_lock:
                self._engine.notify_transport_closed()
                self._collect_effects_locked()
            await self._drain_effects()
            self._closed.set()
""",
    "writer close effects",
)
text = replace_once(
    text,
    """                if now >= due:
                    self._engine.queue_ping()
                    # A lost PINGREQ beats a wedged keepalive under backpressure.
                    try:
                        await self._flush_effects(nowait=True)
""",
    """                if now >= due:
                    async with self._engine_lock:
                        self._engine.queue_ping()
                        self._collect_effects_locked()
                    # A lost PINGREQ beats a wedged keepalive under backpressure.
                    try:
                        await self._drain_effects(nowait=True)
""",
    "keepalive effects",
)

flush_start = "    async def _flush_effects(self, *, nowait: bool = False) -> None:\n"
flush_end = "    def _fail_pending(self, exc: BaseException) -> None:\n"
flush = '''    def _collect_effects_locked(self) -> None:
        effects = self._engine.take_effects()
        self._pending_effects.extend(
            effect for effect in effects if effect.kind is EffectKind.SEND
        )
        self._pending_effects.extend(
            effect for effect in effects if effect.kind is not EffectKind.SEND
        )

    async def _flush_effects(self, *, nowait: bool = False) -> None:
        async with self._engine_lock:
            self._collect_effects_locked()
        await self._drain_effects(nowait=nowait)

    async def _drain_effects(self, *, nowait: bool = False) -> None:
        async with self._effect_flush_lock:
            while self._pending_effects:
                effect = self._pending_effects[0]
                try:
                    await self._apply_effect(effect, nowait=nowait)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self._pending_effects.popleft()
                    raise
                else:
                    self._pending_effects.popleft()

    async def _apply_effect(
        self,
        effect: EngineEffect,
        *,
        nowait: bool,
    ) -> None:
        kind = effect.kind
        if kind is EffectKind.SEND:
            await self._enqueue_outbound(effect.data, nowait=nowait)
        elif kind is EffectKind.CONNACK:
            connack: ConnAckPacket = effect.data
            if self._connack_fut is not None and not self._connack_fut.done():
                self._connack_fut.set_result(connack)
            if self.on_connect is not None:
                self._spawn_callback(self.on_connect, connack)
        elif kind is EffectKind.AUTH:
            challenge: AuthPacket = effect.data
            if self.auth_handler is None:
                await self._enqueue_outbound(
                    encode_disconnect(0x8C, self._engine.config.protocol),
                    nowait=nowait,
                )
                return
            response = await asyncio.wait_for(
                self._invoke(self.auth_handler, challenge), timeout=10.0
            )
            if isinstance(response, AuthPacket):
                await self._enqueue_outbound(
                    response.encode(self._engine.config.protocol),
                    nowait=nowait,
                )
        elif kind is EffectKind.MESSAGE:
            msg: Message = effect.data
            await self._messages.put(msg)
            if self.on_message is not None:
                self._spawn_callback(self.on_message, msg)
        elif kind is EffectKind.PUBLISH_COMPLETE:
            mid: int = effect.data
            receipt = self._receipts.pop(mid, None)
            if receipt is not None and receipt._event is not None:
                receipt._event.set()
        elif kind is EffectKind.PUBLISH_FAILED:
            failure: PublishFailure = effect.data
            receipt = self._receipts.pop(failure.mid, None)
            if receipt is not None:
                receipt._error = failure.reason
                if receipt._event is not None:
                    receipt._event.set()
        elif kind is EffectKind.SUBACK:
            result = SubscribeResult.from_packet(effect.data)
            fut = self._sub_futs.pop(result.mid, None)
            if fut is not None and not fut.done():
                fut.set_result(result)
        elif kind is EffectKind.UNSUBACK:
            result = UnsubscribeResult.from_packet(effect.data)
            fut = self._unsub_futs.pop(result.mid, None)
            if fut is not None and not fut.done():
                fut.set_result(result)
        elif kind is EffectKind.PINGRESP:
            self._ping_pending = False
        elif kind is EffectKind.DISCONNECTED:
            info = effect.data
            if isinstance(info, DisconnectInfo):
                self._last_disconnect = info
                if info.from_broker and self._transport is not None:
                    try:
                        await self._transport.close()
                    except Exception:
                        pass
        elif kind is EffectKind.PROTOCOL_ERROR:
            raise ProtocolError(str(effect.data))
        else:
            never: Never = kind
            raise MQTTError(f"Unhandled effect {never!r}")

    def _spawn_callback(self, callback: Callable[..., Any], *args: Any) -> None:
        task = asyncio.create_task(self._invoke(callback, *args))
        self._callback_tasks.add(task)
        task.add_done_callback(self._callback_done)

    def _callback_done(self, task: asyncio.Task[Any]) -> None:
        self._callback_tasks.discard(task)
        try:
            task.result()
        except (asyncio.CancelledError, Exception):
            pass

'''
text = replace_section(text, flush_start, flush_end, flush, "effect flushing")

text = replace_once(
    text,
    """        tasks = [self._reader_task, self._writer_task, self._keepalive_task]
        if not preserve_reconnect:
            tasks.append(self._reconnect_task)
""",
    """        tasks = [self._reader_task, self._writer_task, self._keepalive_task]
        if not preserve_reconnect:
            tasks.append(self._reconnect_task)
        tasks.extend(self._callback_tasks)
""",
    "callback task cleanup list",
)
text = replace_once(
    text,
    """        if not preserve_reconnect and self._reconnect_task is not current:
            self._reconnect_task = None
        if self._transport is not None:
""",
    """        if not preserve_reconnect and self._reconnect_task is not current:
            self._reconnect_task = None
        self._callback_tasks = {
            task
            for task in self._callback_tasks
            if task is current and not task.done()
        }
        if self._transport is not None:
""",
    "callback task cleanup state",
)

TARGET.write_text(text)

TEST_TARGET.write_text(
    '''"""Atomic effect transfer and callback task lifecycle."""

from __future__ import annotations

import asyncio

import pytest

from mqttnext.api.async_client import AsyncClient
from mqttnext.enums import ConnectionState, EffectKind if False else QoS
from mqttnext.protocol.engine import EffectKind
from mqttnext.types import Message


async def test_cancelled_backpressure_keeps_send_effect_for_retry() -> None:
    client = AsyncClient(
        client_id="effect-cancel",
        max_outbound_messages=1,
        max_outbound_bytes=1,
    )
    client._engine.state = ConnectionState.CONNECTED
    await client._enqueue_outbound(b"x")

    publishing = asyncio.create_task(client.publish("effect/t", b"payload", qos=0))
    for _ in range(100):
        if client._outbound_waiters:
            break
        await asyncio.sleep(0)
    assert client._outbound_waiters == 1

    publishing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await publishing
    assert any(
        effect.kind is EffectKind.SEND for effect in client._pending_effects
    )

    blocked = client._outbound.get_nowait()
    client._outbound.task_done()
    client._outbound_bytes -= len(blocked)
    async with client._outbound_space:
        client._outbound_space.notify_all()

    await client._drain_effects()
    assert not client._pending_effects
    assert client._outbound.qsize() == 1


async def test_callback_exception_is_collected() -> None:
    client = AsyncClient(client_id="callback-error")
    loop = asyncio.get_running_loop()
    contexts: list[dict[str, object]] = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: contexts.append(context))

    def fail(_message: Message) -> None:
        raise RuntimeError("callback failed")

    try:
        client._spawn_callback(fail, Message(topic="t", payload=b"x"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not client._callback_tasks
        assert contexts == []
    finally:
        loop.set_exception_handler(previous)


async def test_force_close_cancels_callback_tasks() -> None:
    client = AsyncClient(client_id="callback-close")
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_message: Message) -> None:
        started.set()
        await release.wait()

    client._spawn_callback(slow, Message(topic="t", payload=b"x"))
    await started.wait()
    assert len(client._callback_tasks) == 1

    await client._force_close()
    assert not client._callback_tasks
'''
)
