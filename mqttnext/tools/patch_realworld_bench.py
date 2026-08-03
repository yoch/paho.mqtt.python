from pathlib import Path

path = Path("mqttnext/tools/realworld_bench.py")
text = path.read_text()

old = '''def wait_subscribed(proc: subprocess.Popen[bytes]) -> None:
    assert proc.stderr is not None
    deadline = time.monotonic() + 8.0
    collected: list[bytes] = []
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        readable, _, _ = select.select([proc.stderr], [], [], max(0.0, remaining))
        if not readable:
            break
        line = proc.stderr.readline()
        if not line:
            break
        collected.append(line)
        if b"received SUBACK" in line:
            return
    proc.kill()
    detail = b"".join(collected).decode("utf-8", errors="replace")
    raise RuntimeError(f"subscriber did not confirm SUBACK: {detail}")
'''
new = '''def wait_subscribed(proc: subprocess.Popen[bytes]) -> None:
    # mosquitto_sub routes debug output differently across packaged builds.
    # The broker is local and already health-checked, so a bounded startup
    # grace period is more portable than parsing human-oriented debug text.
    time.sleep(0.5)
    if proc.poll() is not None:
        assert proc.stderr is not None
        detail = proc.stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"subscriber exited during startup: {detail}")
'''
if text.count(old) != 1:
    raise RuntimeError(f"wait_subscribed marker found {text.count(old)} times")
text = text.replace(old, new, 1)
text = text.replace("import select\n", "", 1)

old = '''    completed = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
        timeout=TIMEOUT + 30,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
'''
new = '''    completed = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        timeout=TIMEOUT + 30,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"benchmark child failed rc={completed.returncode}\\n"
            f"stdout:\\n{completed.stdout}\\nstderr:\\n{completed.stderr}"
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
'''
if text.count(old) != 1:
    raise RuntimeError(f"subprocess marker found {text.count(old)} times")
path.write_text(text.replace(old, new, 1))
