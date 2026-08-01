"""Binary primitives used by MQTT codecs."""

from __future__ import annotations

import struct
from typing import Final

from mqttnext.errors import MalformedPacketError

_U16: Final = struct.Struct("!H")
_U32: Final = struct.Struct("!I")


def pack_u16(value: int) -> bytes:
    return _U16.pack(value)


def unpack_u16(buffer: bytes | bytearray | memoryview, offset: int = 0) -> tuple[int, int]:
    if offset + 2 > len(buffer):
        raise MalformedPacketError("Incomplete uint16")
    return _U16.unpack_from(buffer, offset)[0], offset + 2


def pack_u32(value: int) -> bytes:
    return _U32.pack(value)


def unpack_u32(buffer: bytes | bytearray | memoryview, offset: int = 0) -> tuple[int, int]:
    if offset + 4 > len(buffer):
        raise MalformedPacketError("Incomplete uint32")
    return _U32.unpack_from(buffer, offset)[0], offset + 4


def pack_utf8(value: str | bytes) -> bytes:
    data = value.encode("utf-8") if isinstance(value, str) else value
    if len(data) > 65535:
        raise ValueError("UTF-8 string too long for MQTT")
    return _U16.pack(len(data)) + data


def unpack_utf8(buffer: bytes | bytearray | memoryview, offset: int = 0) -> tuple[str, int]:
    length, pos = unpack_u16(buffer, offset)
    end = pos + length
    if end > len(buffer):
        raise MalformedPacketError("Incomplete UTF-8 string")
    raw = bytes(buffer[pos:end])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedPacketError("Invalid UTF-8 data") from exc
    _validate_mqtt_utf8(text)
    return text, end


def pack_binary(value: bytes) -> bytes:
    if len(value) > 65535:
        raise ValueError("Binary data too long for MQTT")
    return _U16.pack(len(value)) + value


def unpack_binary(buffer: bytes | bytearray | memoryview, offset: int = 0) -> tuple[bytes, int]:
    length, pos = unpack_u16(buffer, offset)
    end = pos + length
    if end > len(buffer):
        raise MalformedPacketError("Incomplete binary data")
    return bytes(buffer[pos:end]), end


def _validate_mqtt_utf8(text: str) -> None:
    for ch in text:
        code = ord(ch)
        if code == 0x00:
            raise MalformedPacketError("[MQTT-1.5.4-2] Null in UTF-8 data")
        if 0xD800 <= code <= 0xDFFF:
            raise MalformedPacketError("[MQTT-1.5.4-1] Surrogate in UTF-8 data")
        if code == 0xFEFF:
            raise MalformedPacketError("[MQTT-1.5.4-3] U+FEFF in UTF-8 data")
