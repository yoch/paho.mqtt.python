"""WebSocket transport for MQTT (binary frames, MQTT subprotocol)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import struct
from typing import Any
from urllib.parse import urlparse


class WebSocketTransport:
    """Minimal MQTT-over-WebSocket client transport (RFC 6455 binary frames)."""

    __slots__ = ("_reader", "_writer", "_recv_buf", "_closing", "_pending_control")

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer
        self._recv_buf = bytearray()
        self._closing = False
        # Control payloads to write (pong) before the next application write.
        self._pending_control: list[bytes] = []

    @classmethod
    async def connect(
        cls,
        url: str,
        *,
        ssl: Any = None,
        extra_headers: dict[str, str] | None = None,
    ) -> WebSocketTransport:
        parsed = urlparse(url)
        if parsed.scheme not in ("ws", "wss"):
            raise ValueError(f"Unsupported WebSocket URL scheme: {parsed.scheme}")
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        use_ssl = ssl if ssl is not None else (True if parsed.scheme == "wss" else None)
        reader, writer = await asyncio.open_connection(host, port, ssl=use_ssl)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        headers = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
            "Sec-WebSocket-Protocol: mqtt",
        ]
        if extra_headers:
            for k, v in extra_headers.items():
                headers.append(f"{k}: {v}")
        writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
        await writer.drain()
        # Read HTTP response headers.
        header_buf = b""
        while b"\r\n\r\n" not in header_buf:
            chunk = await reader.read(4096)
            if not chunk:
                raise ConnectionError("WebSocket handshake closed early")
            header_buf += chunk
        status_line = header_buf.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        if "101" not in status_line:
            writer.close()
            raise ConnectionError(f"WebSocket handshake failed: {status_line}")
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode("ascii")
        if expected not in header_buf.decode("latin1", errors="replace"):
            writer.close()
            raise ConnectionError("WebSocket accept key mismatch")
        transport = cls(reader, writer)
        # Any bytes after headers belong to the WS stream.
        leftover = header_buf.split(b"\r\n\r\n", 1)[1]
        if leftover:
            transport._recv_buf.extend(leftover)
        return transport

    async def write(self, data: bytes) -> None:
        await self._flush_control()
        frame = _mask_client_frame(0x2, data)  # binary
        self._writer.write(frame)
        if self._writer.transport.get_write_buffer_size() > 64 * 1024:
            await self._writer.drain()

    async def write_many(self, parts: list[bytes]) -> None:
        if not parts:
            return
        await self._flush_control()
        # One binary frame per MQTT chunk keeps framing simple and correct.
        frames = [_mask_client_frame(0x2, p) for p in parts]
        self._writer.writelines(frames)
        if self._writer.transport.get_write_buffer_size() > 64 * 1024:
            await self._writer.drain()

    async def drain(self) -> None:
        await self._writer.drain()

    async def read(self, n: int = 65536) -> bytes:
        while True:
            payload = self._try_extract_application_payload()
            if payload is not None:
                if self._pending_control:
                    await self._flush_control()
                return payload
            chunk = await self._reader.read(n)
            if not chunk:
                self._closing = True
                return b""
            self._recv_buf.extend(chunk)

    async def close(self) -> None:
        self._closing = True
        try:
            self._writer.write(_mask_client_frame(0x8, b""))  # close
            await self._writer.drain()
        except Exception:
            pass
        self._writer.close()
        try:
            await self._writer.wait_closed()
        except Exception:
            pass

    def is_closing(self) -> bool:
        return self._closing or self._writer.is_closing()

    async def _flush_control(self) -> None:
        if not self._pending_control:
            return
        self._writer.writelines(self._pending_control)
        self._pending_control.clear()
        if self._writer.transport.get_write_buffer_size() > 64 * 1024:
            await self._writer.drain()

    def _try_extract_application_payload(self) -> bytes | None:
        """Extract next binary MQTT payload; queue pong replies for ping frames."""
        while True:
            parsed = _parse_frame(self._recv_buf)
            if parsed is None:
                return None
            opcode, raw = parsed
            if opcode == 0x8:  # close
                return b""
            if opcode == 0x9:  # ping → pong
                self._pending_control.append(_mask_client_frame(0xA, raw))
                continue
            if opcode == 0xA:  # pong — ignore
                continue
            if opcode != 0x2:
                continue
            return raw


def _mask_client_frame(opcode: int, payload: bytes) -> bytes:
    mask = os.urandom(4)
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    ln = len(payload)
    if ln < 126:
        header.append(0x80 | ln)
    elif ln < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", ln))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", ln))
    header.extend(mask)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return bytes(header) + masked


def _parse_frame(buf: bytearray) -> tuple[int, bytes] | None:
    """Consume one WebSocket frame from *buf*; return (opcode, payload) or None."""
    if len(buf) < 2:
        return None
    b1 = buf[1]
    masked = bool(b1 & 0x80)
    ln = b1 & 0x7F
    pos = 2
    if ln == 126:
        if len(buf) < 4:
            return None
        ln = struct.unpack_from("!H", buf, 2)[0]
        pos = 4
    elif ln == 127:
        if len(buf) < 10:
            return None
        ln = struct.unpack_from("!Q", buf, 2)[0]
        pos = 10
    mask_len = 4 if masked else 0
    total = pos + mask_len + ln
    if len(buf) < total:
        return None
    opcode = buf[0] & 0x0F
    mask = bytes(buf[pos : pos + mask_len]) if masked else b""
    start = pos + mask_len
    raw = bytes(buf[start:total])
    del buf[:total]
    if masked:
        raw = bytes(b ^ mask[i % 4] for i, b in enumerate(raw))
    return opcode, raw
