# Perf sprint — `after_append_encode`

Date: 20260802-003222

| Track | Name | Rate | Unit | Notes |
| --- | --- | ---: | --- | --- |
| A | `encode_qos0_mqtt311` | 1,315,894.7 | msg/s |  |
| A | `encode_qos1_mqtt311` | 1,250,069.5 | msg/s |  |
| A | `encode_qos0_mqtt5_empty_props` | 1,293,803.4 | msg/s |  |
| A | `decode_qos0_mqtt311` | 395,388.5 | msg/s |  |
| A | `decode_qos0_mqtt5_empty_props` | 361,359.2 | msg/s |  |
| B | `ingress_decode_50x` | 17,520.6 | batch/s |  |
| B | `ingress_decode_500x` | 1,792.6 | batch/s |  |
| B | `ingress_engine_50x_qos0` | 3,605.0 | batch/s |  |
