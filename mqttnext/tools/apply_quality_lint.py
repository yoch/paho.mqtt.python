from pathlib import Path

CLIENT = Path("mqttnext/src/mqttnext/api/async_client.py")
PYPROJECT = Path("mqttnext/pyproject.toml")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)

client = CLIENT.read_text()
client = replace_once(client, "    async def _write_loop(self) -> None:\n        assert self._transport is not None\n", "    async def _write_contiguous(\n        self, transport: AsyncTransport, parts: list[bytes]\n    ) -> None:\n        if not parts:\n            return\n        write_many = getattr(transport, \"write_many\", None)\n        if write_many is not None:\n            await write_many(parts)\n        else:\n            for part in parts:\n                await transport.write(part)\n        parts.clear()\n\n    async def _write_loop(self) -> None:\n        assert self._transport is not None\n", "writer helper")
client = replace_once(client, "                    contiguous: list[bytes] = []\n                    transport = self._transport\n\n                    async def _flush_contiguous() -> None:\n                        if not contiguous:\n                            return\n                        write_many = getattr(transport, \"write_many\", None)\n                        if write_many is not None:\n                            await write_many(contiguous)\n                        else:\n                            for part in contiguous:\n                                await transport.write(part)\n                        contiguous.clear()\n\n                    for data in batch:\n                        if isinstance(data, tuple):\n                            await _flush_contiguous()\n                            for part in data:\n                                await transport.write(part)\n                        else:\n                            contiguous.append(data)\n                    await _flush_contiguous()\n", "                    contiguous: list[bytes] = []\n                    transport = self._transport\n                    if transport is None:\n                        raise ConnectionError(\"Transport closed while writer was active\")\n\n                    for data in batch:\n                        if isinstance(data, tuple):\n                            await self._write_contiguous(transport, contiguous)\n                            for part in data:\n                                await transport.write(part)\n                        else:\n                            contiguous.append(data)\n                    await self._write_contiguous(transport, contiguous)\n", "writer closure")
CLIENT.write_text(client)

pyproject = PYPROJECT.read_text()
pyproject = replace_once(pyproject, "dev = [\n    \"pytest>=8\",\n    \"pytest-asyncio>=0.24\",\n]\n", "dev = [\n    \"mypy>=1.17\",\n    \"pytest>=8\",\n    \"pytest-asyncio>=0.24\",\n    \"pytest-cov>=6\",\n    \"ruff>=0.16\",\n]\n", "quality dependencies")
pyproject = replace_once(pyproject, "[tool.ruff]\nline-length = 100\ntarget-version = \"py311\"\n", "[tool.ruff]\nline-length = 100\ntarget-version = \"py311\"\n\n[tool.ruff.lint]\nselect = [\"E4\", \"E7\", \"E9\", \"F\", \"B\", \"SIM\", \"RUF\", \"UP\"]\n\n[tool.ruff.lint.per-file-ignores]\n\"src/mqttnext/protocol/__init__.py\" = [\"F401\"]\n\"tests/**\" = [\"B017\"]\n", "ruff configuration")
PYPROJECT.write_text(pyproject)
