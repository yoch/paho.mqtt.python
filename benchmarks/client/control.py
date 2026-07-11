"""Shared control-plane helpers for worker processes."""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


def configure_source_root(source_root: str) -> str:
    """Put <source_root>/src first on sys.path and return imported paho.__file__."""
    src = str(Path(source_root).resolve() / "src")
    while src in sys.path:
        sys.path.remove(src)
    sys.path.insert(0, src)
    # Ensure we don't pick up a previously imported paho.
    for name in list(sys.modules):
        if name == "paho" or name.startswith("paho."):
            del sys.modules[name]
    import paho  # noqa: WPS433 - intentional late import after path setup

    return str(Path(paho.__file__).resolve())


def write_json(path: str, payload: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def wait_for_file(path: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if os.path.exists(path):
            return
        time.sleep(0.05)
    raise TimeoutError(f"timed out waiting for {path}")


def touch(path: str, payload: Optional[dict] = None) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if payload is None:
        Path(path).write_text("ready\n", encoding="utf-8")
    else:
        write_json(path, payload)


class BarrierServer:
    """Tiny line-oriented Unix socket barrier for T0/T1 coordination."""

    def __init__(self, path: str):
        self.path = path
        if os.path.exists(path):
            os.unlink(path)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(16)
        self.sock.settimeout(0.5)
        self.clients = []

    def accept_n(self, n: int, timeout_s: float = 30.0) -> None:
        deadline = time.time() + timeout_s
        while len(self.clients) < n and time.time() < deadline:
            try:
                conn, _ = self.sock.accept()
                conn.settimeout(1.0)
                self.clients.append(conn)
            except socket.timeout:
                continue
        if len(self.clients) < n:
            raise TimeoutError(f"only {len(self.clients)}/{n} workers connected to barrier")

    def broadcast(self, message: str) -> None:
        data = (message.strip() + "\n").encode("utf-8")
        for conn in self.clients:
            conn.sendall(data)

    def close(self) -> None:
        for conn in self.clients:
            try:
                conn.close()
            except OSError:
                pass
        try:
            self.sock.close()
        except OSError:
            pass
        if os.path.exists(self.path):
            os.unlink(self.path)


def barrier_client_wait(path: str, expected: str, timeout_s: float = 120.0) -> str:
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(path)
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(64)
                if not chunk:
                    break
                buf += chunk
            sock.close()
            line = buf.decode("utf-8").strip()
            if line == expected or expected == "*":
                return line
            if line:
                return line
        except OSError as exc:
            last_err = exc
            time.sleep(0.05)
    raise TimeoutError(f"barrier wait for {expected!r} failed: {last_err}")
