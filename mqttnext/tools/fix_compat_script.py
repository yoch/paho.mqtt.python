from pathlib import Path


path = Path("mqttnext/tools/apply_compat_confinement.py")
text = path.read_text()
old = '        """Run a short synchronous mutation on the network loop when active."""'
new = '        \\"\\"\\"Run a short synchronous mutation on the network loop when active.\\"\\"\\"'
count = text.count(old)
if count != 1:
    raise RuntimeError(f"compat script docstring marker found {count} times")
path.write_text(text.replace(old, new, 1))
