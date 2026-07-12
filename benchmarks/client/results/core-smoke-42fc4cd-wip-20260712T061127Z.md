# Benchmark client Paho — baseline courante

Profil **smoke** (non comparable pour A/B sérieux), suite **core**, 1 run/point.

## Contexte

| Champ | Valeur |
|---|---|
| Source Paho | `current-42fc4cd-wip` |
| Source root | `/home/yoch/paho.mqtt.python` |
| Suite / profil | `core` / smoke |
| Points | 41 (39 valid, 2 inconclusive) |
| Python | None |
| CPU | Intel(R) Core(TM) i7-3770 CPU @ 3.40GHz |
| Plateforme | Linux-6.8.0-134-lowlatency-x86_64-with-glibc2.39 |
| Artefact brut | `core-smoke-42fc4cd-wip-20260712T061127Z.json` |
| Résumé JSON | `core-smoke-42fc4cd-wip-20260712T061127Z.summary.json` |

| Scénario / point | status | msg/s | reasons |
|---|---|---:|---|
| `pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 29,129 |  |
| `pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 30,276 |  |
| `pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 20,516 |  |
| `pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 27,857 |  |
| `pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 659 |  |
| `pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 29,703 |  |
| `pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 8,628 |  |
| `pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 16,480 |  |
| `pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 27,635 |  |
| `pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 11,308 |  |
| `pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 15,489 |  |
| `pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single` | valid | 5,603 |  |
| `pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single` | valid | 20,896 |  |
| `remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 21,180 |  |
| `remaining_length_boundaries · payload=rl_127 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 29,131 |  |
| `remaining_length_boundaries · payload=rl_128 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 27,847 |  |
| `remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 21,182 |  |
| `remaining_length_boundaries · payload=rl_126 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 29,471 |  |
| `sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single` | valid | 5,265 |  |
| `sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf` | inconclusive | — | not_implemented:topic_topology:fleet4k_zipf |
| `sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform` | valid | 5,330 |  |
| `sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf` | inconclusive | — | not_implemented:topic_topology:fleet4k_zipf |
| `sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform` | valid | 5,357 |  |
| `sub_callback_matching · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16` | valid | 5,279 |  |
| `sub_callback_matching · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1` | valid | 5,331 |  |
| `sub_callback_matching · payload=telemetry256 · qos_publish=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256` | valid | 5,039 |  |
| `duplex_gateway · payload=telemetry256 · qos_publish=0 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single` | valid | 2,013 |  |
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
| `application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75` | valid | 751 |  |
| `application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5` | valid | 499 |  |
| `application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9` | valid | 905 |  |
| `application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25` | valid | 251 |  |
