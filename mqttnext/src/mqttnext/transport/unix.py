"""Unix domain socket transport for MQTT."""

from __future__ import annotations

import asyncio


class UnixSocketTransport:
    """asyncio StreamReader/StreamWriter over an AF_UNIX socket."""

    __slots__ = ("_reader", "_writer")

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer

    @classmethod
    async def connect(cls, path: str) -> UnixSocketTransport:
        reader, writer = await asyncio.open_unix_connection(path)
        return cls(reader, writer)

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        transport = self._writer.transport
        if transport is not None and transport.get_write_buffer_size() > 64 * 1024:
            await self._writer.drain()

    async def drain(self) -> None:
        await self._writer.drain()

    async def read(self, n: int = 65536) -> bytes:
        return await self._reader.read(n)

    async def close(self) -> None:
        self._writer.close()
        try:
            await self._writer.wait_closed()
        except Exception:
            pass

    def is_closing(self) -> bool:
        return bool(self._writer.is_closing())
