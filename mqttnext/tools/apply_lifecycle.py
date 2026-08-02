from __future__ import annotations

from pathlib import Path


TARGET = Path("mqttnext/src/mqttnext/api/async_client.py")
TEST_TARGET = Path("mqttnext/tests/unit/test_async_lifecycle.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


text = TARGET.read_text()

text = replace_once(
    text,
    """        self._keepalive_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._outbound: asyncio.Queue[WriteItem] = asyncio.Queue()
""",
    """        self._keepalive_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._outbound: asyncio.Queue[WriteItem] = asyncio.Queue()
""",
    "lifecycle lock",
)

text = replace_once(
    text,
    """        self._host = host
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
""",
    """        async with self._lifecycle_lock:
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
""",
    "TCP connect serialization",
)

text = replace_once(
    text,
    """        self._unix_path = path
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
""",
    """        async with self._lifecycle_lock:
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
""",
    "Unix connect serialization",
)

text = replace_once(
    text,
    """        self._ws_url = url
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
""",
    """        async with self._lifecycle_lock:
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
""",
    "WebSocket connect serialization",
)

old_connect_once = """    async def _connect_once(
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
"""
new_connect_once = """    async def _connect_once_locked(
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
"""
text = replace_once(text, old_connect_once, new_connect_once, "connect attempt cleanup")

text = replace_once(
    text,
    """    async def disconnect(self, reason_code: int = 0) -> None:
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
""",
    """    async def disconnect(self, reason_code: int = 0) -> None:
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
""",
    "disconnect serialization",
)

text = replace_once(
    text,
    """                await asyncio.sleep(delay)
                await self._force_close(preserve_reconnect=True)
                try:
                    await self._connect_once(
                        self._host,
                        self._port,
                        ssl=self._ssl,
                        timeout=self._reconnect.connect_timeout,
                    )
""",
    """                await asyncio.sleep(delay)
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
""",
    "reconnect serialization",
)

text = replace_once(
    text,
    """                try:
                    await task
                except asyncio.CancelledError:
                    pass
""",
    """                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
""",
    "task cleanup",
)

text = replace_once(
    text,
    """        if self._transport is not None:
            await self._transport.close()
            self._transport = None
""",
    """        if self._transport is not None:
            try:
                await self._transport.close()
            except Exception:
                pass
            self._transport = None
""",
    "transport cleanup",
)

TARGET.write_text(text)

TEST_TARGET.write_text(
    '''"""AsyncClient lifecycle serialization and cancellation cleanup."""

from __future__ import annotations

import asyncio

import pytest

from mqttnext.api.async_client import AsyncClient
from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.enums import ConnectionState, PacketType
from mqttnext.errors import ProtocolError
from mqttnext.packets import encode_frame
from mqttnext.protocol.reconnect import ReconnectPolicy


class _Transport:
    def __init__(self, *, connack: bool) -> None:
        self._rx: asyncio.Queue[bytes] = asyncio.Queue()
        self._decoder = IncrementalDecoder()
        self._connack = connack
        self._closing = False
        self.connect_written = asyncio.Event()

    async def write(self, data: bytes) -> None:
        self._decoder.feed(data)
        for raw in self._decoder.drain_packets():
            if raw.packet_type is PacketType.CONNECT:
                self.connect_written.set()
                if self._connack:
                    self._rx.put_nowait(
                        encode_frame(PacketType.CONNACK, 0, b"\\x00\\x00")
                    )

    async def read(self, n: int = 65536) -> bytes:
        return await self._rx.get()

    async def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._rx.put_nowait(b"")

    def is_closing(self) -> bool:
        return self._closing


async def test_concurrent_connects_open_one_transport() -> None:
    client = AsyncClient(client_id="lifecycle")
    release_factory = asyncio.Event()
    factory_entered = asyncio.Event()
    calls = 0
    transport = _Transport(connack=True)

    async def factory(host: str, port: int, *, ssl: object = None) -> _Transport:
        nonlocal calls
        calls += 1
        factory_entered.set()
        await release_factory.wait()
        return transport

    client._transport_factory = factory
    first = asyncio.create_task(client.connect("fake", timeout=2.0))
    await factory_entered.wait()
    second = asyncio.create_task(client.connect("fake", timeout=2.0))
    await asyncio.sleep(0)
    assert calls == 1

    release_factory.set()
    await first
    with pytest.raises(ProtocolError, match="Already connected"):
        await second
    assert calls == 1
    assert client.is_connected
    await client.disconnect()


async def test_cancelled_connect_closes_transport_and_tasks() -> None:
    reconnect = ReconnectPolicy(enabled=True, min_delay=0.01, max_delay=0.01)
    client = AsyncClient(client_id="cancel-connect", reconnect=reconnect)
    transport = _Transport(connack=False)
    calls = 0

    async def factory(host: str, port: int, *, ssl: object = None) -> _Transport:
        nonlocal calls
        calls += 1
        return transport

    client._transport_factory = factory
    task = asyncio.create_task(client.connect("fake", timeout=30.0))
    await asyncio.wait_for(transport.connect_written.wait(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.05)

    assert calls == 1
    assert transport.is_closing()
    assert client._transport is None
    assert client._reader_task is None
    assert client._writer_task is None
    assert client._keepalive_task is None
    assert client._reconnect_task is None
    assert client.state is ConnectionState.DISCONNECTED


async def test_disconnect_waits_for_in_progress_connect_without_overlap() -> None:
    client = AsyncClient(client_id="connect-disconnect")
    release_factory = asyncio.Event()
    factory_entered = asyncio.Event()
    transport = _Transport(connack=True)

    async def factory(host: str, port: int, *, ssl: object = None) -> _Transport:
        factory_entered.set()
        await release_factory.wait()
        return transport

    client._transport_factory = factory
    connecting = asyncio.create_task(client.connect("fake", timeout=2.0))
    await factory_entered.wait()
    disconnecting = asyncio.create_task(client.disconnect())
    await asyncio.sleep(0)
    assert not disconnecting.done()

    release_factory.set()
    await connecting
    await disconnecting
    assert transport.is_closing()
    assert client._transport is None
    assert client.state is ConnectionState.DISCONNECTED
'''
)
