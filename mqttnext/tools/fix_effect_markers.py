from pathlib import Path


path = Path("mqttnext/tools/apply_effect_atomicity.py")
text = path.read_text()
replacements = {
    '"    def set_auth_handler(\\n",': '"    def set_auth_handler(",',
    '"    async def messages(\\n",': '"    async def messages(",',
    '"    async def ack(\\n",': '"    async def ack(",',
    '"    async def _read_loop(\\n",': '"    async def _read_loop(",',
}
for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one marker {old!r}, found {count}")
    text = text.replace(old, new, 1)
path.write_text(text)
