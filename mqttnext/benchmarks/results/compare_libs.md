# Comparative benchmarks

Broker: `127.0.0.1:11883` (local Mosquitto 2.x)  
Date: 2026-08-02 (post perf sprint)  
Machine: cloud agent VM, Python 3.12  
mqttnext `local_receive_maximum=100` (new default)

## Results (harness median)

| Scenario | mqttnext | gmqtt | paho | mqttnext/gmqtt | mqttnext/paho |
| --- | ---: | ---: | ---: | ---: | ---: |
| `publish_encode_qos0_small` | 1,390,266 | 1,009,279 | 210,484 | **1.4×** | **6.6×** |
| `ingress_decode_50x_qos0_small` | 17,763 | n/a | n/a | — | — |
| `e2e_pub_qos0_p64` | 231,815 | 97,679 | 75,730 | **2.4×** | **3.1×** |
| `e2e_pub_qos1_p64` | 27,448 | 227.2† | 21,973 | — | **1.2×** |
| `e2e_pub_qos2_p64` | 15,900 | 51,574‡ | 13,513 | — | **1.2×** |

Units: msg/s (encode / e2e) or batch/s (decode of 50 concatenated packets).

## Reading

- **QoS 0**: mqttnext ahead (~2.4× gmqtt, ~3.1× paho) after codec + writer + QoS0 path opts.
- **QoS 1 / 2**: ahead of paho on true PUBACK/PUBCOMP (~1.2×) with RM=100.
- Isolated sprint harness (larger counts, same completion semantics): QoS1 ~48k, QoS2 ~32k — see `docs/PERF-SPRINT.md`.
- † gmqtt QoS1 drained in batches of 10 (Receive-Maximum-as-MID bug).
- ‡ gmqtt QoS2 `wait_empty` returns after PUBREC — not comparable to PUBCOMP.

## Hardening / sprint constraints kept

- No `drain()` in the writer loop (avoids deadlock vs reader enqueue of PUBREL).
- Local flow window held until PUBCOMP.
- PacketIdPool independent of Receive Maximum.

## Reproduce

```bash
mosquitto -c /tmp/mosq-bench.conf -d   # listener 11883, allow_anonymous
cd /workspace && PYTHONPATH=mqttnext/src:/tmp/gmqtt:src \
  python3 mqttnext/benchmarks/compare_libs.py
PYTHONPATH=mqttnext/src python3 mqttnext/benchmarks/perf_sprint.py --tag run
```
