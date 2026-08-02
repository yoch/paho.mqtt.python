# Comparative benchmarks

Broker: `127.0.0.1:11883` (local Mosquitto 2.x)  
Date: 2026-08-01 (post production-hardening)  
Machine: cloud agent VM, Python 3.12

## Results (harness median)

| Scenario | mqttnext | gmqtt | paho | mqttnext/gmqtt | mqttnext/paho |
| --- | ---: | ---: | ---: | ---: | ---: |
| `publish_encode_qos0_small` | 1,102,432 | 1,045,238 | 214,270 | 1.1× | **5.1×** |
| `ingress_decode_50x_qos0_small` | 17,132 | n/a | n/a | — | — |
| `e2e_pub_qos0_p64` | 182,291 | 97,084 | 74,893 | **1.9×** | **2.4×** |
| `e2e_pub_qos1_p64` | 23,034 | 227.3† | 22,217 | — | **1.0×** |
| `e2e_pub_qos2_p64` | 13,351 | 54,559‡ | 13,523 | — | **1.0×** |

Units: msg/s (encode / e2e) or batch/s (decode of 50 concatenated packets).

## Reading

- **QoS 0**: mqttnext ahead (~1.9× gmqtt, ~2.4× paho).
- **QoS 1 / 2**: matches paho on true PUBACK/PUBCOMP completion.
- † gmqtt QoS1 drained in batches of 10 (Receive-Maximum-as-MID bug).
- ‡ gmqtt QoS2 `wait_empty` returns after PUBREC — not comparable to PUBCOMP.

## Hardening notes affecting perf

- No `drain()` in the writer loop (avoids deadlock vs reader enqueue of PUBREL).
- Local flow window held until PUBCOMP (stable under load; see `AUDIT-CORRECTNESS.md`).

## Reproduce

```bash
mosquitto -c /tmp/mosq-bench.conf -d   # listener 11883, allow_anonymous
cd /workspace && PYTHONPATH=mqttnext/src:/tmp/gmqtt:src \
  python3 mqttnext/benchmarks/compare_libs.py
```
