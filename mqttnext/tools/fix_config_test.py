from pathlib import Path


path = Path("mqttnext/tests/unit/test_config_contracts.py")
text = path.read_text()
old = "from mqttnext.protocol.engine import EngineConfig, ProtocolEngine\n"
new = (
    "from mqttnext.protocol.engine import EngineConfig, ProtocolEngine\n"
    "from mqttnext.protocol.negotiated import NegotiatedSettings\n"
)
if text.count(old) != 1:
    raise RuntimeError("config test import marker not found exactly once")
text = text.replace(old, new, 1)
old = """    engine = ProtocolEngine()
    engine.negotiated.maximum_qos = 0
    engine.negotiated.retain_available = False
    engine.negotiated.maximum_packet_size = 128

    engine.begin_connect()
"""
new = """    engine = ProtocolEngine()
    engine.negotiated = NegotiatedSettings(
        maximum_qos=0,
        retain_available=False,
        maximum_packet_size=128,
    )

    engine.begin_connect()
"""
if text.count(old) != 1:
    raise RuntimeError("config test negotiated marker not found exactly once")
path.write_text(text.replace(old, new, 1))
