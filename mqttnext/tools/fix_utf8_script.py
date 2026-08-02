from pathlib import Path


path = Path("mqttnext/tools/apply_utf8_symmetry.py")
text = path.read_text()
replacements = {
    '    """Validate and encode one MQTT UTF-8 string without its length prefix."""':
        '    \\"\\"\\"Validate and encode one MQTT UTF-8 string without its length prefix.\\"\\"\\"',
    '    """Append MQTT UTF-8 string encoding into *buf* without intermediate concat."""':
        '    \\"\\"\\"Append MQTT UTF-8 string encoding into *buf* without intermediate concat.\\"\\"\\"',
}
for old, new in replacements.items():
    count = text.count(old)
    if count < 1:
        raise RuntimeError(f"UTF-8 script marker not found: {old!r}")
    text = text.replace(old, new)
path.write_text(text)
