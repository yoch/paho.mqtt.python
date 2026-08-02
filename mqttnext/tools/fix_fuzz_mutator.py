from pathlib import Path


path = Path("mqttnext/tests/fuzz/fuzz.py")
text = path.read_text()
old = """        else:
            buf = buf[: rng.randrange(1, len(buf) + 1)]
"""
new = """        elif buf:
            buf = buf[: rng.randrange(1, len(buf) + 1)]
"""
if text.count(old) != 1:
    raise RuntimeError("fuzz mutator truncation marker not found exactly once")
path.write_text(text.replace(old, new, 1))
