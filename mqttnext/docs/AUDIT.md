# Auto-audit — livraison Phase 0

Date : 2026-08-01  
Branche : `cursor/mqtt-next-from-scratch-6c02`

## Périmètre audité

Code sous `mqttnext/src/mqttnext` + tests `mqttnext/tests/unit`.

## Checklist correctness

| Point | Statut | Notes |
| --- | --- | --- |
| QoS 2 out : MID conservé jusqu’à PUBCOMP | OK | Test `test_qos2_outbound_keeps_mid_until_pubcomp` ; contraste gmqtt |
| QoS 2 in : dédup / pas de redeliver | OK | Test `test_qos2_inbound_dedup` |
| Receive Maximum ≠ espace MID | OK | `FlowControl` vs `PacketIdPool` ; test dédié |
| Decoder fragmentation + multi-paquet | OK | Tests codec |
| Limite taille paquet | OK | `PacketTooLargeError` |
| `memoryview` non exposé à l’API | OK | `RawPacket.remaining` est `bytes` |
| session_present replay + DUP | OK | Test replay |
| Exhaustive switch effects | OK | branche `Never` dans `AsyncClient._flush_effects` |
| Imports en tête de module | OK | règle workspace |

## Risques connus (assumés Phase 0)

| Risque | Mitigation prévue |
| --- | --- |
| MQTT 5 properties non implémentées | `NotImplementedError` explicite ; phase 1 |
| Pas de keepalive timer dans AsyncClient | phase 1 |
| Pas de reconnect / backoff | phase 1 |
| SUBACK/UNSUBACK non awaitables | phase 1 futures |
| `queue_publish` offline QoS>0 sans borne d’ordre reconnect complexe | tests + ROADMAP |
| Pas de TLS / WS | phase 1–2 |
| Licence TBD | avant spin-out |
| Façade Paho absente | phase 3 |
| Engine `handle_raw` table dict (pas `match`) | OK perf ; exhaustive via KeyError path |

## Non-régressions vs leçons Paho

| Leçon audit | Appliquée ? |
| --- | --- |
| Decoder contigu / buffer borné | Oui (base) |
| Empty props fast path | Oui (octet `0x00`) |
| dict ordonné inflight | Oui |
| Callback hors engine | Oui (effects → API) |
| Pas d’alias auto / cache topic | Oui (non implémenté) |
| Read-ahead batch | Partiel (`drain_packets(limit=100)`) |
| Segmented large payload | Non (phase 2) |

## Non-régressions vs bugs gmqtt

| Bug gmqtt | Traité ? |
| --- | --- |
| PUBCOMP no-op / free MID sur PUBREC | Oui |
| Pas de dédup inbound QoS2 | Oui |
| Receive Maximum → max MID | Oui (séparé) |
| Parser `buf +=` quadratique | Évité (`bytearray` + offset) |
| write sans drain | `TcpTransport.write` appelle `drain()` |

## Vérification exécutée

```bash
cd mqttnext && pip install -e ".[dev]" && python3 -m pytest -q
# 22 passed in 0.03s
```

## Verdict auditeur

**GO pour Phase 0** en tant que fondation / plan exécutable.  
**NO GO production.** Ne pas publier sur PyPI tant que Phase 1 (properties,
keepalive, reconnect, TLS) et la matrice QoS reconnect ne sont pas vertes.
