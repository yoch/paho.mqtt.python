from pathlib import Path


path = Path("mqttnext/tools/apply_auth_contracts.py")
text = path.read_text()
old = '''    """        connack = ConnAckPacket.decode(raw.remaining, self.config.protocol)
        if connack.reason_code != 0:
""",
'''
new = '''    """        connack = ConnAckPacket.decode(raw.remaining, self.config.protocol)
        self._pending_connect = False
        if connack.reason_code != 0:
""",
'''
if text.count(old) != 1:
    raise RuntimeError(f"auth script CONNACK marker found {text.count(old)} times")
text = text.replace(old, new, 1)
old = '''    """        connack = ConnAckPacket.decode(raw.remaining, self.config.protocol)
        if self.config.protocol == MQTTProtocolVersion.MQTTv5:
'''
new = '''    """        connack = ConnAckPacket.decode(raw.remaining, self.config.protocol)
        self._pending_connect = False
        if self.config.protocol == MQTTProtocolVersion.MQTTv5:
'''
if text.count(old) != 1:
    raise RuntimeError(f"auth script replacement CONNACK marker found {text.count(old)} times")
path.write_text(text.replace(old, new, 1))
