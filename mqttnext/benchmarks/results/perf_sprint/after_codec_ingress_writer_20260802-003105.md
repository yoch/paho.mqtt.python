# Perf sprint — `after_codec_ingress_writer`

Date: 20260802-003105

| Track | Name | Rate | Unit | Notes |
| --- | --- | ---: | --- | --- |
| A | `encode_qos0_mqtt311` | 1,051,975.7 | msg/s |  |
| A | `encode_qos1_mqtt311` | 983,223.0 | msg/s |  |
| A | `encode_qos0_mqtt5_empty_props` | 923,600.9 | msg/s |  |
| A | `decode_qos0_mqtt311` | 387,301.9 | msg/s |  |
| A | `decode_qos0_mqtt5_empty_props` | 355,653.8 | msg/s |  |
| B | `ingress_decode_50x` | 17,678.5 | batch/s |  |
| B | `ingress_decode_500x` | 1,783.0 | batch/s |  |
| B | `ingress_engine_50x_qos0` | 3,602.6 | batch/s |  |
