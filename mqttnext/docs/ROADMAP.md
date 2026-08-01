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

- MQTT 5 properties encode/decode complets (guide §2)
- ConnACK properties / négociation `NegotiatedSettings` (guide §3)
- Keepalive + PINGREQ/RESP avec détection PINGRESP explicite (guide §4)
- Reconnect policy backoff+jitter, codes terminaux v3/v5 (guide §5)
- Timeouts par opération + futures SUBACK/UNSUBACK (guide §6)
- Validation topics/filtres/`$share` (guide §7)
- Raffinement QoS : PUBREC négatif → `PUBLISH_FAILED` + reason (guide §8)
- TLS
- `messages()` : sentinel de fermeture (remplace le polling 0.5 s)
- Callbacks sync+async (politique d'erreur explicite)
- Exemples basiques
- Microbench ingress/egress (port idées harness Paho) — baseline officielle

## Phase 2 — Robustesse & perf

- Read-ahead / batch ACK refill
- Segmented large payloads
- WebSocket transport
- Unix sockets
- Manual ACK
- Shared subscriptions validation
- Topic alias **explicite** (pas auto)
- Fuzzing codec (malformed packets)
- Harness client e2e vs Mosquitto

## Phase 3 — Compat & spin-out

- `compat.paho.Client` (VERSION2)
- Helpers publish/subscribe
- `loop_start` adaptateur
- Persistence SQLite optionnelle
- Docs utilisateur + migration depuis Paho/gmqtt
- Nouveau dépôt open-source + CI + packaging

## Jalons de qualité

| Jalon | Critère |
| --- | --- |
| A | Tests QoS 2 phase matrix verts hors réseau |
| B | Ping Mosquitto local : pub/sub QoS 0/1/2 |
| C | Microbench ingress ≥ baseline gmqtt sur même machine |
| D | Façade Paho fait passer un sous-ensemble `tests/lib` Paho |
| E | Audit externe / fuzz 24h sans crash |
