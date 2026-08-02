"""Async-native MQTT client (phase 1).

Owns the transport + IncrementalDecoder + ProtocolEngine loop.

Concurrency invariants (see docs/IMPLEMENTATION-GUIDE.md §1):
- A single writer task drains the outbound queue.
- Publish receipts / SUBACK futures are registered *before* bytes can reach
  the wire.
- User callbacks run outside the engine's synchronous critical section.
"""

from __future__ import annotations

import asyncio
import ssl
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import Any, Literal, Never

from mqttnext.api.models import PublishReceipt, SubscribeResult, UnsubscribeResult
from mqttnext.codec.buffer import DEFAULT_MAX_PACKET_SIZE, IncrementalDecoder
from mqttnext.enums import ConnectionState, MQTTProtocolVersion, QoS
from mqttnext.errors import (
    FlowControlError,
    MQTTError,
    MQTTTimeoutError,
    MalformedPacketError,
    PacketTooLargeError,
    ProtocolError,
)
from mqttnext.packets import AuthPacket, ConnAckPacket, SubscribeOptions, encode_disconnect
from mqttnext.protocol.engine import (
    DisconnectInfo,
    EffectKind,
    EngineConfig,
    EngineEffect,
    ProtocolEngine,
    PublishFailure,
)
from mqttnext.protocol.negotiated import NegotiatedSettings
from mqttnext.protocol.reconnect import ReconnectPolicy
from mqttnext.persistence.memory import InflightStore
from mqttnext.transport.tcp import AsyncTransport, TcpTransport
from mqttnext.transport.unix import UnixSocketTransport
from mqttnext.transport.websocket import WebSocketTransport
from mqttnext.transport.writes import WriteItem, item_size
from mqttnext.types import Message, Properties

OnMessage = Callable[[Message], Any]
OnConnect = Callable[[ConnAckPacket], Any]
OnDisconnect = Callable[[BaseException | None], Any]
OnAuth = Callable[[AuthPacket], Any]
MessageDelivery = Literal["auto", "iterator", "callback", "both"]

_MESSAGE_SENTINEL = object()


