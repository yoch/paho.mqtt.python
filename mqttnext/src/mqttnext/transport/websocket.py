"""WebSocket transport for MQTT (binary frames, MQTT subprotocol)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import struct
from typing import Any
from urllib.parse import urlparse

_MAX_HANDSHAKE_BYTES = 64 * 1024
_MAX_CONTROL_PAYLOAD = 125
_MAX_PENDING_CONTROL = 16


class WebSocketTransport:
    """Minimal MQTT-over-WebSocket client transport (RFC 6455 binary frames)."""

    __slots__ = (
        "_reader",
        "_writer",
        "_recv_buf",
        "_closing",
        "_pending_control",
        "_max_frame_size",
        "_fragment",
    )

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        max_frame_size: int = 16 * 1024 * 1024,
    ) -> None:
        if max_frame_size <= 0:
            raise ValueError("max_frame_size must be positive")
        self._reader = reader
        self._writer = writer
        self._recv_buf = bytearray()
        self._closing = False
        self._pending_control: list[bytes] = []
        self._max_frame_size = max_frame_size
        # Reassembled fragmented binary message (FIN=0 sequence).
        self._fragment: bytearray | None = None

    @classmethod
    async def connect(
        cls,
        url: str,
        *,
        ssl: Any = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        max_frame_size: int = 16 * 1024 * 1024,
    ) -> WebSocketTransport:
        parsed = urlparse(url)
        if parsed.scheme not in ("ws", "wss"):
            raise ValueError(f"Unsupported WebSocket URL scheme: {parsed.scheme}")
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        if parsed.scheme == "wss" and ssl is False:
            raise ValueError("wss:// requires TLS (ssl=False would downgrade silently)")
        use_ssl = ssl if ssl is not None else (True if parsed.scheme == "wss" else None)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=use_ssl), timeout=timeout
        )
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
                if "\r" in k or "\n" in k or "\r" in v or "\n" in v:
                    raise ValueError("extra_headers must not contain CR/LF")
                headers.append(f"{k}: {v}")
        writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
        await writer.drain()
        # Read HTTP response headers (bounded).
        header_buf = b""
        while b"\r\n\r\n" not in header_buf:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
            if not chunk:
                raise ConnectionError("WebSocket handshake closed early")
            header_buf += chunk
            if len(header_buf) > _MAX_HANDSHAKE_BYTES:
                writer.close()
                raise ConnectionError("WebSocket handshake headers too large")
        head, _, leftover = header_buf.partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        status_line = lines[0].decode("ascii", errors="replace")
        parts = status_line.split(" ", 2)
        if len(parts) < 2 or parts[1] != "101":
            writer.close()
            raise ConnectionError(f"WebSocket handshake failed: {status_line}")
        headers_map: dict[str, str] = {}
        for header_line_bytes in lines[1:]:
            if b":" in header_line_bytes:
                raw_name, _, raw_value = header_line_bytes.partition(b":")
                headers_map[raw_name.decode("latin1").strip().lower()] = (
                    raw_value.decode("latin1").strip()
                )
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode("ascii")
        if headers_map.get("sec-websocket-accept") != expected:
            writer.close()
            raise ConnectionError("WebSocket accept key mismatch")
        if headers_map.get("upgrade", "").lower() != "websocket":
            writer.close()
            raise ConnectionError("WebSocket handshake missing Upgrade: websocket")
        connection_tokens = {
            token.strip().lower()
            for token in headers_map.get("connection", "").split(",")
            if token.strip()
        }
        if "upgrade" not in connection_tokens:
            writer.close()
            raise ConnectionError("WebSocket handshake missing Connection: Upgrade")
        if headers_map.get("sec-websocket-protocol", "").lower() != "mqtt":
            writer.close()
            raise ConnectionError("WebSocket subprotocol 'mqtt' not negotiated")
        transport = cls(reader, writer, max_frame_size=max_frame_size)
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
            if self._pending_control:
                # RFC 6455 requires a pong as soon as practical. Flush it before
                # waiting for any more network or application traffic.
                await self._flush_control()
                if payload is None:
                    continue
            if payload is not None:
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
        """Extract the next binary MQTT payload and process control frames."""
        while True:
            parsed = _parse_frame(
                self._recv_buf,
                self._max_frame_size,
                expect_masked=False,
            )
            if parsed is None:
                return None
            fin, opcode, raw = parsed
            if opcode == 0x8:  # close
                self._closing = True
                return b""
            if opcode == 0x9:  # ping → immediate pong on the next read-loop turn
                if len(self._pending_control) >= _MAX_PENDING_CONTROL:
                    raise ConnectionError("Too many pending WebSocket control replies")
                self._pending_control.append(_mask_client_frame(0xA, raw))
                return None
            if opcode == 0xA:  # pong — ignore
                continue
            if opcode == 0x2:
                if self._fragment is not None:
                    raise ConnectionError(
                        "WebSocket binary frame started before fragmented message completed"
                    )
                if not fin:
                    self._fragment = bytearray(raw)
                    continue
                return raw
            if opcode == 0x0:  # continuation
                if self._fragment is None:
                    raise ConnectionError("WebSocket continuation without start frame")
                self._fragment.extend(raw)
                if len(self._fragment) > self._max_frame_size:
                    raise ConnectionError("WebSocket fragmented message too large")
                if fin:
                    payload = bytes(self._fragment)
                    self._fragment = None
                    return payload
                continue
            # _parse_frame rejects every non-MQTT application opcode.
            raise AssertionError(f"unreachable WebSocket opcode {opcode}")


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


def _parse_frame(
    buf: bytearray,
    max_frame_size: int,
    *,
    expect_masked: bool | None = None,
) -> tuple[bool, int, bytes] | None:
    """Consume one RFC 6455 frame and return ``(fin, opcode, payload)``.

    ``expect_masked=False`` is used for server→client frames and rejects masked
    server frames. ``expect_masked=True`` is useful for server-side tests parsing
    client frames. ``None`` accepts either direction for low-level fuzzing only.
    """
    if len(buf) < 2:
        return None
    b0 = buf[0]
    b1 = buf[1]
    if b0 & 0x70:
        raise ConnectionError("WebSocket RSV bits set without negotiated extension")
    fin = bool(b0 & 0x80)
    masked = bool(b1 & 0x80)
    if expect_masked is not None and masked is not expect_masked:
        direction = "masked" if expect_masked else "unmasked"
        raise ConnectionError(f"Expected {direction} WebSocket frame")

    opcode = b0 & 0x0F
    if opcode not in (0x0, 0x2, 0x8, 0x9, 0xA):
        if opcode == 0x1:
            raise ConnectionError("MQTT over WebSocket requires binary frames")
        raise ConnectionError(f"Unsupported WebSocket opcode 0x{opcode:x}")

    ln = b1 & 0x7F
    pos = 2
    if ln == 126:
        if len(buf) < 4:
            return None
        ln = struct.unpack_from("!H", buf, 2)[0]
        if ln < 126:
            raise ConnectionError("Non-canonical WebSocket frame length")
        pos = 4
    elif ln == 127:
        if len(buf) < 10:
            return None
        ln = struct.unpack_from("!Q", buf, 2)[0]
        if ln & (1 << 63):
            raise ConnectionError("Invalid 64-bit WebSocket frame length (MSB set)")
        if ln < 65536:
            raise ConnectionError("Non-canonical WebSocket frame length")
        pos = 10
    if ln > max_frame_size:
        raise ConnectionError(f"WebSocket frame {ln} exceeds max {max_frame_size}")
    if opcode in (0x8, 0x9, 0xA):
        if ln > _MAX_CONTROL_PAYLOAD:
            raise ConnectionError("WebSocket control frame payload too large")
        if not fin:
            raise ConnectionError("WebSocket control frame must not be fragmented")
        if opcode == 0x8 and ln == 1:
            raise ConnectionError("WebSocket close frame payload must not be one byte")

    mask_len = 4 if masked else 0
    total = pos + mask_len + ln
    if len(buf) < total:
        return None
    mask = bytes(buf[pos : pos + mask_len]) if masked else b""
    start = pos + mask_len
    raw = bytes(buf[start:total])
    del buf[:total]
    if masked:
        raw = bytes(b ^ mask[i % 4] for i, b in enumerate(raw))
    return fin, opcode, raw
