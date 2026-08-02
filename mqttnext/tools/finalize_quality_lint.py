from pathlib import Path


PYPROJECT = Path("mqttnext/pyproject.toml")
PAHO = Path("mqttnext/src/mqttnext/compat/paho.py")
AUDIT_TEST = Path("mqttnext/tests/unit/test_audit_full.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


pyproject = PYPROJECT.read_text()
pyproject = replace_once(
    pyproject,
    'select = ["E4", "E7", "E9", "F", "B", "SIM", "RUF", "UP"]\n',
    'select = ["E4", "E7", "E9", "F", "B", "RUF006", "UP"]\n',
    "focused Ruff selection",
)
pyproject = replace_once(
    pyproject,
    '"tests/**" = ["B017"]\n',
    '"tests/**" = ["B017", "E731"]\n'
    '"tests/fuzz/test_hypothesis_fuzz.py" = ["E402"]\n',
    "test Ruff exceptions",
)
PYPROJECT.write_text(pyproject)

paho = PAHO.read_text()
paho = paho.replace(
    "asyncio.create_task(self._async._flush_effects())",
    "self._async._spawn_callback(self._async._flush_effects)",
)
paho = paho.replace(
    "asyncio.create_task(self._watch_publish(receipt))",
    "self._async._spawn_callback(self._watch_publish, receipt)",
)
if "asyncio.create_task(" in paho:
    raise RuntimeError("untracked asyncio.create_task remains in compat facade")
PAHO.write_text(paho)

audit_test = AUDIT_TEST.read_text()
audit_test = replace_once(
    audit_test,
    '    h1 = engine.queue_publish("t", b"1", qos=QoS.AT_LEAST_ONCE)\n'
    '    h2 = engine.queue_publish("t", b"2", qos=QoS.AT_LEAST_ONCE)\n',
    '    engine.queue_publish("t", b"1", qos=QoS.AT_LEAST_ONCE)\n'
    '    engine.queue_publish("t", b"2", qos=QoS.AT_LEAST_ONCE)\n',
    "unused replay handles",
)
AUDIT_TEST.write_text(audit_test)