class AsyncClient:
    def __init__(
        self,
        client_id: str = "",
        *,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
        clean_start: bool = True,
        keepalive: int = 60,
        username: str | None = None,
        password: bytes | str | None = None,
        local_receive_maximum: int = 100,
        connect_properties: Properties | None = None,
        will: Message | None = None,
        will_properties: Properties | None = None,
        maximum_packet_size: int | None = None,
        topic_alias_maximum: int = 0,
        reconnect: ReconnectPolicy | None = None,
        ping_timeout: float | None = None,
        ack_timeout: float = 30.0,
        max_outbound_bytes: int = 1 * 1024 * 1024,
        max_outbound_messages: int = 10_000,
        max_pending_messages: int = 65_536,
        message_delivery: MessageDelivery = "auto",
        manual_ack: bool = False,
        store: InflightStore | None = None,
        auth_handler: OnAuth | None = None,
    ) -> None:
        if message_delivery not in ("auto", "iterator", "callback", "both"):
            raise ValueError(
                "message_delivery must be 'auto', 'iterator', 'callback', or 'both'"
            )
        if max_pending_messages <= 0:
            raise ValueError("max_pending_messages must be greater than 0")
        if max_outbound_messages <= 0:
            raise ValueError("max_outbound_messages must be greater than 0")
        if max_outbound_bytes <= 0:
            raise ValueError("max_outbound_bytes must be greater than 0")
        if ack_timeout <= 0:
            raise ValueError("ack_timeout must be greater than 0")
        if ping_timeout is not None and ping_timeout <= 0:
            raise ValueError("ping_timeout must be greater than 0")
        if not isinstance(client_id, str):
            raise ValueError("client_id must be a string")
        if username is not None and not isinstance(username, str):
            raise ValueError("username must be a string or None")
        if password is not None and not isinstance(password, (bytes, str)):
            raise ValueError("password must be bytes, str, or None")
        self._message_delivery = message_delivery
        self._max_pending_messages = max_pending_messages
        effective_max_packet_size = (
            maximum_packet_size
            if maximum_packet_size is not None
            else DEFAULT_MAX_PACKET_SIZE
        )
        pwd = password.encode("utf-8") if isinstance(password, str) else password
        self._engine = ProtocolEngine(
            EngineConfig(
                client_id=client_id,
                protocol=protocol,
                clean_start=clean_start,
                keepalive=keepalive,
                username=username,
                password=pwd,
                local_receive_maximum=local_receive_maximum,
                connect_properties=connect_properties,
                will=will,
                will_properties=will_properties,
                maximum_packet_size=effective_max_packet_size,
                topic_alias_maximum=topic_alias_maximum,
                manual_ack=manual_ack,
                accept_auth=auth_handler is not None,
            ),
            store=store,
        )
        self._decoder = IncrementalDecoder(
            max_packet_size=effective_max_packet_size
        )
        self._transport: AsyncTransport | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._writer_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._engine_lock = asyncio.Lock()
        self._effect_flush_lock = asyncio.Lock()
        self._pending_effects: deque[EngineEffect] = deque()
        self._callback_tasks: set[asyncio.Task[Any]] = set()
        self._outbound: asyncio.Queue[WriteItem] = asyncio.Queue()
        self._outbound_bytes = 0
        self._max_outbound_bytes = max_outbound_bytes
        self._max_outbound_messages = max_outbound_messages
        self._outbound_space = asyncio.Condition()
        self._outbound_waiters = 0
        self._connack_fut: asyncio.Future[ConnAckPacket] | None = None
        self._receipts: dict[int, PublishReceipt] = {}
        self._sub_futs: dict[int, asyncio.Future[SubscribeResult]] = {}
        self._unsub_futs: dict[int, asyncio.Future[UnsubscribeResult]] = {}
        self._messages: asyncio.Queue[Message | object] = asyncio.Queue(
            maxsize=self._max_pending_messages
        )
        self._closed = asyncio.Event()
        self._disconnect_exc: BaseException | None = None
        self._last_outbound = 0.0
        self._ping_pending = False
        self._ping_deadline = 0.0
        self._connected_at = 0.0
        self._host = ""
        self._port = 1883
        self._ssl: ssl.SSLContext | bool | None = None
        self._unix_path: str | None = None
        self._ws_url: str | None = None
        self._ws_headers: dict[str, str] | None = None
        self._reconnect = reconnect if reconnect is not None else ReconnectPolicy(enabled=False)
        self._ping_timeout = ping_timeout
        self._ack_timeout = ack_timeout
        self._intentional_disconnect = False
        self._transport_factory: Callable[..., Awaitable[AsyncTransport]] = TcpTransport.connect
        self._last_disconnect: DisconnectInfo | None = None

        self.on_message: OnMessage | None = None
        self.on_connect: OnConnect | None = None
        self.on_disconnect: OnDisconnect | None = None
        self.auth_handler: OnAuth | None = auth_handler

    @property
    def state(self) -> ConnectionState:
        return self._engine.state

    @property
    def is_connected(self) -> bool:
        return self._engine.state == ConnectionState.CONNECTED

    @property
    def negotiated(self) -> NegotiatedSettings:
        return self._engine.negotiated

    @property
    def effective_client_id(self) -> str:
        return self.negotiated.effective_client_id(self._engine.config.client_id)

    async def connect(
        self,
        host: str,
        port: int = 1883,
        *,
        ssl: ssl.SSLContext | bool | None = None,
        timeout: float | None = None,
    ) -> ConnAckPacket:
        async with self._lifecycle_lock:
            self._reset_message_stream()
            self._host = host
            self._port = port
            self._ssl = ssl
            was_alt = self._unix_path is not None or self._ws_url is not None
            self._unix_path = None
            self._ws_url = None
            self._ws_headers = None
            if was_alt:
                self._transport_factory = TcpTransport.connect
            self._intentional_disconnect = False
            timeout = timeout if timeout is not None else self._reconnect.connect_timeout
            self._reconnect.reset()
            return await self._connect_once_locked(host, port, ssl=ssl, timeout=timeout)

    async def connect_unix(
        self,
        path: str,
        *,
        timeout: float | None = None,
    ) -> ConnAckPacket:
        """Connect over a Unix domain socket (AF_UNIX)."""
        async with self._lifecycle_lock:
            self._reset_message_stream()
            self._unix_path = path
            self._ws_url = None
            self._ws_headers = None
            self._host = path
            self._port = 0
            self._ssl = None
            self._intentional_disconnect = False

            async def _factory(
                host: str,
                port: int,
                *,
                ssl: object | None = None,
            ) -> AsyncTransport:
                return await UnixSocketTransport.connect(self._unix_path or host)

            self._transport_factory = _factory
            timeout = timeout if timeout is not None else self._reconnect.connect_timeout
            self._reconnect.reset()
            return await self._connect_once_locked(path, 0, ssl=None, timeout=timeout)

    async def connect_ws(
        self,
        url: str,
        *,
        ssl: ssl.SSLContext | bool | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> ConnAckPacket:
        """Connect over MQTT-over-WebSocket (``ws://`` / ``wss://``)."""
        async with self._lifecycle_lock:
            self._reset_message_stream()
            self._ws_url = url
            self._ws_headers = extra_headers
            self._unix_path = None
            self._host = url
            self._port = 0
            self._ssl = ssl
            self._intentional_disconnect = False

            async def _factory(
                host: str,
                port: int,
                *,
                ssl: object | None = None,
            ) -> AsyncTransport:
                return await WebSocketTransport.connect(
                    self._ws_url or host,
                    ssl=ssl if ssl is not None else self._ssl,
                    extra_headers=self._ws_headers,
                )

            self._transport_factory = _factory
            timeout = timeout if timeout is not None else self._reconnect.connect_timeout
            self._reconnect.reset()
            return await self._connect_once_locked(url, 0, ssl=ssl, timeout=timeout)

    async def _connect_once_locked(
        self,
        host: str,
        port: int,
        *,
        ssl: ssl.SSLContext | bool | None = None,
        timeout: float = 30.0,
    ) -> ConnAckPacket:
        if self._engine.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            raise ProtocolError("Already connected or connecting")
        try:
            try:
                transport = await asyncio.wait_for(
                    self._transport_factory(host, port, ssl=ssl), timeout=timeout
                )
            except TimeoutError as exc:
                raise MQTTTimeoutError("Transport connection timed out") from exc
            self._transport = transport
            self._closed.clear()
            self._disconnect_exc = None
            self._last_disconnect = None
            self._decoder.clear()
            self._outbound = asyncio.Queue()
            self._outbound_bytes = 0
            self._ping_pending = False
            connect_packet = self._engine.begin_connect()
            loop = asyncio.get_running_loop()
            self._connack_fut = loop.create_future()
            self._writer_task = asyncio.create_task(
                self._write_loop(), name="mqttnext-writer"
            )
            await self._enqueue_outbound(connect_packet)
            self._reader_task = asyncio.create_task(
                self._read_loop(), name="mqttnext-reader"
            )
            try:
                connack = await asyncio.wait_for(self._connack_fut, timeout=timeout)
            except TimeoutError as exc:
                raise MQTTTimeoutError("CONNACK timed out") from exc
            if connack.reason_code != 0:
                raise ProtocolError(
                    f"Connection refused: reason_code={connack.reason_code}"
                )
            self._connected_at = time.monotonic()
            self._last_outbound = time.monotonic()
            self._keepalive_task = asyncio.create_task(
                self._keepalive_loop(), name="mqttnext-keepalive"
            )
            return connack
        except BaseException:
            self._intentional_disconnect = True
            if self._connack_fut is not None and not self._connack_fut.done():
                self._connack_fut.cancel()
            try:
                await self._force_close()
            except BaseException:
                pass
            if self._engine.state not in (
                ConnectionState.NEW,
                ConnectionState.DISCONNECTED,
            ):
                self._engine.notify_transport_closed()
                self._engine.take_effects()
            raise

    async def disconnect(self, reason_code: int = 0) -> None:
        self._intentional_disconnect = True
        reconnect_task = self._reconnect_task
        if reconnect_task is not None and reconnect_task is not asyncio.current_task():
            reconnect_task.cancel()
            try:
                await reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None
        async with self._lifecycle_lock:
            if self._transport is None:
                return
            if self.is_connected:
                packet = self._engine.begin_disconnect(reason_code)
                await self._enqueue_outbound(packet)
                try:
                    # Skip the wait if the writer already died (connection lost).
                    if self._writer_task is not None and not self._writer_task.done():
                        await asyncio.wait_for(self._outbound.join(), timeout=5.0)
                except TimeoutError:
                    pass
            await self._force_close()

    async def publish(
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

    async def auth(
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

    def set_auth_handler(self, handler: OnAuth | None) -> None:
        """Register or clear the enhanced-authentication handler."""
        self.auth_handler = handler
        self._engine.config.accept_auth = handler is not None

    async def subscribe(
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

    async def unsubscribe(
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

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            item = await self._messages.get()
            if item is _MESSAGE_SENTINEL:
                return
            yield item  # type: ignore[misc]

    async def ack(self, message: Message) -> None:
        """Acknowledge an inbound QoS>0 message when ``manual_ack=True``.

        Defers PUBACK (QoS 1) or PUBCOMP (QoS 2). PUBREC is always immediate.
        """
        if message.mid is None:
            return
        async with self._engine_lock:
            self._engine.ack(message.mid)
            self._collect_effects_locked()
        await self._drain_effects()

    async def _read_loop(self) -> None:
        assert self._transport is not None
        try:
            while not self._transport.is_closing():
                data = await self._transport.read(256 * 1024)
                if not data:
                    break
                self._decoder.feed(data)
                # Drain the whole buffer before waiting on the socket again —
                # a fixed packet cap would strand frames when the peer pauses.
                # One flush per read keeps SEND-before-MESSAGE ordering while
                # avoiding N await points for N/100 batches.
                handled = 0
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
        except asyncio.CancelledError:
            raise
        except (PacketTooLargeError, MalformedPacketError, ProtocolError) as exc:
            # Fatal wire/protocol error: send a normative DISCONNECT (v5) before
            # tearing down, so a strict broker sees *why* we left.
            await self._send_fatal_disconnect(exc)
            self._disconnect_exc = exc
            if not self._will_reconnect():
                self._fail_pending(exc)
        except Exception as exc:
            self._disconnect_exc = exc
            if not self._will_reconnect():
                self._fail_pending(exc)
        finally:
            async with self._engine_lock:
                self._engine.notify_transport_closed()
                self._collect_effects_locked()
            try:
                await self._drain_effects()
            except (Exception, asyncio.CancelledError):
                pass
            if self._disconnect_exc is None:
                self._disconnect_exc = MQTTError("Connection closed")
            self._fail_non_replayable(self._disconnect_exc)
            will_reconnect = self._will_reconnect()
            if not will_reconnect:
                self._fail_pending(self._disconnect_exc)
                # Wake any publish() parked on outbound backpressure.
                async with self._outbound_space:
                    self._outbound_space.notify_all()
                # Cancel writer + close transport so no task/fd leaks.
                if self._writer_task is not None and self._writer_task is not asyncio.current_task():
                    self._writer_task.cancel()
                    try:
                        await self._writer_task
                    except (asyncio.CancelledError, Exception):
                        pass
                    self._writer_task = None
                if self._transport is not None:
                    try:
                        await self._transport.close()
                    except Exception:
                        pass
            self._closed.set()
            if not will_reconnect:
                try:
                    self._messages.put_nowait(_MESSAGE_SENTINEL)
                except asyncio.QueueFull:
                    try:
                        self._messages.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        self._messages.put_nowait(_MESSAGE_SENTINEL)
                    except asyncio.QueueFull:
                        pass
            try:
                await self._invoke(self.on_disconnect, self._disconnect_exc)
            except Exception:
                pass
            if will_reconnect and (
                self._reconnect_task is None or self._reconnect_task.done()
            ):
                self._reconnect_task = asyncio.create_task(
                    self._reconnect_loop(), name="mqttnext-reconnect"
                )

    def _will_reconnect(self) -> bool:
        reason = None
        if self._last_disconnect is not None and self._last_disconnect.from_broker:
            reason = self._last_disconnect.reason_code
        return (
            not self._intentional_disconnect
            and self._reconnect.enabled
            and self._reconnect.should_retry(reason, self._engine.config.protocol)
        )

    async def _write_contiguous(
        self, transport: AsyncTransport, parts: list[bytes]
    ) -> None:
        if not parts:
            return
        write_many = getattr(transport, "write_many", None)
        if write_many is not None:
            await write_many(parts)
        else:
            for part in parts:
                await transport.write(part)
        parts.clear()

    async def _write_loop(self) -> None:
        assert self._transport is not None
        try:
            while True:
                first = await self._outbound.get()
                batch: list[WriteItem] = [first]
                while len(batch) < 256:
                    try:
                        batch.append(self._outbound.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                try:
                    # Coalesce contiguous small frames into one writelines call.
                    # Never await drain() after the batch (deadlocks vs reader ACK).
                    contiguous: list[bytes] = []
                    transport = self._transport
                    if transport is None:
                        raise ConnectionError("Transport closed while writer was active")

                    for data in batch:
                        if isinstance(data, tuple):
                            await self._write_contiguous(transport, contiguous)
                            for part in data:
                                await transport.write(part)
                        else:
                            contiguous.append(data)
                    await self._write_contiguous(transport, contiguous)
                    self._last_outbound = time.monotonic()
                finally:
                    released = 0
                    for data in batch:
                        released += item_size(data)
                        self._outbound.task_done()
                    async with self._outbound_space:
                        self._outbound_bytes = max(0, self._outbound_bytes - released)
                        if self._outbound_waiters:
                            self._outbound_space.notify_all()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._disconnect_exc = exc
            if not self._will_reconnect():
                self._fail_pending(exc)
            async with self._engine_lock:
                self._engine.notify_transport_closed()
                self._collect_effects_locked()
            await self._drain_effects()
            self._closed.set()
            # Close transport so the reader unblocks and runs shared cleanup.
            if self._transport is not None:
                await self._transport.close()

    async def _enqueue_outbound(self, item: WriteItem, *, nowait: bool = False) -> None:
        size = item_size(item)
        # Fast path (no Condition): safe under asyncio's cooperative scheduling
        # as long as we do not await between the capacity check and the update.
        messages_full = self._outbound.qsize() >= self._max_outbound_messages
        bytes_blocked = (
            self._outbound_bytes + size > self._max_outbound_bytes
            and not (self._outbound_bytes == 0 and self._outbound.empty())
        )
        if not messages_full and not bytes_blocked:
            self._outbound.put_nowait(item)
            self._outbound_bytes += size
            return
        if nowait:
            raise FlowControlError("Outbound backpressure limit reached")

        async with self._outbound_space:
            while True:
                messages_full = self._outbound.qsize() >= self._max_outbound_messages
                # Allow a single oversized item into an empty queue (segmented
                # payloads can exceed max_outbound_bytes by the MQTT header).
                bytes_blocked = (
                    self._outbound_bytes + size > self._max_outbound_bytes
                    and not (self._outbound_bytes == 0 and self._outbound.empty())
                )
                if not messages_full and not bytes_blocked:
                    break
                # Escape hatch: if the writer is idle but space accounting is
                # wedged, do not block protocol forever.
                if self._outbound.empty() and self._outbound_bytes == 0:
                    break
                self._outbound_waiters += 1
                try:
                    await self._outbound_space.wait()
                finally:
                    self._outbound_waiters -= 1
            self._outbound.put_nowait(item)
            self._outbound_bytes += size

    async def _keepalive_loop(self) -> None:
        try:
            while not self._closed.is_set():
                k = self._effective_keepalive()
                if k <= 0:
                    await asyncio.sleep(1.0)
                    continue
                now = time.monotonic()
                if self._ping_pending:
                    if now >= self._ping_deadline:
                        self._disconnect_exc = MQTTTimeoutError("PINGRESP timed out")
                        await self._force_close()
                        return
                    await asyncio.sleep(min(0.5, self._ping_deadline - now))
                    continue
                due = self._last_outbound + k
                if now >= due:
                    async with self._engine_lock:
                        self._engine.queue_ping()
                        self._collect_effects_locked()
                    # A lost PINGREQ beats a wedged keepalive under backpressure.
                    try:
                        await self._drain_effects(nowait=True)
                    except FlowControlError:
                        pass
                    self._ping_pending = True
                    ping_to = self._ping_timeout
                    if ping_to is None:
                        ping_to = max(k / 2, 5.0)
                    self._ping_deadline = now + ping_to
                else:
                    await asyncio.sleep(min(1.0, due - now))
        except asyncio.CancelledError:
            raise

    async def _reconnect_loop(self) -> None:
        try:
            while self._reconnect.enabled and not self._intentional_disconnect:
                reason = None
                if self._last_disconnect is not None and self._last_disconnect.from_broker:
                    reason = self._last_disconnect.reason_code
                elif isinstance(self._disconnect_exc, ProtocolError):
                    msg = str(self._disconnect_exc)
                    if "reason_code=" in msg:
                        try:
                            reason = int(msg.rsplit("=", 1)[-1])
                        except ValueError:
                            reason = None
                if not self._reconnect.should_retry(reason, self._engine.config.protocol):
                    self._fail_pending(
                        self._disconnect_exc or MQTTError("Reconnect exhausted")
                    )
                    return
                delay = self._reconnect.next_delay()
                await asyncio.sleep(delay)
                try:
                    async with self._lifecycle_lock:
                        if self._intentional_disconnect:
                            return
                        await self._force_close(preserve_reconnect=True)
                        await self._connect_once_locked(
                            self._host,
                            self._port,
                            ssl=self._ssl,
                            timeout=self._reconnect.connect_timeout,
                        )
                    # Only clear backoff after the connection stays up.
                    await asyncio.sleep(self._reconnect.stable_after)
                    if self.is_connected:
                        self._reconnect.reset()
                        return
                    # Dropped again during the stability window — keep retrying.
                    continue
                except Exception as exc:
                    self._disconnect_exc = exc
                    continue
        except asyncio.CancelledError:
            raise
        finally:
            self._reconnect_task = None

    def _effective_keepalive(self) -> int:
        negotiated = self._engine.negotiated.server_keep_alive
        if negotiated is not None:
            return negotiated
        return self._engine.config.keepalive

    def _collect_effects_locked(self) -> None:
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
                except FlowControlError:
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
                async with self._engine_lock:
                    self._engine.queue_auth(
                        reason_code=response.reason_code,
                        properties=response.properties,
                    )
                    self._collect_effects_locked()
        elif kind is EffectKind.MESSAGE:
            msg: Message = effect.data
            callback_delivery = self.on_message is not None and self._message_delivery in (
                "auto",
                "callback",
                "both",
            )
            iterator_delivery = self._message_delivery in ("iterator", "both") or (
                self._message_delivery == "auto" and self.on_message is None
            )
            if iterator_delivery:
                await self._messages.put(msg)
            if callback_delivery:
                assert self.on_message is not None
                self._spawn_callback(self.on_message, msg)
            if msg.mid is not None:
                async with self._engine_lock:
                    self._engine.mark_inbound_delivered(msg.mid)
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

    def _reset_message_stream(self) -> None:
        if self._closed.is_set():
            self._messages = asyncio.Queue(maxsize=self._max_pending_messages)
            self._closed.clear()

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

    def _fail_non_replayable(self, exc: BaseException) -> None:
        for fut in self._sub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._sub_futs.clear()
        for fut in self._unsub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._unsub_futs.clear()

    def _fail_pending(self, exc: BaseException) -> None:
        for receipt in self._receipts.values():
            receipt._error = exc
            if receipt._event is not None:
                receipt._event.set()
        self._receipts.clear()
        self._fail_non_replayable(exc)

    async def _send_fatal_disconnect(self, exc: BaseException) -> None:
        """Best-effort normative DISCONNECT before a fatal close (MQTT 5).

        Maps the error to its spec reason code; no-op on v3.1.1 or if the
        transport is already unusable. Never raises.
        """
        if self._engine.config.protocol != MQTTProtocolVersion.MQTTv5:
            return
        if self._transport is None or self._transport.is_closing():
            return
        reason = 0x82  # Protocol Error (generic)
        if isinstance(exc, PacketTooLargeError):
            reason = 0x95  # Packet too large
        elif isinstance(exc, MalformedPacketError):
            reason = 0x81  # Malformed Packet
        try:
            await self._transport.write(encode_disconnect(reason, MQTTProtocolVersion.MQTTv5))
        except Exception:
            pass

    async def _invoke(self, callback: Callable[..., Any] | None, *args: Any) -> Any:
        if callback is None:
            return None
        result = callback(*args)
        if isinstance(result, Awaitable):
            return await result
        return result

    async def _force_close(self, *, preserve_reconnect: bool = False) -> None:
        current = asyncio.current_task()
        tasks = [self._reader_task, self._writer_task, self._keepalive_task]
        if not preserve_reconnect:
            tasks.append(self._reconnect_task)
        tasks.extend(self._callback_tasks)
        for task in tasks:
            if task is not None and task is not current:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        if self._reader_task is not current:
            self._reader_task = None
        if self._writer_task is not current:
            self._writer_task = None
        if self._keepalive_task is not current:
            self._keepalive_task = None
        if not preserve_reconnect and self._reconnect_task is not current:
            self._reconnect_task = None
        self._callback_tasks = {
            task
            for task in self._callback_tasks
            if task is current and not task.done()
        }
        if self._transport is not None:
            try:
                await self._transport.close()
            except Exception:
                pass
            self._transport = None
        self._closed.set()
