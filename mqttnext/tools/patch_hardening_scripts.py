from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one marker, found {count}")
    path.write_text(text.replace(old, new, 1))


def patch_core() -> None:
    path = ROOT / "tools/apply_hardening_core.py"

    replace_once(
        path,
        '    path = "src/mqttnext/api/async_client.py"\n\n    replace_once(\n',
        '''    path = "src/mqttnext/api/async_client.py"

    replace_once(
        path,
        "from collections import deque\\n",
        "from collections import deque\\nfrom contextlib import nullcontext\\n",
    )

    replace_once(
''',
    )

    replace_once(
        path,
        '''                    with self._engine.store.batch():\\n                        while True:\\n''',
        '''                    store_batch = getattr(self._engine.store, "batch", None)\\n                    with (\\n                        store_batch() if store_batch is not None else nullcontext()\\n                    ):\\n                        while True:\\n''',
    )

    replace_once(
        path,
        '''    def _ensure_callback_worker(self) -> None:\\n        if self._callback_worker_task is None or self._callback_worker_task.done():\\n            self._callback_worker_task = asyncio.create_task(\\n                self._callback_worker(), name=\\"mqttnext-callback-worker\\"\\n            )\\n\\n    async def _enqueue_callback(\\n''',
        '''    def _ensure_callback_worker(self) -> None:\\n        if self._callback_worker_task is None or self._callback_worker_task.done():\\n            self._callback_worker_task = asyncio.create_task(\\n                self._callback_worker(), name=\\"mqttnext-callback-worker\\"\\n            )\\n\\n    def _spawn_callback(self, callback: Callable[..., Any], *args: Any) -> None:\\n        \\\"\\\"\\\"Compatibility entry point for loop-thread callback producers.\\\"\\\"\\\"\\n        self._ensure_callback_worker()\\n        try:\\n            self._callback_queue.put_nowait((callback, args))\\n        except asyncio.QueueFull as exc:\\n            raise MessageDeliveryError(\\n                \\\"Callback delivery queue is full\\\"\\n            ) from exc\\n\\n    async def _enqueue_callback(\\n''',
    )

    replace_once(
        path,
        '''        from collections.abc import ContextManager, Iterator\n        from contextlib import nullcontext\n        from typing import Protocol\n''',
        '''        from collections.abc import Iterator\n        from contextlib import AbstractContextManager, nullcontext\n        from typing import Protocol\n''',
    )
    text = path.read_text()
    expected = text.count("ContextManager[None]")
    if expected != 2:
        raise RuntimeError(f"unexpected ContextManager count: {expected}")
    path.write_text(text.replace("ContextManager[None]", "AbstractContextManager[None]"))


def patch_tests() -> None:
    path = ROOT / "tools/apply_hardening_tests.py"
    old = r'''async def test_tls_rejects_hostname_mismatch(tmp_path: Path) -> None:
    key, cert = _make_certs(tmp_path)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert, key)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=server_ctx)
    assert server.sockets
    port = server.sockets[0].getsockname()[1]
    async with server:
        client_ctx = ssl.create_default_context()
        client_ctx.load_verify_locations(cert)
        client = AsyncClient(client_id="tls-hostname")
        with pytest.raises(ssl.CertificateError):
            await client.connect(
                "localhost.invalid",
                port,
                ssl=client_ctx,
                timeout=5.0,
            )
        assert not client.is_connected
'''
    new = r'''async def test_tls_rejects_hostname_mismatch(tmp_path: Path) -> None:
    if shutil.which("openssl") is None:
        pytest.skip("openssl not available")
    key = tmp_path / "wrong-key.pem"
    cert = tmp_path / "wrong-cert.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "1",
            "-subj", "/CN=wrong.example",
            "-addext", "subjectAltName=DNS:wrong.example",
        ],
        check=True,
        capture_output=True,
    )
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert, key)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=server_ctx)
    assert server.sockets
    port = server.sockets[0].getsockname()[1]
    async with server:
        client_ctx = ssl.create_default_context()
        client_ctx.load_verify_locations(cert)
        client = AsyncClient(client_id="tls-hostname")
        with pytest.raises(ssl.SSLCertVerificationError):
            await client.connect(
                "127.0.0.1",
                port,
                ssl=client_ctx,
                timeout=5.0,
            )
        assert not client.is_connected
'''
    replace_once(path, old, new)


def patch_bench() -> None:
    path = ROOT / "tools/apply_hardening_bench.py"
    replace_once(path, '        import struct\n', '')
    replace_once(
        path,
        '        HEADER = struct.Struct("!QQ")\n        WINDOW = 100\n',
        '        HEADER_HEX_BYTES = 32\n        WINDOW = 100\n',
    )
    replace_once(
        path,
        '''        def make_payload(sequence: int, size: int) -> bytes:
            header = HEADER.pack(sequence, time.monotonic_ns())
            return header + b"x" * max(0, size - len(header))
''',
        '''        def make_payload(sequence: int, size: int) -> bytes:
            header = f"{sequence:016x}{time.monotonic_ns():016x}".encode("ascii")
            return header + b"x" * max(0, size - len(header))
''',
    )
    replace_once(
        path,
        '''            latencies = []
            for raw, arrived_ns in arrivals:
                if len(raw) < HEADER.size:
                    raise RuntimeError(f"invalid payload length {len(raw)}")
                _, sent_ns = HEADER.unpack(raw[: HEADER.size])
                latencies.append((arrived_ns - sent_ns) / 1_000_000)
''',
        '''            latencies = []
            sequences = []
            for raw, arrived_ns in arrivals:
                if len(raw) < HEADER_HEX_BYTES:
                    raise RuntimeError(f"invalid payload length {len(raw)}")
                try:
                    sequence = int(raw[:16], 16)
                    sent_ns = int(raw[16:HEADER_HEX_BYTES], 16)
                except ValueError as exc:
                    raise RuntimeError("invalid benchmark payload header") from exc
                sequences.append(sequence)
                latencies.append((arrived_ns - sent_ns) / 1_000_000)
            if sorted(sequences) != list(range(args.count)):
                raise RuntimeError("subscriber payload sequence mismatch")
''',
    )


def main() -> None:
    patch_core()
    patch_tests()
    patch_bench()


if __name__ == "__main__":
    main()
