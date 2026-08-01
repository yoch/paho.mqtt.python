"""MQTT Variable Byte Integer encode/decode."""

from __future__ import annotations

from mqttnext.errors import MalformedPacketError

_MAX_VBI = 268_435_455


def encode_vbi(value: int) -> bytes:
    if not 0 <= value <= _MAX_VBI:
        raise ValueError(f"VBI out of range: {value}")
    out = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value > 0:
            digit |= 0x80
        out.append(digit)
        if value == 0:
            break
    return bytes(out)


def decode_vbi(buffer: bytes | bytearray | memoryview, offset: int = 0) -> tuple[int, int]:
    """Decode a VBI starting at *offset*.

    Returns ``(value, new_offset)``.
    """
    multiplier = 1
    value = 0
    encoded_bytes = 0
    length = len(buffer)
    pos = offset
    while True:
        if pos >= length:
            raise MalformedPacketError("Incomplete Variable Byte Integer")
        encoded_bytes += 1
        if encoded_bytes > 4:
            raise MalformedPacketError("Malformed Variable Byte Integer (too long)")
        byte = buffer[pos]
        pos += 1
        value += (byte & 0x7F) * multiplier
        if byte & 0x80 == 0:
            break
        multiplier *= 128
        if multiplier > 128 * 128 * 128:
            raise MalformedPacketError("Malformed Variable Byte Integer")
    if value > _MAX_VBI:
        raise MalformedPacketError("Variable Byte Integer exceeds maximum")
    return value, pos


def vbi_len(value: int) -> int:
    if value < 128:
        return 1
    if value < 16_384:
        return 2
    if value < 2_097_152:
        return 3
    if value <= _MAX_VBI:
        return 4
    raise ValueError(f"VBI out of range: {value}")
