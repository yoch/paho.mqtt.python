# Roadmap — mqttnext

## Phase 0 — Fondation (cette branche)

- [x] Analyse Paho optimisé + gmqtt
- [x] Design & principes
- [x] Codec : VBI, buffer incrémental, primitives
- [x] Packets : framing PUBLISH/CONNECT/CONNACK/SUB*/ACK/PING/DISCONNECT
- [x] ProtocolEngine sync + PacketIdPool + FlowControl
- [x] Machines QoS 1 / QoS 2 (in + out)
- [x] Matcher de topics
- [x] Persistence mémoire
- [x] Transport TCP asyncio minimal
- [x] AsyncClient squelette (connect/publish/subscribe)
- [x] Tests unitaires codec + QoS + engine (22 passed)
- [x] Checklist d’auto-audit

## Phase 1 — Client async utilisable

Contrats détaillés : voir `IMPLEMENTATION-GUIDE.md` (sections indiquées).

- [x] MQTT 5 properties encode/decode complets (guide §2)
- [x] ConnACK properties / négociation `NegotiatedSettings` (guide §3)
- [x] Keepalive + PINGREQ/RESP avec détection PINGRESP explicite (guide §4)
- [x] Reconnect policy backoff+jitter, codes terminaux v3/v5 (guide §5)
- [x] Timeouts par opération + futures SUBACK/UNSUBACK (guide §6)
- [x] Validation topics/filtres/`$share` (guide §7)
- [x] Raffinement QoS : PUBREC négatif → `PUBLISH_FAILED` + reason (guide §8)
- [x] TLS (via `ssl=` sur `connect()` / TcpTransport)
- [x] `messages()` : sentinel de fermeture (remplace le polling 0.5 s)
- [x] Callbacks sync+async
- [x] Exemples basiques
- [x] Microbench ingress/egress (`benchmarks/micro_baseline.py`)
- [x] Test d'intégration réel contre Mosquitto (docker) — à lancer en CI/local

## Phase 2 — Robustesse & perf

- [x] Backpressure octets + messages (file writer bornée)
- [x] Segmented large payloads (≥ 1 MiB, header/payload séparés)
- [x] WebSocket transport (client MQTT-over-WS) — *transport bas niveau ; pas encore branché sur AsyncClient*
- [x] Topic alias explicite (déjà phase 1 + validation)
- [x] Fuzzing codec (malformed / noise)
- [x] Intégration Mosquitto live (v3.1.1 + v5, QoS 0/1/2)
- [x] TCP_NODELAY + drain conditionnel (pipelining QoS)
- [x] Unix sockets
- [x] Manual ACK
- [x] Read-ahead / batch ACK refill (micro-opts supplémentaires)

## Phase 3 — Compat & spin-out

- [x] `compat.paho.Client` (VERSION2) — loop_start/connect/publish/subscribe + userdata / topic callbacks / will / auth
- [x] Helpers publish/subscribe (`mqttnext.helpers`)
- [x] Persistence SQLite optionnelle (`SqliteInflightStore`) — *best effort*
- [x] Docs utilisateur + migration (`docs/MIGRATION.md`) + licence Apache-2.0
- [x] Packaging + workflow CI dédié (`.github/workflows/mqttnext.yml` + Mosquitto IT)
- [x] Politique compat Paho documentée (`docs/COMPAT.md`) + façade VERSION2 durcie
- [x] Hardening production : flags/MID, DISCONNECT reasons, Clean Start resume, inbound RM, offline limits, receipts/reconnect
- [ ] Nouveau dépôt open-source (extraction) — en attente spin-out
- [x] Audit de correctness post-phase 3 (`docs/AUDIT-CORRECTNESS.md`)

## Jalons de qualité

| Jalon | Critère |
| --- | --- |
| A | Tests QoS 2 phase matrix verts hors réseau |
| B | Ping Mosquitto local : pub/sub QoS 0/1/2 |
| C | Microbench ingress ≥ baseline gmqtt sur même machine |
| D | Façade Paho fait passer un sous-ensemble `tests/lib` Paho |
| E | Audit externe / fuzz 24h sans crash |
