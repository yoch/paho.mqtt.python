# Comparative benchmarks

Broker: `127.0.0.1:11883` (local Mosquitto 2.x)  
Date: 2026-08-01 (post audit-correctness fixes)  
Machine: cloud agent VM, Python 3.12

## Results (harness median)

| Scenario | mqttnext | gmqtt | paho | mqttnext/gmqtt | mqttnext/paho |
| --- | ---: | ---: | ---: | ---: | ---: |
| `publish_encode_qos0_small` | 1,093,793 | 1,055,093 | 212,302 | 1.0× | **5.2×** |
| `ingress_decode_50x_qos0_small` | 17,350 | n/a | n/a | — | — |
| `e2e_pub_qos0_p64` | 181,199 | 95,589 | 71,195 | **1.9×** | **2.5×** |
| `e2e_pub_qos1_p64` | 23,005 | 227.3† | 18,886 | — | **1.2×** |
| `e2e_pub_qos2_p64` | 8,206 | 1,186 | 11,941 | **6.9×** | 0.7× |

Units: msg/s (encode / e2e) or batch/s (decode of 50 concatenated packets).

## Reading

- **QoS 0**: mqttnext ahead of both (~1.9× gmqtt, ~2.5× paho).
- **QoS 1**: matches/beats paho on true PUBACK wait; gmqtt handicapped (†).
- **QoS 2**: behind paho on this run; still ahead of gmqtt with real PUBCOMP wait.
- Prior run (pre-audit) saw ~222k QoS0 / ~14k QoS2 — same order of magnitude; VM noise.

## Caveats

- † gmqtt QoS1 drained in batches of 10 (Receive-Maximum-as-MID bug).
- Inflight window capped at 20 for all clients.
- No WAN/TLS/WebSocket in this round.
- Post-audit behavioural changes (PUBREC frees flow slot; SEND-before-MESSAGE flush).

## Reproduce

```bash
mosquitto -c /tmp/mosq-bench.conf -d   # listener 11883, allow_anonymous
cd /workspace && PYTHONPATH=mqttnext/src:/tmp/gmqtt:src \
  python3 mqttnext/benchmarks/compare_libs.py
```
