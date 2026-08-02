"""Async transport abstractions."""

from __future__ import annotations

import asyncio
import socket
from typing import Protocol


class AsyncTransport(Protocol):
    async def write(self, data: bytes) -> None: ...
    async def read(self, n: int = 65536) -> bytes: ...
    async def close(self) -> None: ...
    def is_closing(self) -> bool: ...


class TcpTransport:
    """Thin asyncio StreamReader/StreamWriter wrapper with write drain."""

    __slots__ = ("_reader", "_writer")

    def __init__(self, reader: object, writer: object) -> None:
        self._reader = reader
        self._writer = writer

    @classmethod
    async def connect(
        cls,
        host: str,
        port: int,
        *,
        ssl: object | None = None,
    ) -> TcpTransport:
        reader, writer = await asyncio.open_connection(host, port, ssl=ssl)
        sock = writer.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
        return cls(reader, writer)

    async def write(self, data: bytes) -> None:
        self._writer.write(data)  # type: ignore[attr-defined]
        # Avoid awaiting drain on every small packet: it serializes the
        # event loop against socket buffer flushes and kills QoS pipelining.
        transport = self._writer.transport  # type: ignore[attr-defined]
        if transport is not None and transport.get_write_buffer_size() > 64 * 1024:
            await self._writer.drain()  # type: ignore[attr-defined]

    async def write_many(self, parts: list[bytes]) -> None:
        """Coalesce multiple small frames into one writelines + single buffer check."""
        if not parts:
            return
        if len(parts) == 1:
            await self.write(parts[0])
            return
        writer = self._writer
        writer.writelines(parts)  # type: ignore[attr-defined]
        transport = writer.transport  # type: ignore[attr-defined]
        if transport is not None and transport.get_write_buffer_size() > 64 * 1024:
            await writer.drain()  # type: ignore[attr-defined]

    async def drain(self) -> None:
        await self._writer.drain()  # type: ignore[attr-defined]

    async def read(self, n: int = 65536) -> bytes:
        return await self._reader.read(n)  # type: ignore[attr-defined]

    async def close(self) -> None:
        self._writer.close()  # type: ignore[attr-defined]
        try:
            await self._writer.wait_closed()  # type: ignore[attr-defined]
        except Exception:
            pass

    def is_closing(self) -> bool:
        return bool(self._writer.is_closing())  # type: ignore[attr-defined]
