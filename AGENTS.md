# AGENTS.md

## Cursor Cloud specific instructions

This repository hosts **two** Python products, both pure-Python libraries (no web UI):

- `paho-mqtt` — mature Eclipse Paho MQTT client, package at `src/paho`, config in root `pyproject.toml`. Requires Python >= 3.7.
- `mqttnext` — new async-native MQTT client under `mqttnext/`, config in `mqttnext/pyproject.toml`. Requires Python >= 3.11.

The VM has Python 3.12, which satisfies both. Dependencies are installed at user level with
`pip --user --break-system-packages` (the system interpreter is marked EXTERNALLY-MANAGED),
so console scripts land in `~/.local/bin` (not on `PATH`) — invoke tools via `python3 -m <tool>`
(e.g. `python3 -m pytest`, `python3 -m ruff`, `python3 -m build`). The startup update script
handles the editable installs; no manual dependency step is needed.

### Test / lint / build commands

| Product | Test | Lint | Build |
| --- | --- | --- | --- |
| paho-mqtt | `python3 -m pytest` (from repo root) | `python3 -m ruff check src` | `python3 -m build .` (from repo root) |
| mqttnext | `python3 -m pytest -q tests/unit` (from `mqttnext/`) | `python3 -m ruff check .` (from `mqttnext/`) | `python3 -m build .` (from `mqttnext/`) |

Notes and non-obvious caveats:

- `python3 -m build` uses an isolated build env and needs network to fetch `hatchling`.
- The official paho lint job is `tox -e lint` (pre-commit with a pinned older ruff 0.1.9, plus `black`/`mypy`/`safety`); the directly-installed newer `ruff` reports more findings than CI. Treat existing ruff findings in `src/` and `mqttnext/` as pre-existing, not setup failures.
- paho's SSL tests (`tests/lib/test_08_ssl_*`) fail with `CERTIFICATE_EXPIRED` because the checked-in test certs under `tests/ssl/` expired 2026-07-06. Regenerate with `tests/ssl/gen.sh` if you need them; this is a test-fixture issue, unrelated to environment setup.
- paho tests that need the `paho.mqtt.testing` interop broker are auto-skipped when it is absent (CI checks out `eclipse/paho.mqtt.testing` into `paho.mqtt.testing/`, which is gitignored).

### Running a broker (for integration tests & manual pub/sub)

Mosquitto is installed. `mqttnext`'s integration tests (`mqttnext/tests/integration/test_mosquitto.py`)
require a broker on `127.0.0.1:11883` and are skipped otherwise. Start a broker listening on both the
default `1883` and the integration `11883` ports (do NOT rely on the systemd service; run it directly):

```bash
printf 'listener 1883 127.0.0.1\nlistener 11883 127.0.0.1\nallow_anonymous true\n' > /tmp/mosq.conf
mosquitto -c /tmp/mosq.conf   # run in a tmux session / background
```

With the broker up, `cd mqttnext && python3 -m pytest -q tests/integration` runs a real pub/sub
roundtrip (MQTT v3.1.1 & v5 × QoS 0/1/2).
