# mqttnext

Implémentation MQTT Python **async-native**, conçue from scratch pour devenir
une référence open-source. Ce dossier vit temporairement dans le fork Paho
(`yoch/paho.mqtt.python`) sur la branche dédiée ; il est destiné à être
extrait vers son propre dépôt.

## Pourquoi

| Source | Apport | Limite |
| --- | --- | --- |
| **Paho** (+ branche `benchmarks`) | API mature, couverture MQTT, leçons perf **mesurées** (28 projets GO/NO GO) | Monolithe ~200 KiB, pas d’asyncio natif, dette structurelle |
| **gmqtt** | Architecture async par couches, style event-loop moderne | Moteur QoS 2 incorrect, Receive Maximum mal appliqué, parser allocateur |

`mqttnext` reprend le meilleur des deux **sans hériter** du monolithe Paho ni
des bugs protocolaires gmqtt.

## État

**Phase 1 — client async utilisable** (voir `docs/ROADMAP.md`) :

- Codec MQTT 5 properties complet + validation par paquet
- `NegotiatedSettings` (Receive Maximum, max packet, max QoS, retain, alias…)
- Keepalive PINGREQ/RESP (détection PINGRESP explicite)
- `ReconnectPolicy` (backoff + jitter, codes terminaux)
- Futures awaitables SUBACK/UNSUBACK + timeouts
- Validation topics / filtres / `$share`
- Writer unique, receipts avant wire, TLS via `ssl=`
- **54 tests unitaires verts** ; microbench `benchmarks/micro_baseline.py`

Reste pour clôturer la DoD phase 1 : intégration Mosquitto docker.
WebSocket / façade Paho / fuzz = phases 2–3.

## Documentation

- [`docs/ANALYSIS.md`](docs/ANALYSIS.md) — audit comparatif Paho vs gmqtt
- [`docs/DESIGN.md`](docs/DESIGN.md) — architecture et contrats
- [`docs/IMPLEMENTATION-GUIDE.md`](docs/IMPLEMENTATION-GUIDE.md) — contrats détaillés phases 1–3
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phases
- [`docs/AUDIT.md`](docs/AUDIT.md) — auto-audit + audit de planification

## Quick start (dev)

```bash
cd mqttnext
pip install -e ".[dev]"
python3 -m pytest -q
```

Exemple minimal (nécessite un broker) :

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
