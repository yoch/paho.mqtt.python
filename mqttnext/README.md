# mqttnext

Implémentation MQTT Python **async-native**, conçue from scratch pour devenir
une référence open-source. Ce dossier vit temporairement dans le fork Paho
(`yoch/paho.mqtt.python`) sur la branche dédiée ; il est destiné à être
extrait vers son propre dépôt.

Licence : **Apache-2.0**.

## Pourquoi

| Source | Apport | Limite |
| --- | --- | --- |
| **Paho** (+ branche `benchmarks`) | API mature, couverture MQTT, leçons perf **mesurées** (28 projets GO/NO GO) | Monolithe ~200 KiB, pas d’asyncio natif, dette structurelle |
| **gmqtt** | Architecture async par couches, style event-loop moderne | Moteur QoS 2 incorrect, Receive Maximum mal appliqué, parser allocateur |

`mqttnext` reprend le meilleur des deux **sans hériter** du monolithe Paho ni
des bugs protocolaires gmqtt.

## État

**Hardening production + compat Paho** (voir `docs/ROADMAP.md`) :

- Engine / AsyncClient durcis (flags, MID, DISCONNECT, Clean Start resume, inbound RM, offline limits, receipts/reconnect)
- Façade `compat.paho` VERSION2 + politique documentée dans `docs/COMPAT.md`
- Helpers, SQLite best-effort, CI Mosquitto, licence Apache-2.0
- **87+ tests** ; benches `benchmarks/results/compare_libs.md`

Reste principal : spin-out dépôt dédié.

## Documentation

- [`docs/ANALYSIS.md`](docs/ANALYSIS.md) — audit comparatif Paho vs gmqtt
- [`docs/DESIGN.md`](docs/DESIGN.md) — architecture et contrats
- [`docs/IMPLEMENTATION-GUIDE.md`](docs/IMPLEMENTATION-GUIDE.md) — contrats détaillés
- [`docs/COMPAT.md`](docs/COMPAT.md) — compat Paho : supporté / écarts / rejets
- [`docs/MIGRATION.md`](docs/MIGRATION.md) — migration Paho / gmqtt
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phases
- [`docs/AUDIT-CORRECTNESS.md`](docs/AUDIT-CORRECTNESS.md) — audit correctness + benches

## Quick start (dev)

```bash
cd mqttnext
pip install -e ".[dev]"
python3 -m pytest -q
```

```python
import asyncio
from mqttnext.api import AsyncClient

async def main():
    client = AsyncClient("demo")
    await client.connect("127.0.0.1", 1883)
    await client.subscribe("demo/#")
    receipt = await client.publish("demo/hello", b"world", qos=1)
    await receipt.wait()
    await client.disconnect()

asyncio.run(main())
```

## Principes non négociables

1. Correctness before speed
2. Engine sync, I/O async
3. Une source de vérité pour l’état QoS
4. Mesurer avant d’optimiser (méthodologie audit Paho)
5. Compat Paho = couche additive, jamais le cœur
