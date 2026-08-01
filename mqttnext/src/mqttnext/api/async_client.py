"""Async-native MQTT client (phase 0 skeleton).

Owns the transport + IncrementalDecoder + ProtocolEngine loop. User callbacks
are optional and invoked outside the engine's synchronous critical section.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Never

from mqttnext.api.models import PublishReceipt
from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.enums import ConnectionState, MQTTProtocolVersion, QoS
from mqttnext.errors import MQTTError, NotConnectedError, ProtocolError
from mqttnext.packets import ConnAckPacket
from mqttnext.protocol.engine import EffectKind, EngineConfig, ProtocolEngine
from mqttnext.transport.tcp import AsyncTransport, TcpTransport
from mqttnext.types import Message, Properties

OnMessage = Callable[[Message], Any]
OnConnect = Callable[[ConnAckPacket], Any]
OnDisconnect = Callable[[], Any]


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
        local_receive_maximum: int = 20,
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
            )
        )
        self._decoder = IncrementalDecoder()
        self._transport: AsyncTransport | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._connack_fut: asyncio.Future[ConnAckPacket] | None = None
        self._receipts: dict[int, PublishReceipt] = {}
        self._messages: asyncio.Queue[Message] = asyncio.Queue()
        self._closed = asyncio.Event()

        self.on_message: OnMessage | None = None
        self.on_connect: OnConnect | None = None
        self.on_disconnect: OnDisconnect | None = None

    @property
    def state(self) -> ConnectionState:
        return self._engine.state

    @property
    def is_connected(self) -> bool:
        return self._engine.state == ConnectionState.CONNECTED

    async def connect(
        self,
        host: str,
        port: int = 1883,
        *,
        ssl: Any = None,
        timeout: float = 30.0,
    ) -> ConnAckPacket:
        if self.is_connected:
            raise ProtocolError("Already connected")
        transport = await TcpTransport.connect(host, port, ssl=ssl)
        self._transport = transport
        self._closed.clear()
        self._decoder.clear()
        connect_packet = self._engine.begin_connect()
        loop = asyncio.get_running_loop()
        self._connack_fut = loop.create_future()
        await transport.write(connect_packet)
        self._reader_task = asyncio.create_task(self._read_loop(), name="mqttnext-reader")
        try:
            connack = await asyncio.wait_for(self._connack_fut, timeout=timeout)
        except Exception:
            await self._force_close()
            raise
        if connack.reason_code != 0:
            await self._force_close()
            raise ProtocolError(f"Connection refused: reason_code={connack.reason_code}")
        return connack

    async def disconnect(self, reason_code: int = 0) -> None:
        if self._transport is None:
            return
        packet = self._engine.begin_disconnect(reason_code)
        try:
            await self._transport.write(packet)
        finally:
            await self._force_close()

    async def publish(
        self,
        topic: str,
        payload: bytes | str = b"",
        *,
        qos: int | QoS = 0,
        retain: bool = False,
        properties: Properties | None = None,
    ) -> PublishReceipt:
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        handle = self._engine.queue_publish(
            topic,
            data,
            qos=qos,
            retain=retain,
            properties=properties,
        )
        await self._flush_effects()
        event = asyncio.Event()
        if handle.qos == QoS.AT_MOST_ONCE:
            event.set()
            return PublishReceipt(mid=None, qos=handle.qos, _event=event)
        assert handle.mid is not None
        receipt = PublishReceipt(mid=handle.mid, qos=handle.qos, _event=event)
        self._receipts[handle.mid] = receipt
        return receipt

    async def subscribe(self, topic: str, qos: int | QoS = 0) -> int:
        mid = self._engine.queue_subscribe(topic, qos=qos)
        await self._flush_effects()
        return mid

    async def unsubscribe(self, topic: str) -> int:
        mid = self._engine.queue_unsubscribe(topic)
        await self._flush_effects()
        return mid

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            if self._closed.is_set() and self._messages.empty():
                return
            try:
                msg = await asyncio.wait_for(self._messages.get(), timeout=0.5)
            except TimeoutError:
                if self._closed.is_set():
                    return
                continue
            yield msg

    async def _read_loop(self) -> None:
        assert self._transport is not None
        try:
            while not self._transport.is_closing():
                data = await self._transport.read(65536)
                if not data:
                    break
                self._decoder.feed(data)
                for raw in self._decoder.drain_packets():
                    self._engine.handle_raw(raw)
                    await self._flush_effects()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            for receipt in self._receipts.values():
                receipt._error = exc
                receipt._event.set()
            self._receipts.clear()
        finally:
            self._engine.notify_transport_closed()
            await self._flush_effects()
            self._closed.set()

    async def _flush_effects(self) -> None:
        effects = self._engine.take_effects()
        for effect in effects:
            kind = effect.kind
            if kind is EffectKind.SEND:
                if self._transport is None:
                    raise NotConnectedError("No transport for SEND effect")
                await self._transport.write(effect.data)
            elif kind is EffectKind.MESSAGE:
                msg: Message = effect.data
                await self._messages.put(msg)
                await self._invoke(self.on_message, msg)
            elif kind is EffectKind.CONNACK:
                connack: ConnAckPacket = effect.data
                if self._connack_fut is not None and not self._connack_fut.done():
                    self._connack_fut.set_result(connack)
                await self._invoke(self.on_connect, connack)
            elif kind is EffectKind.PUBLISH_COMPLETE:
                mid: int = effect.data
                receipt = self._receipts.pop(mid, None)
                if receipt is not None:
                    receipt._event.set()
            elif kind is EffectKind.DISCONNECTED:
                await self._invoke(self.on_disconnect)
            elif kind is EffectKind.PROTOCOL_ERROR:
                raise ProtocolError(str(effect.data))
            elif kind is EffectKind.SUBACK or kind is EffectKind.UNSUBACK:
                continue
            else:
                never: Never = kind
                raise MQTTError(f"Unhandled effect {never!r}")

    async def _invoke(self, callback: Callable[..., Any] | None, *args: Any) -> None:
        if callback is None:
            return
        result = callback(*args)
        if isinstance(result, Awaitable):
            await result

    async def _force_close(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._transport is not None:
            await self._transport.close()
            self._transport = None
        self._closed.set()
