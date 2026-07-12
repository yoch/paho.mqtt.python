# Benchmark client Paho — origin/master

Profil **smoke** (non comparable pour A/B sérieux), suite **core**, 1 run/point.

## Contexte

| Champ | Valeur |
|---|---|
| Source Paho | `origin/master-7a3d161` |
| Source root | `/tmp/paho-origin-master-wt` |
| Suite / profil | `core` / smoke |
| Points | 41 (39 valid, 2 inconclusive) |
| Python | None |
| CPU | Intel(R) Core(TM) i7-3770 CPU @ 3.40GHz |
| Plateforme | Linux-6.8.0-134-lowlatency-x86_64-with-glibc2.39 |
| Artefact brut | `core-smoke-origin-master-7a3d161-20260712T061127Z.json` |
| Résumé JSON | `core-smoke-origin-master-7a3d161-20260712T061127Z.summary.json` |

| Scénario / point | status | msg/s | reasons |
|---|---|---:|---|
| `pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 11,852 |  |
| `pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 13,486 |  |
| `pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 11,028 |  |
| `pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 11,958 |  |
| `pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 618 |  |
| `pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 12,634 |  |
| `pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 8,138 |  |
| `pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 8,755 |  |
| `pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 12,031 |  |
| `pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 7,081 |  |
| `pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 9,496 |  |
| `pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single` | valid | 4,512 |  |
| `pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single` | valid | 9,064 |  |
| `remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 10,878 |  |
| `remaining_length_boundaries · payload=rl_127 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 12,551 |  |
| `remaining_length_boundaries · payload=rl_128 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 12,068 |  |
| `remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 11,796 |  |
| `remaining_length_boundaries · payload=rl_126 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 13,032 |  |
| `sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 5,382 |  |
| `sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf` | inconclusive | — | not_implemented:topic_topology:fleet4k_zipf |
| `sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform` | valid | 5,199 |  |
| `sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf` | inconclusive | — | not_implemented:topic_topology:fleet4k_zipf |
| `sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform` | valid | 5,295 |  |
| `sub_callback_matching · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16` | valid | 5,310 |  |
| `sub_callback_matching · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1` | valid | 5,300 |  |
| `sub_callback_matching · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256` | valid | 5,013 |  |
| `duplex_gateway · payload=telemetry256 · qos_publish=0 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single` | valid | 848 |  |
| `duplex_gateway · payload=telemetry256 · qos_publish=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single` | valid | 1,000 |  |
| `burst_recovery · payload=telemetry256 · qos_publish=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform` | valid | 5,000 |  |
| `e2e_integrity · payload=telemetry256 · qos_publish=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single` | valid | 1,000 |  |
| `e2e_integrity · payload=telemetry256 · qos_publish=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single` | valid | 1,000 |  |
| `e2e_integrity · payload=empty0 · qos_publish=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single` | valid | 1,000 |  |
| `e2e_integrity · payload=telemetry256 · qos_publish=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single` | valid | 1,000 |  |
| `puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75` | valid | 750 |  |
| `puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5` | valid | 500 |  |
| `puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9` | valid | 900 |  |
| `puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25` | valid | 250 |  |
| `application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75` | valid | 746 |  |
| `application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5` | valid | 504 |  |
| `application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9` | valid | 906 |  |
| `application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25` | valid | 252 |  |
