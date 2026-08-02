from pathlib import Path


path = Path("mqttnext/benchmarks/compare_libs.py")
text = path.read_text()
if "WINDOW = 10\n" in text:
    raise SystemExit(0)
old = "WINDOW = 20\n"
new = "# gmqtt 0.7.x exhausts its internal ID generator above ten queued QoS messages.\n# Use the largest common supported window so the comparison remains equivalent.\nWINDOW = 10\n"
if text.count(old) != 1:
    raise RuntimeError(f"benchmark window marker found {text.count(old)} times")
text = text.replace(old, new, 1)
old = "- Micro encode for paho includes queue + `_packet_write` to a null socket.\n"
new = "- Paho is N/A for codec encode because it has no isolated codec API.\n"
if text.count(old) != 1:
    raise RuntimeError(f"benchmark note marker found {text.count(old)} times")
path.write_text(text.replace(old, new, 1))
