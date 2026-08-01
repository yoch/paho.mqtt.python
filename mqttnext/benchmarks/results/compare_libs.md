# Comparative benchmarks

Broker: `127.0.0.1:11883` (local Mosquitto 2.0.18)  
Date: 2026-08-01  
Machine: cloud agent VM, Python 3.12

## Results (median of 3 e2e runs / 7 micro runs)

| Scenario | mqttnext | gmqtt | paho | mqttnext/gmqtt | mqttnext/paho |
| --- | ---: | ---: | ---: | ---: | ---: |
| `publish_encode_qos0_small` | 1,144,776 | 1,046,742 | 212,802 | 1.1× | 5.4× |
| `ingress_decode_50x_qos0_small` | 17,364 | n/a | n/a | — | — |
| `e2e_pub_qos0_p64` | 221,668 | 90,882 | 69,663 | **2.4×** | **3.2×** |
| `e2e_pub_qos1_p64` | 24,065 | 227.3 | 21,898 | 106×† | **1.1×** |
| `e2e_pub_qos2_p64` | 14,078 | 50,505‡ | 13,488 | 0.3×‡ | **1.0×** |

Units: msg/s (encode / e2e) or batch/s (decode of 50 concatenated packets).

## Reading

- **QoS 0 firehose**: mqttnext clearly ahead of both (≈2.4× gmqtt, ≈3.2× paho).
- **QoS 1 / 2 completion**: mqttnext matches paho (±10%). True end-to-end PUBACK/PUBCOMP wait.
- **Encode micro**: mqttnext ≈ gmqtt; both ≫ paho path that includes queue+write to a null socket.
- **Decode micro**: only mqttnext exposes an isolated incremental decoder.

## Caveats

- † gmqtt QoS1 is handicapped by its Receive-Maximum-as-MID-space bug: the
  harness must drain in batches of 10, which destroys pipelining.
- ‡ gmqtt QoS2 `wait_empty()` returns after **PUBREC** (MID freed early — known
  protocol bug). That number is **not** comparable to PUBCOMP completion.
- Inflight window capped at 20 for all clients (Mosquitto default / gmqtt limit).
- No WAN/TLS/WebSocket in this round.

## Reproduce

```bash
mosquitto -c /tmp/mosq-bench.conf -d   # listener 11883, allow_anonymous
cd /workspace && PYTHONPATH=src:/tmp/gmqtt python3 mqttnext/benchmarks/compare_libs.py
```
