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
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import Any, Never

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
        manual_ack: bool = False,
        store: InflightStore | None = None,
        auth_handler: OnAuth | None = None,
    ) -> None:
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
                maximum_packet_size=maximum_packet_size,
                topic_alias_maximum=topic_alias_maximum,
                manual_ack=manual_ack,
                accept_auth=auth_handler is not None,
            ),
            store=store,
        )
        max_pkt = maximum_packet_size or DEFAULT_MAX_PACKET_SIZE
        self._decoder = IncrementalDecoder(max_packet_size=max_pkt)
        self._transport: AsyncTransport | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._writer_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
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
            maxsize=max_pending_messages
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
        return await self._connect_once(host, port, ssl=ssl, timeout=timeout)

    async def connect_unix(
        self,
        path: str,
        *,
        timeout: float | None = None,
    ) -> ConnAckPacket:
        """Connect over a Unix domain socket (AF_UNIX)."""
        self._unix_path = path
        self._ws_url = None
        self._ws_headers = None
        self._host = path
        self._port = 0
        self._ssl = None
        self._intentional_disconnect = False

        async def _factory(host: str, port: int, *, ssl: object | None = None) -> AsyncTransport:
            return await UnixSocketTransport.connect(self._unix_path or host)

        self._transport_factory = _factory
        timeout = timeout if timeout is not None else self._reconnect.connect_timeout
        self._reconnect.reset()
        return await self._connect_once(path, 0, ssl=None, timeout=timeout)

    async def connect_ws(
        self,
        url: str,
        *,
        ssl: ssl.SSLContext | bool | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> ConnAckPacket:
        """Connect over MQTT-over-WebSocket (``ws://`` / ``wss://``)."""
        self._ws_url = url
        self._ws_headers = extra_headers
        self._unix_path = None
        self._host = url
        self._port = 0
        self._ssl = ssl
        self._intentional_disconnect = False

        async def _factory(host: str, port: int, *, ssl: object | None = None) -> AsyncTransport:
            return await WebSocketTransport.connect(
                self._ws_url or host,
                ssl=ssl if ssl is not None else self._ssl,
                extra_headers=self._ws_headers,
            )

        self._transport_factory = _factory
        timeout = timeout if timeout is not None else self._reconnect.connect_timeout
        self._reconnect.reset()
        return await self._connect_once(url, 0, ssl=ssl, timeout=timeout)

    async def _connect_once(
        self,
        host: str,
        port: int,
        *,
        ssl: ssl.SSLContext | bool | None = None,
        timeout: float = 30.0,
    ) -> ConnAckPacket:
        if self.is_connected:
            raise ProtocolError("Already connected")
        transport = await asyncio.wait_for(
            self._transport_factory(host, port, ssl=ssl), timeout=timeout
        )
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
        self._writer_task = asyncio.create_task(self._write_loop(), name="mqttnext-writer")
        await self._enqueue_outbound(connect_packet)
        self._reader_task = asyncio.create_task(self._read_loop(), name="mqttnext-reader")
        try:
            connack = await asyncio.wait_for(self._connack_fut, timeout=timeout)
        except TimeoutError as exc:
            await self._force_close()
            raise MQTTTimeoutError("CONNACK timed out") from exc
        except Exception:
            await self._force_close()
            raise
        if connack.reason_code != 0:
            await self._force_close()
            raise ProtocolError(f"Connection refused: reason_code={connack.reason_code}")
        self._connected_at = time.monotonic()
        self._last_outbound = time.monotonic()
        self._keepalive_task = asyncio.create_task(
            self._keepalive_loop(), name="mqttnext-keepalive"
        )
        return connack

    async def disconnect(self, reason_code: int = 0) -> None:
        self._intentional_disconnect = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None
        if self._transport is None:
            return
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
        handle = self._engine.queue_publish(
            topic,
            data,
            qos=qos,
            retain=retain,
            properties=properties,
        )
        if handle.qos == QoS.AT_MOST_ONCE:
            # QoS 0 completes at queue time — skip Event allocation.
            receipt = PublishReceipt(mid=None, qos=handle.qos, _event=None)
        else:
            assert handle.mid is not None
            event = asyncio.Event()
            receipt = PublishReceipt(mid=handle.mid, qos=handle.qos, _event=event)
            self._receipts[handle.mid] = receipt
        await self._flush_effects(nowait=nowait)
        return receipt

    async def auth(
        self,
        reason_code: int = 0x19,
        properties: Properties | None = None,
    ) -> None:
        """Send a client AUTH packet (MQTT 5 continue / re-authenticate)."""
        self._engine.config.accept_auth = True
        self._engine.queue_auth(reason_code=reason_code, properties=properties)
        await self._flush_effects()

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
        mid = self._engine.queue_subscribe(topics, qos=qos, properties=properties)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[SubscribeResult] = loop.create_future()
        self._sub_futs[mid] = fut
        await self._flush_effects()
        try:
            return await asyncio.wait_for(
                fut, timeout=timeout if timeout is not None else self._ack_timeout
            )
        except TimeoutError as exc:
            self._sub_futs.pop(mid, None)
            # Do NOT release the mid: a late SUBACK must still resolve it
            # (engine tracks pending sub mids and releases on receipt).
            raise MQTTTimeoutError(f"SUBACK timed out for mid={mid}") from exc

    async def unsubscribe(
        self,
        topics: str | Iterable[str],
        *,
        timeout: float | None = None,
    ) -> UnsubscribeResult:
        mid = self._engine.queue_unsubscribe(topics)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[UnsubscribeResult] = loop.create_future()
        self._unsub_futs[mid] = fut
        await self._flush_effects()
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
        self._engine.ack(message.mid)
        await self._flush_effects()

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
                while True:
                    n = self._decoder.process_packets(
                        self._engine.handle_raw, limit=256
                    )
                    if n == 0:
                        break
                    handled += n
                if handled:
                    await self._flush_effects()
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
            self._engine.notify_transport_closed()
            try:
                await self._flush_effects()
            except (Exception, asyncio.CancelledError):
                pass
            if self._disconnect_exc is None:
                self._disconnect_exc = MQTTError("Connection closed")
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

                    async def _flush_contiguous() -> None:
                        if not contiguous:
                            return
                        write_many = getattr(transport, "write_many", None)
                        if write_many is not None:
                            await write_many(contiguous)
                        else:
                            for part in contiguous:
                                await transport.write(part)
                        contiguous.clear()

                    for data in batch:
                        if isinstance(data, tuple):
                            await _flush_contiguous()
                            for part in data:
                                await transport.write(part)
                        else:
                            contiguous.append(data)
                    await _flush_contiguous()
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
            self._engine.notify_transport_closed()
            await self._flush_effects()
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
                    self._engine.queue_ping()
                    # A lost PINGREQ beats a wedged keepalive under backpressure.
                    try:
                        await self._flush_effects(nowait=True)
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
                await self._force_close(preserve_reconnect=True)
                try:
                    await self._connect_once(
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

    async def _flush_effects(self, *, nowait: bool = False) -> None:
        effects = self._engine.take_effects()
        # Protocol bytes first (PUBACK/PUBREC/…), then app delivery. Keeps the
        # wire moving even if the message queue or user callback blocks.
        for effect in effects:
            if effect.kind is EffectKind.SEND:
                await self._enqueue_outbound(effect.data, nowait=nowait)
        for effect in effects:
            kind = effect.kind
            if kind is EffectKind.SEND:
                continue
            elif kind is EffectKind.CONNACK:
                connack: ConnAckPacket = effect.data
                if self._connack_fut is not None and not self._connack_fut.done():
                    self._connack_fut.set_result(connack)
                if self.on_connect is not None:
                    # Schedule independently: an on_connect that awaits
                    # subscribe()/publish() must not block the reader.
                    asyncio.create_task(self._invoke(self.on_connect, connack))
            elif kind is EffectKind.AUTH:
                challenge: AuthPacket = effect.data
                if self.auth_handler is None:
                    # Should not happen when accept_auth is False (engine rejects).
                    await self._enqueue_outbound(
                        encode_disconnect(0x8C, self._engine.config.protocol),
                        nowait=nowait,
                    )
                    continue
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
                    # Schedule independently so awaiting a receipt inside a
                    # callback cannot deadlock the reader.
                    asyncio.create_task(self._invoke(self.on_message, msg))
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
                        # Broker ended the session — close proactively so the
                        # reader exits and reconnect/cleanup can proceed.
                        try:
                            await self._transport.close()
                        except Exception:
                            pass
                continue
            elif kind is EffectKind.PROTOCOL_ERROR:
                raise ProtocolError(str(effect.data))
            else:
                never: Never = kind
                raise MQTTError(f"Unhandled effect {never!r}")

    def _fail_pending(self, exc: BaseException) -> None:
        for receipt in self._receipts.values():
            receipt._error = exc
            if receipt._event is not None:
                receipt._event.set()
        self._receipts.clear()
        for fut in self._sub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._sub_futs.clear()
        for fut in self._unsub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._unsub_futs.clear()

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
        for task in tasks:
            if task is not None and task is not current:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._reader_task is not current:
            self._reader_task = None
        if self._writer_task is not current:
            self._writer_task = None
        if self._keepalive_task is not current:
            self._keepalive_task = None
        if not preserve_reconnect and self._reconnect_task is not current:
            self._reconnect_task = None
        if self._transport is not None:
            await self._transport.close()
            self._transport = None
        self._closed.set()
