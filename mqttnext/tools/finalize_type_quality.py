from pathlib import Path


path = Path("mqttnext/src/mqttnext/transport/websocket.py")
text = path.read_text()
old = """        for raw_header in lines[1:]:
            if b":" in raw_header:
                k, _, v = raw_header.partition(b":")
"""
new = """        for header_line_bytes in lines[1:]:
            if b":" in header_line_bytes:
                k, _, v = header_line_bytes.partition(b":")
"""
count = text.count(old)
if count != 1:
    raise RuntimeError(f"typed WebSocket header marker found {count} times")
path.write_text(text.replace(old, new, 1))
