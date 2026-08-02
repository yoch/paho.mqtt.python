from __future__ import annotations

from pathlib import Path


PRIMITIVES = Path("mqttnext/src/mqttnext/codec/primitives.py")
PACKETS = Path("mqttnext/src/mqttnext/packets/__init__.py")
TOPICS = Path("mqttnext/src/mqttnext/topics.py")
TEST = Path("mqttnext/tests/unit/test_utf8_symmetry.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


primitives = PRIMITIVES.read_text()
primitives = replace_once(
    primitives,
    "from mqttnext.errors import MalformedPacketError\n",
    "from mqttnext.errors import MalformedPacketError, ProtocolError\n",
    "protocol error import",
)
primitives = replace_once(
    primitives,
    """def pack_utf8(value: str | bytes) -> bytes:
    data = value.encode("utf-8") if isinstance(value, str) else value
    if len(data) > 65535:
        raise ValueError("UTF-8 string too long for MQTT")
    return _U16.pack(len(data)) + data


def append_utf8(buf: bytearray, value: str | bytes) -> None:
    """Append MQTT UTF-8 string encoding into *buf* without intermediate concat."""
    data = value.encode("utf-8") if isinstance(value, str) else value
    if len(data) > 65535:
        raise ValueError("UTF-8 string too long for MQTT")
    buf += _U16.pack(len(data))
    buf += data
""",
    """def encode_utf8(value: str) -> bytes:
    """Validate and encode one MQTT UTF-8 string without its length prefix."""
    if not isinstance(value, str):
        raise ProtocolError(f"MQTT UTF-8 value must be str, got {type(value).__name__}")
    try:
        data = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ProtocolError("Invalid MQTT UTF-8 string") from exc
    _validate_mqtt_utf8(value, error_type=ProtocolError)
    if len(data) > 65535:
        raise ProtocolError("UTF-8 string too long for MQTT")
    return data


def pack_utf8(value: str) -> bytes:
    data = encode_utf8(value)
    return _U16.pack(len(data)) + data


def append_utf8(buf: bytearray, value: str) -> None:
    """Append MQTT UTF-8 string encoding into *buf* without intermediate concat."""
    data = encode_utf8(value)
    buf += _U16.pack(len(data))
    buf += data
""",
    "outbound utf8 encoding",
)
primitives = replace_once(
    primitives,
    """def _validate_mqtt_utf8(text: str) -> None:
""",
    """def _validate_mqtt_utf8(
    text: str,
    *,
    error_type: type[MalformedPacketError] | type[ProtocolError] = MalformedPacketError,
) -> None:
""",
    "utf8 validator signature",
)
primitives = primitives.replace(
    'raise MalformedPacketError("[MQTT-1.5.4-2] Null in UTF-8 data")',
    'raise error_type("[MQTT-1.5.4-2] Null in UTF-8 data")',
)
primitives = primitives.replace(
    'raise MalformedPacketError("[MQTT-1.5.4-1] Surrogate in UTF-8 data")',
    'raise error_type("[MQTT-1.5.4-1] Surrogate in UTF-8 data")',
)
primitives = primitives.replace(
    'raise MalformedPacketError("[MQTT-1.5.4-3] U+FEFF in UTF-8 data")',
    'raise error_type("[MQTT-1.5.4-3] U+FEFF in UTF-8 data")',
)
PRIMITIVES.write_text(primitives)

packets = PACKETS.read_text()
packets = replace_once(
    packets,
    "from mqttnext.codec.primitives import pack_utf8, pack_u16, unpack_utf8, unpack_u16\n",
    "from mqttnext.codec.primitives import encode_utf8, pack_utf8, pack_u16, unpack_utf8, unpack_u16\n",
    "packet encode_utf8 import",
)
packets = replace_once(
    packets,
    """        topic_bytes = self.topic.encode("utf-8")
        topic_len = len(topic_bytes)
        if topic_len > 65535:
            raise ValueError("UTF-8 string too long for MQTT")
""",
    """        topic_bytes = encode_utf8(self.topic)
        topic_len = len(topic_bytes)
""",
    "publish topic encoding",
)
PACKETS.write_text(packets)

topics = TOPICS.read_text()
topics = replace_once(
    topics,
    "from mqttnext.errors import MalformedPacketError, ProtocolError\n",
    "from mqttnext.codec.primitives import encode_utf8\nfrom mqttnext.errors import MalformedPacketError, ProtocolError\n",
    "topic encoder import",
)
start = topics.index("def _check_utf8_mqtt_topic(topic: str) -> None:\n")
topics = topics[:start] + '''def _check_utf8_mqtt_topic(topic: str) -> None:
    try:
        encode_utf8(topic)
    except ProtocolError as exc:
        raise ProtocolError(f"Invalid MQTT topic: {exc}") from exc
'''
TOPICS.write_text(topics)

TEST.write_text(
    '''"""Symmetric MQTT UTF-8 validation for outbound and inbound strings."""

from __future__ import annotations

import pytest

from mqttnext.codec.primitives import append_utf8, pack_utf8, unpack_utf8
from mqttnext.codec.properties import PUBLISH, encode_properties
from mqttnext.errors import MalformedPacketError, ProtocolError
from mqttnext.packets import PublishPacket
from mqttnext.types import Properties


@pytest.mark.parametrize("value", ["a\\x00b", "\\ufeff", "\\ud800"])
def test_pack_utf8_rejects_forbidden_outbound_text(value: str) -> None:
    with pytest.raises(ProtocolError):
        pack_utf8(value)


def test_pack_utf8_rejects_raw_bytes() -> None:
    with pytest.raises(ProtocolError, match="must be str"):
        pack_utf8(b"raw")  # type: ignore[arg-type]


def test_append_utf8_uses_same_validation() -> None:
    with pytest.raises(ProtocolError):
        append_utf8(bytearray(), "bad\\x00value")


def test_string_property_rejects_surrogate_as_protocol_error() -> None:
    properties = Properties()
    properties.set("content_type", "\\ud800")
    with pytest.raises(ProtocolError):
        encode_properties(properties, PUBLISH)


def test_publish_topic_rejects_surrogate_as_protocol_error() -> None:
    packet = PublishPacket(
        topic="bad/\\ud800",
        payload=b"x",
        qos=0,
        retain=False,
        dup=False,
    )
    with pytest.raises(ProtocolError):
        packet.encode()


def test_valid_unicode_roundtrip_is_unchanged() -> None:
    encoded = pack_utf8("capteur/électricité")
    decoded, offset = unpack_utf8(encoded)
    assert decoded == "capteur/électricité"
    assert offset == len(encoded)


def test_inbound_forbidden_text_remains_malformed_packet() -> None:
    wire = b"\\x00\\x03a\\x00b"
    with pytest.raises(MalformedPacketError):
        unpack_utf8(wire)
'''
)
