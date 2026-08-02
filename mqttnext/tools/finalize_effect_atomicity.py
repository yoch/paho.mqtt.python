from pathlib import Path


client = Path("mqttnext/src/mqttnext/api/async_client.py")
text = client.read_text()
old = """                except asyncio.CancelledError:
                    raise
                except Exception:
                    self._pending_effects.popleft()
                    raise
"""
new = """                except asyncio.CancelledError:
                    raise
                except FlowControlError:
                    raise
                except Exception:
                    self._pending_effects.popleft()
                    raise
"""
if text.count(old) != 1:
    raise RuntimeError("effect retry exception block not found exactly once")
client.write_text(text.replace(old, new, 1))

test = Path("mqttnext/tests/unit/test_effect_atomicity.py")
test_text = test.read_text()
bad = "from mqttnext.enums import ConnectionState, EffectKind if False else QoS"
good = "from mqttnext.enums import ConnectionState"
if test_text.count(bad) != 1:
    raise RuntimeError("generated test import not found exactly once")
test.write_text(test_text.replace(bad, good, 1))
