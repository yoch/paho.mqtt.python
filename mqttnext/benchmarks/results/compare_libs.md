# Comparative benchmarks

Broker: `127.0.0.1:11883` (local Mosquitto)

| Scenario | mqttnext | gmqtt | paho | mqttnext/gmqtt | mqttnext/paho |
| --- | ---: | ---: | ---: | ---: | ---: |
| `publish_encode_qos0_small` | 1,018,737 | 1,033,001 | n/a | 1.0× | n/a× |
| `ingress_decode_50x_qos0_small` | 17,986 | n/a | n/a | n/a× | n/a× |
| `e2e_puback_qos1_p64_w10` | 30,111 | 227.3 | 31,534 | 132.5× | 1.0× |

Notes:
- Paho is N/A for codec encode because it has no isolated codec API.
- Micro decode is mqttnext-only (gmqtt/paho parsers are not isolatable).
- Comparative E2E is limited to QoS 1, completed after PUBACK.
- All libraries use the same outbound inflight window.
- Execution order rotates between runs to reduce warm-up/order bias.
- QoS 0 and gmqtt QoS 2 are excluded because completion semantics differ.

