from pathlib import Path


enums = Path("mqttnext/src/mqttnext/enums.py")
text = enums.read_text()
old = "from enum import IntEnum\n\n\nclass MQTTProtocolVersion"
new = "from enum import IntEnum\n\nfrom mqttnext.errors import MalformedPacketError\n\n\nclass MQTTProtocolVersion"
if text.count(old) != 1:
    raise RuntimeError("enums import marker not found exactly once")
text = text.replace(old, new, 1)
old = '            raise ValueError(f"Unknown MQTT packet type byte 0x{byte:02x}") from exc\n'
new = '            raise MalformedPacketError(\n                f"Unknown MQTT packet type byte 0x{byte:02x}"\n            ) from exc\n'
if text.count(old) != 1:
    raise RuntimeError("PacketType exception marker not found exactly once")
enums.write_text(text.replace(old, new, 1))

test = Path("mqttnext/tests/unit/test_fuzz_contracts.py")
test_text = test.read_text()
old = "from mqttnext.enums import ConnectionState, OutboundQoSState, QoS  # noqa: E402\n"
new = (
    "from mqttnext.enums import (  # noqa: E402\n"
    "    ConnectionState,\n"
    "    OutboundQoSState,\n"
    "    PacketType,\n"
    "    QoS,\n"
    ")\n"
)
if test_text.count(old) != 1:
    raise RuntimeError("fuzz contract enum import marker not found exactly once")
test_text = test_text.replace(old, new, 1)
anchor = "\ndef test_low_level_parser_exceptions_are_not_allowed() -> None:\n"
addition = (
    "\ndef test_reserved_packet_type_raises_public_mqtt_error() -> None:\n"
    "    with pytest.raises(MQTTError):\n"
    "        PacketType.from_byte(0x0D)\n"
)
if test_text.count(anchor) != 1:
    raise RuntimeError("fuzz contract test anchor not found exactly once")
test.write_text(test_text.replace(anchor, addition + anchor, 1))
