"""WebSocket transport unit tests (handshake + ping/pong + binary MQTT)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import struct

import pytest

from mqttnext.transport.websocket import WebSocketTransport, _mask_client_frame, _parse_frame


def _server_accept(key: str) -> str:
    return base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
    ).decode("ascii")


def _unmask_server_frame(opcode: int, payload: bytes) -> bytes:
    """Server→client frames are typically unmasked."""
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    ln = len(payload)
    if ln < 126:
        header.append(ln)
    elif ln < 65536:
        header.append(126)
        header.extend(struct.pack("!H", ln))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", ln))
    return bytes(header) + payload


@pytest.mark.asyncio
async def test_websocket_binary_roundtrip_and_pong() -> None:
    loop = asyncio.get_running_loop()
    got_mqtt = loop.create_future()
    got_pong = loop.create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = await reader.read(4096)
            if not chunk:
                return
            req += chunk
        key_line = next(
            line for line in req.decode("latin1").split("\r\n") if line.lower().startswith("sec-websocket-key:")
        )
        key = key_line.split(":", 1)[1].strip()
        accept = _server_accept(key)
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "Sec-WebSocket-Protocol: mqtt\r\n"
            "\r\n"
        )
        writer.write(resp.encode("ascii"))
        await writer.drain()
        # Send a ping then a binary MQTT-looking payload.
        writer.write(_unmask_server_frame(0x9, b"ping-payload"))
        writer.write(_unmask_server_frame(0x2, b"\x30\x02\x00\x00"))  # tiny PUBLISH-ish
        await writer.drain()
        # Read client frames: pong then maybe close.
        buf = bytearray()
        while not (got_pong.done() and got_mqtt.done()):
            chunk = await reader.read(4096)
            if not chunk:
                break
            buf.extend(chunk)
            while True:
                parsed = _parse_frame(buf, 16 * 1024 * 1024)
                if parsed is None:
                    break
                fin, opcode, payload = parsed
                if opcode == 0xA and not got_pong.done():
                    got_pong.set_result(payload)
                if opcode == 0x2 and not got_mqtt.done():
                    got_mqtt.set_result(payload)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]
    try:
        transport = await WebSocketTransport.connect(f"ws://{host}:{port}/mqtt")
        data = await transport.read()
        assert data == b"\x30\x02\x00\x00"
        await transport.write(b"\x10\x00")  # dummy CONNECT fragment
        assert await asyncio.wait_for(got_pong, timeout=2.0) == b"ping-payload"
        assert await asyncio.wait_for(got_mqtt, timeout=2.0) == b"\x10\x00"
        await transport.close()
    finally:
        server.close()
        await server.wait_closed()


def test_mask_frame_roundtrip_parse() -> None:
    frame = _mask_client_frame(0x2, b"abc")
    buf = bytearray(frame)
    fin, opcode, payload = _parse_frame(buf, 16 * 1024 * 1024)
    assert fin is True
    assert opcode == 0x2
    assert payload == b"abc"
    assert buf == b""
