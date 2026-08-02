# Sprint performance — mesures isolées

Date: 2026-08-02  
Harness: `mqttnext/benchmarks/perf_sprint.py`  
Broker: Mosquitto local `:11883`  
Machine: cloud agent VM, Python 3.12

Chaque piste a été mesurée **avant** (baseline) puis après les changements
retenus. Les pistes rejetées ou non retenues sont documentées aussi.

## Baseline → final (résumé)

| Track | Metric | Baseline | Final | Δ |
| --- | --- | ---: | ---: | ---: |
| A | encode QoS0 MQTT 3.1.1 | 1,023,910 | 1,324,000 | **+29%** |
| A | encode QoS0 MQTT 5 empty props | 1,012,177 | 1,281,549 | **+27%** |
| A | decode QoS0 MQTT 3.1.1 | 369,746 | 519,582 | **+41%** |
| A | decode QoS0 MQTT 5 empty props | 317,425 | 467,817 | **+47%** |
| B | ingress decode 50× | 16,699 | 17,521 | +5% |
| B | ingress decode 500× | 1,703 | 1,793 | +5% |
| C | e2e QoS0 (rm20) | 120,566 | 201,494 | **+67%** |
| C | e2e QoS1 (rm20) | 37,417 | 40,430 | +8% |
| C | e2e QoS2 (rm20) | 23,471 | 25,923 | +10% |
| D | e2e QoS1 rm100 (nouveau défaut) | 41,214 | 47,599 | **+15%** vs base rm100 |
| D | e2e QoS2 rm100 | 25,894 | 32,092 | **+24%** vs base rm100 |

Comparatif libs (post-sprint, `compare_libs.py`, payload 64 B, rm=100) :

| Scenario | mqttnext | gmqtt | paho | vs gmqtt | vs paho |
| --- | ---: | ---: | ---: | ---: | ---: |
| encode QoS0 | ~1.38M | ~1.05M | ~213k | 1.3× | **6.4×** |
| e2e QoS0 | ~226k | ~96k | ~75k | **2.3×** | **3.0×** |
| e2e QoS1 | ~24–48k† | ~227‡ | ~22k | — | ≥1.1× |
| e2e QoS2 | ~14–34k† | n/c‡ | ~13.5k | — | ~1.0–1.5× |

† Selon harness (counts / RM) ; sprint isolé avec counts élevés + rm100 ≈ 48k / 32k.  
‡ gmqtt : Receive-Maximum-as-MID (QoS1) ; QoS2 `wait_empty` au PUBREC.

---

## Piste A — Codec PUBLISH

### Idées testées

| Idée | Verdict | Note |
| --- | --- | --- |
| VBI fast-path `<128` + table `_VBI_ONE` | **GO** | `encode_vbi` / `decode_vbi` / `append_vbi` |
| Empty MQTT5 props encode constant | **GO** | `_EMPTY_PROPS_V5 = b"\x00"` sans appeler `encode_properties` |
| Empty props decode short-circuit (`0x00`) | **GO** | Gros gain decode MQTT5 |
| Pré-dimensionner `bytearray` + writes par index | **NO GO** | ~0.5× vs append sur petits frames (mesuré) |
| Append-built PUBLISH (topic/mid/props/payload) | **GO** | ~+29% encode vs baseline |
| Éviter `bytes()` redondant sur payload decode | **GO** | slice owned depuis le decoder |
| UTF-8 MQTT : fast-path `str.isascii()` | **GO** | decode +41% |

### Non retenu

- Partager un singleton `Properties()` vide mutable (risque mutation caller).
- Zero-copy `memoryview` vers l’API (contrat : jamais d’alias du buffer réutilisable).

---

## Piste B — Ingress

| Idée | Verdict | Note |
| --- | --- | --- |
| `bytearray.clear()` au lieu de réallouer | **GO** | |
| `process_packets(callback)` sans list | **GO** | utilisé par `_read_loop` |
| Un seul `_flush_effects` par `read()` | **GO** | au lieu d’un flush / 100 paquets |
| Ring buffer / compaction fancy | reporté | complexité > gain observé (~5%) |

---

## Piste C — Writer / backpressure

| Idée | Verdict | Note |
| --- | --- | --- |
| `write_many` / `writelines` par batch | **GO** | TCP + Unix ; **pas** de `drain()` fin de batch |
| Batch writer 64 → 256 | **GO** | |
| Fast-path enqueue sans `Condition` si place | **GO** | sûr sous scheduling coopératif asyncio |
| `notify_all` seulement si waiters | **GO** | compteur `_outbound_waiters` |
| `await drain()` après chaque batch | **NO GO** | deadlock reader/ACK (déjà documenté) |

---

## Piste D — Publish allocations / pipelining

| Idée | Verdict | Note |
| --- | --- | --- |
| `PacketIdPool` free-list LIFO | **GO** | |
| Encode différé jusqu’à `_launch_outbound` | **GO** | budget taille via estimate |
| QoS0 : pas d’`asyncio.Event` sur receipt | **GO** | fort sur firehose QoS0 |
| `local_receive_maximum` défaut 20 → **100** | **GO** | plateau ~500+ ; 100 = bon défaut |
| Libérer flow au PUBREC | **NO GO** | stalls ×20 (AUDIT-CORRECTNESS) |

### Courbe Receive Maximum (post-opts, isolée)

| RM | QoS1 msg/s | QoS2 msg/s |
| ---: | ---: | ---: |
| 20 | 40.8k | 25.9k |
| **100** | **47.6k** | **32.1k** |
| 500 | 48.7k | 33.7k |
| 2000 | 50.1k | 34.0k |

---

## Reproduire

```bash
mosquitto -c /tmp/mosq-bench.conf -d   # :11883
cd /workspace
PYTHONPATH=mqttnext/src python3 mqttnext/benchmarks/perf_sprint.py --tag run
PYTHONPATH=mqttnext/src:/tmp/gmqtt:src python3 mqttnext/benchmarks/compare_libs.py
```

Artefacts JSON/MD : `mqttnext/benchmarks/results/perf_sprint/`.
