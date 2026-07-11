# Benchmark client Paho — origin/master

Profil **smoke**, suite **core**, 1 run/point.

## Contexte

| Champ | Valeur |
|---|---|
| Source Paho | `origin/master` (`7a3d161`) |
| Worktree | `/tmp/paho-origin-master` |
| Points | 41 (valid=41, inconclusive=0) |
| Python | 3.12.3 |
| CPU | Intel(R) Core(TM) i7-3770 CPU @ 3.40GHz |
| Broker | `127.0.0.1:11883` |
| Artefact | `core-smoke-origin-master-7a3d161-20260711T194959Z.json` |

## Publication — sweep payloads QoS0

| Payload | msg/s |
|---|---:|
| `binary64` | 12,837 |
| `event1k` | 13,915 |
| `record16k` | 11,450 |
| `telemetry256` | 12,385 |
| `blob1m` | 0 |
| `empty0` | 12,456 |
| `block64k` | 8,537 |

## Publication — sweep QoS

| QoS | msg/s |
|---:|---:|
| 0 | 12,126 |
| 1 | 8,952 |
| 2 | 6,985 |

## Ingress subscriber

| Scénario | Détail | msg/s |
|---|---|---:|
| exact | 32 pubs | 3,771 |
| hierarchy | fleet4k_zipf/plus | 3,765 |
| hierarchy | fleet4k_uniform/hash | 3,970 |
| hierarchy | fleet4k_zipf/hash | 3,885 |
| hierarchy | fleet4k_uniform/plus | 3,831 |
| callbacks | filters=16 | 0 |
| callbacks | filters=1 | 0 |
| callbacks | filters=256 | 0 |

## Intégrité / latence (aperçu)

| Point | status | msg/s |
|---|---|---:|
| `e2e_integrity` qos=2 frac=None `telemetry256` | valid | 1,000 |
| `e2e_integrity` qos=1 frac=None `telemetry256` | valid | 1,000 |
| `e2e_integrity` qos=0 frac=None `empty0` | valid | 1,000 |
| `e2e_integrity` qos=0 frac=None `telemetry256` | valid | 999 |
| `puback_latency_qos1` qos=1 frac=0.75 `telemetry256` | valid | 750 |
| `puback_latency_qos1` qos=1 frac=0.5 `telemetry256` | valid | 500 |
| `puback_latency_qos1` qos=1 frac=0.9 `telemetry256` | valid | 900 |
| `puback_latency_qos1` qos=1 frac=0.25 `telemetry256` | valid | 250 |
| `application_rtt_qos1` qos=1 frac=0.75 `telemetry256` | valid | 756 |
| `application_rtt_qos1` qos=1 frac=0.5 `telemetry256` | valid | 501 |
| `application_rtt_qos1` qos=1 frac=0.9 `telemetry256` | valid | 890 |
| `application_rtt_qos1` qos=1 frac=0.25 `telemetry256` | valid | 250 |
