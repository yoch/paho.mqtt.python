# mqttnext

`mqttnext` is an async-native MQTT client implemented from scratch around a
synchronous protocol engine. It currently lives in this Paho fork while the API
and packaging are prepared for extraction into a dedicated repository.

License: **Apache-2.0**. Python: **3.11+**.

## Design goals

- protocol correctness before throughput claims;
- one authoritative QoS/session state machine;
- bounded backpressure for wire, callback and iterator delivery;
- native `asyncio` API with an additive Paho VERSION2 compatibility layer;
- injectable in-memory or SQLite inflight persistence;
- measured optimisations only, with equivalent benchmark contracts.

## Current status

The implemented surface includes MQTT 3.1.1/5 pub/sub QoS 0/1/2, TCP/TLS,
WebSocket and Unix transports, reconnect/session replay, keepalive, MQTT 5
properties and AUTH hooks, manual acknowledgement, bounded delivery queues,
SQLite persistence, helpers and the Paho-compatible façade.

The validation baseline is **230 unit tests**, Mosquitto integration on Python
3.11/3.12/3.13, deterministic and Hypothesis fuzzing, Ruff, mypy and an 80%
coverage gate. Performance runs cover equivalent PUBACK completion, independent
subscriber-confirmed delivery over TCP/TLS/WAN profiles, callback/iterator
stress and SQLite batching. Generated measurements are CI artefacts rather than
committed source files.

## Documentation

- [`docs/ANALYSIS.md`](docs/ANALYSIS.md) — architectural lessons from Paho and gmqtt
- [`docs/DESIGN.md`](docs/DESIGN.md) — architecture and invariants
- [`docs/IMPLEMENTATION-GUIDE.md`](docs/IMPLEMENTATION-GUIDE.md) — protocol contracts
- [`docs/COMPAT.md`](docs/COMPAT.md) — supported Paho compatibility and differences
- [`docs/MIGRATION.md`](docs/MIGRATION.md) — migration from Paho or gmqtt
- [`docs/BENCHMARKING.md`](docs/BENCHMARKING.md) — benchmark validity contract
- [`docs/FUZZING.md`](docs/FUZZING.md) — fuzzing strategy
- [`docs/LOGGING.md`](docs/LOGGING.md) — observability policy
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — remaining release work

Historical audit narratives and generated benchmark snapshots are intentionally
kept in Git history and pull-request artefacts, not duplicated in the maintained
documentation set.

## Development

```bash
cd mqttnext
pip install -e ".[dev]"
python -m pytest -q
```

```python
import asyncio
from mqttnext.api import AsyncClient


async def main() -> None:
    client = AsyncClient("demo")
    await client.connect("127.0.0.1", 1883)
    await client.subscribe("demo/#")
    receipt = await client.publish("demo/hello", b"world", qos=1)
    await receipt.wait()
    await client.disconnect()


asyncio.run(main())
```
