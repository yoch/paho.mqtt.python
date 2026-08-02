from pathlib import Path


path = Path("mqttnext/tests/unit/test_auth.py")
text = path.read_text()
old = '''    engine.state = ConnectionState.CONNECTING
    full = AuthPacket(reason_code=0x18).encode()
'''
new = '''    engine.begin_connect()
    engine.take_effects()
    full = AuthPacket(reason_code=0x18).encode()
'''
if text.count(old) != 1:
    raise RuntimeError(f"accepted AUTH setup marker found {text.count(old)} times")
path.write_text(text.replace(old, new, 1))
