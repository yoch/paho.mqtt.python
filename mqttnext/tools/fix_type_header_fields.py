from pathlib import Path


path = Path("mqttnext/src/mqttnext/transport/websocket.py")
text = path.read_text()
old = """        for header_line_bytes in lines[1:]:
            if b":" in header_line_bytes:
                k, _, v = header_line_bytes.partition(b":")
                headers_map[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
"""
new = """        for header_line_bytes in lines[1:]:
            if b":" in header_line_bytes:
                raw_name, _, raw_value = header_line_bytes.partition(b":")
                headers_map[raw_name.decode("latin1").strip().lower()] = (
                    raw_value.decode("latin1").strip()
                )
"""
count = text.count(old)
if count != 1:
    raise RuntimeError(f"typed WebSocket header fields marker found {count} times")
path.write_text(text.replace(old, new, 1))
