"""Async transport abstractions."""

from __future__ import annotations

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
        import asyncio

        reader, writer = await asyncio.open_connection(host, port, ssl=ssl)
        return cls(reader, writer)

    async def write(self, data: bytes) -> None:
        self._writer.write(data)  # type: ignore[attr-defined]
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
