# Différentiels benchmark client — smoke core depuis plan 1

- Timestamp UTC: `20260712T103742Z`
- Profil: `smoke` · suite: `core` · seed: `42`
- Harness: branche `benchmarks` (fixe) · SUT via `--source` worktrees
- Δ% = (commit / précédent) − 1 sur médiane `msgs/s` du point
- Smoke = bruit élevé ; signes seulement si écarts gros et stables

## Index des commits

| # | SHA | Sujet | Artefact |
|---:|---|---|---|
| 0 | `a734a9c` | baseline pre-optimisations (parent of 238eee8) | `core-smoke-a734a9c-20260712T103742Z` |
| 1 | `f2aaa76` | perf: cache MQTT v5 property metadata lookups | `core-smoke-f2aaa76-20260712T103742Z` |
| 2 | `92008c1` | perf: reduce receive message dispatch overhead | `core-smoke-92008c1-20260712T103742Z` |
| 3 | `6f6869c` | perf: reduce publish write-path overhead | `core-smoke-6f6869c-20260712T103742Z` |
| 4 | `65e1671` | fix: avoid missed sockpair wakeup during loop_start | `core-smoke-65e1671-20260712T103742Z` |
| 5 | `6bb33c5` | perf: fast-path small remaining length encoding | `core-smoke-6bb33c5-20260712T103742Z` |
| 6 | `90afdb9` | perf: speed up inbound packet parse path (plan 01) | `core-smoke-90afdb9-20260712T103742Z` |
| 7 | `5bbbd95` | perf: micro-optimize MQTTMatcher.iter_match | `core-smoke-5bbbd95-20260712T103742Z` |
| 8 | `4e5221b` | perf: skip PUBLISH topic decode when logging is disabled | `core-smoke-4e5221b-20260712T103742Z` |
| 9 | `9e502e7` | perf: speed up rich MQTT v5 property decoding | `core-smoke-9e502e7-20260712T103742Z` |
| 10 | `07e6cd9` | perf: optimize network hot paths | `core-smoke-07e6cd9-20260712T103742Z` |
| 11 | `7c33f50` | perf: decode buffered packets directly | `core-smoke-7c33f50-20260712T103742Z` |
| 12 | `8011c9f` | perf: batch inflight refill after ACK bursts | `core-smoke-8011c9f-20260712T103742Z` |
| 13 | `be0d5b2` | perf: stage reconnect replay in bounded batches | `core-smoke-be0d5b2-20260712T103742Z` |
| 14 | `6634d03` | perf: segment large immutable publish payloads | `core-smoke-6634d03-20260712T103742Z` |

## Résumé des pas (Δ% médian sur points capacity publish)

| Pas | Prev → Curr | Δ% médian (capacity pub*) | Points valid curr |
|---|---|---:|---:|
| 0→1 | `a734a9c` → `f2aaa76` | +35.9% | 39/41 |
| 1→2 | `f2aaa76` → `92008c1` | +5.4% | 39/41 |
| 2→3 | `92008c1` → `6f6869c` | +24.5% | 39/41 |
| 3→4 | `6f6869c` → `65e1671` | +1.2% | 39/41 |
| 4→5 | `65e1671` → `6bb33c5` | +6.9% | 39/41 |
| 5→6 | `6bb33c5` → `90afdb9` | +4.4% | 39/41 |
| 6→7 | `90afdb9` → `5bbbd95` | -0.8% | 39/41 |
| 7→8 | `5bbbd95` → `4e5221b` | +2.3% | 39/41 |
| 8→9 | `4e5221b` → `9e502e7` | -11.0% | 39/41 |
| 9→10 | `9e502e7` → `07e6cd9` | +2.0% | 39/41 |
| 10→11 | `07e6cd9` → `7c33f50` | -8.9% | 39/41 |
| 11→12 | `7c33f50` → `8011c9f` | +34.7% | 39/41 |
| 12→13 | `8011c9f` → `be0d5b2` | -1.4% | 39/41 |
| 13→14 | `be0d5b2` → `6634d03` | -5.3% | 39/41 |

\* Points dont la clé contient `cadence=capacity` et un scénario `pub_*` / `remaining_length*` / `duplex_*`.

## Pas 0→1: `a734a9c` → `f2aaa76`

- **Précédent:** `a734a9c` — baseline pre-optimisations (parent of 238eee8)
- **Courant:** `f2aaa76` — perf: cache MQTT v5 property metadata lookups
- **Δ% médian (capacity pub*):** +35.9%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 249.3 | 253.0 | +1.5% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 497.7 | 500.6 | +0.6% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 756.3 | 743.3 | -1.7% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 903.0 | 900.7 | -0.3% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | +0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 851.4 | 1,582 | +85.8% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 999.1 | -0.1% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.0 | 999.2 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 998.8 | 999.6 | +0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 12,483 | 18,517 | +48.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 791.6 | 641.5 | -19.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,458 | 5,414 | -36.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 12,868 | 20,051 | +55.8% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,581 | 19,815 | +35.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,992 | 16,032 | +33.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 12,523 | 20,179 | +61.1% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 4,297 | 5,146 | +19.8% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,656 | 10,991 | +27.0% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 9,645 | 11,903 | +23.4% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,542 | 16,989 | +61.1% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,052 | 11,979 | +19.2% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 7,955 | 8,580 | +7.8% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 250.0 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.7 | 499.7 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 750.0 | 749.7 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | +0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,374 | 18,273 | +60.7% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,654 | 19,847 | +70.3% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,927 | 18,096 | +51.7% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,670 | 14,998 | +28.5% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 9,433 | 15,548 | +64.8% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,319 | 5,149 | -3.2% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 5,345 | 5,047 | -5.6% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,978 | 4,838 | -2.8% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,075 | 4,331 | -14.7% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,348 | 4,356 | -18.5% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,107 | 4,419 | -13.5% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 1→2: `f2aaa76` → `92008c1`

- **Précédent:** `f2aaa76` — perf: cache MQTT v5 property metadata lookups
- **Courant:** `92008c1` — perf: reduce receive message dispatch overhead
- **Δ% médian (capacity pub*):** +5.4%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 253.0 | 252.3 | -0.3% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 500.6 | 502.7 | +0.4% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 743.3 | 755.3 | +1.6% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 900.7 | 893.6 | -0.8% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | -0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,582 | 1,623 | +2.6% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.1 | 1,000.0 | +0.1% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.2 | 1,000.0 | +0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 18,517 | 21,898 | +18.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 641.5 | 746.2 | +16.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,414 | 9,110 | +68.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,051 | 20,691 | +3.2% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 19,815 | 17,186 | -13.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,032 | 16,896 | +5.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,179 | 21,975 | +8.9% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,146 | 5,159 | +0.2% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,991 | 11,344 | +3.2% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,903 | 12,131 | +1.9% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,989 | 20,687 | +21.8% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,979 | 10,380 | -13.4% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,580 | 8,988 | +4.8% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 250.0 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.7 | 500.0 | +0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.7 | 749.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | -0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 18,273 | 21,518 | +17.8% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 19,847 | 20,689 | +4.2% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 18,096 | 20,891 | +15.4% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,998 | 14,705 | -2.0% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 15,548 | 17,340 | +11.5% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,149 | 5,304 | +3.0% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 5,047 | 5,185 | +2.7% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,838 | 5,019 | +3.7% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 4,331 | 5,314 | +22.7% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,356 | 5,321 | +22.1% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,419 | 5,272 | +19.3% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 2→3: `92008c1` → `6f6869c`

- **Précédent:** `92008c1` — perf: reduce receive message dispatch overhead
- **Courant:** `6f6869c` — perf: reduce publish write-path overhead
- **Δ% médian (capacity pub*):** +24.5%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 252.3 | 251.7 | -0.3% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 502.7 | 499.3 | -0.7% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 755.3 | 747.6 | -1.0% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 893.6 | 903.3 | +1.1% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | +0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,623 | 2,283 | +40.7% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.5 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,898 | 28,450 | +29.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 746.2 | 726.2 | -2.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 9,110 | 6,330 | -30.5% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,691 | 30,584 | +47.8% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 17,186 | 29,827 | +73.6% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,896 | 20,563 | +21.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,975 | 27,151 | +23.6% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,159 | 5,353 | +3.8% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,344 | 14,126 | +24.5% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 12,131 | 10,764 | -11.3% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,687 | 18,515 | -10.5% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,380 | 10,161 | -2.1% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,988 | 3,684 | -59.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 250.0 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 500.0 | 500.0 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | +0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,518 | 27,731 | +28.9% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,689 | 29,044 | +40.4% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,891 | 28,476 | +36.3% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,705 | 20,573 | +39.9% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 17,340 | 23,163 | +33.6% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,304 | 5,351 | +0.9% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 5,185 | 5,324 | +2.7% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 5,019 | 5,013 | -0.1% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,314 | 5,272 | -0.8% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,321 | 5,332 | +0.2% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,272 | 5,278 | +0.1% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 3→4: `6f6869c` → `65e1671`

- **Précédent:** `6f6869c` — perf: reduce publish write-path overhead
- **Courant:** `65e1671` — fix: avoid missed sockpair wakeup during loop_start
- **Δ% médian (capacity pub*):** +1.2%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 251.7 | 248.3 | -1.3% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.3 | 502.0 | +0.5% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 747.6 | 761.0 | +1.8% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 903.3 | 903.0 | -0.0% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | +0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,283 | 2,319 | +1.6% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 999.6 | -0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.5 | 999.6 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,450 | 28,558 | +0.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 726.2 | 495.3 | -31.8% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 6,330 | 7,620 | +20.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,584 | 23,480 | -23.2% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,827 | 16,780 | -43.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,563 | 14,095 | -31.5% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,151 | 26,946 | -0.8% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,353 | 5,500 | +2.7% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,126 | 11,812 | -16.4% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,764 | 11,761 | +9.3% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 18,515 | 26,493 | +43.1% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,161 | 12,360 | +21.6% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 3,684 | 8,240 | +123.6% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 249.8 | -0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 500.0 | 500.0 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | +0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,731 | 29,419 | +6.1% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,044 | 28,365 | -2.3% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,476 | 28,811 | +1.2% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,573 | 22,223 | +8.0% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 23,163 | 22,254 | -3.9% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,351 | 4,697 | -12.2% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 5,324 | 4,903 | -7.9% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 5,013 | 4,929 | -1.7% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,272 | 5,194 | -1.5% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,332 | 4,647 | -12.8% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,278 | 5,109 | -3.2% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 4→5: `65e1671` → `6bb33c5`

- **Précédent:** `65e1671` — fix: avoid missed sockpair wakeup during loop_start
- **Courant:** `6bb33c5` — perf: fast-path small remaining length encoding
- **Δ% médian (capacity pub*):** +6.9%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 248.3 | 248.3 | +0.0% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 502.0 | 506.7 | +0.9% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 761.0 | 752.6 | -1.1% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 903.0 | 889.6 | -1.5% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | -0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,319 | 2,599 | +12.1% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 999.1 | -0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,558 | 27,628 | -3.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 495.3 | 574.3 | +16.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 7,620 | 6,144 | -19.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 23,480 | 30,128 | +28.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,780 | 30,757 | +83.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,095 | 21,142 | +50.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 26,946 | 25,599 | -5.0% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,500 | 5,372 | -2.3% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,812 | 14,189 | +20.1% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,761 | 13,668 | +16.2% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 26,493 | 24,003 | -9.4% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 12,360 | 14,350 | +16.1% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,240 | 10,255 | +24.5% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 249.8 | 250.0 | +0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 500.0 | 499.7 | -0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | +0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,419 | 27,178 | -7.6% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,365 | 30,330 | +6.9% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,811 | 28,179 | -2.2% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,223 | 22,732 | +2.3% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,254 | 19,729 | -11.3% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 4,697 | 5,141 | +9.5% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 4,903 | 4,811 | -1.9% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,929 | 4,974 | +0.9% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,194 | 4,766 | -8.2% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,647 | 5,090 | +9.5% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,109 | 4,823 | -5.6% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 5→6: `6bb33c5` → `90afdb9`

- **Précédent:** `6bb33c5` — perf: fast-path small remaining length encoding
- **Courant:** `90afdb9` — perf: speed up inbound packet parse path (plan 01)
- **Δ% médian (capacity pub*):** +4.4%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 248.3 | 248.3 | -0.0% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 506.7 | 505.3 | -0.3% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 752.6 | 748.3 | -0.6% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 889.6 | 895.3 | +0.6% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 4,996 | -0.1% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,599 | 2,152 | -17.2% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 999.2 | -0.1% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.1 | 999.3 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,628 | 28,866 | +4.5% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 574.3 | 610.9 | +6.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 6,144 | 7,428 | +20.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,128 | 30,034 | -0.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,757 | 29,047 | -5.6% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,142 | 20,792 | -1.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 25,599 | 27,954 | +9.2% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,372 | 5,490 | +2.2% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,189 | 13,411 | -5.5% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 13,668 | 13,704 | +0.3% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 24,003 | 28,012 | +16.7% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,350 | 14,984 | +4.4% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,255 | 10,772 | +5.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 249.8 | -0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.7 | 500.0 | +0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | -0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,178 | 29,552 | +8.7% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,330 | 29,539 | -2.6% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,179 | 27,248 | -3.3% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,732 | 22,540 | -0.8% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 19,729 | 21,797 | +10.5% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,141 | 4,929 | -4.1% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 4,811 | 4,987 | +3.6% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,974 | 4,918 | -1.1% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 4,766 | 4,181 | -12.3% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,090 | 4,906 | -3.6% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,823 | 4,839 | +0.3% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 6→7: `90afdb9` → `5bbbd95`

- **Précédent:** `90afdb9` — perf: speed up inbound packet parse path (plan 01)
- **Courant:** `5bbbd95` — perf: micro-optimize MQTTMatcher.iter_match
- **Δ% médian (capacity pub*):** -0.8%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 248.3 | 248.0 | -0.1% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 505.3 | 509.7 | +0.9% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 748.3 | 750.6 | +0.3% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 895.3 | 894.1 | -0.1% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,996 | 5,000 | +0.1% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,152 | 2,376 | +10.4% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.2 | 1,000.0 | +0.1% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.3 | 999.3 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 999.9 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 998.6 | -0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,866 | 26,828 | -7.1% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 610.9 | 489.0 | -20.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 7,428 | 8,090 | +8.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,034 | 30,881 | +2.8% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,047 | 28,171 | -3.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,792 | 20,637 | -0.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,954 | 27,914 | -0.1% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,490 | 5,341 | -2.7% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 13,411 | 12,989 | -3.1% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 13,704 | 13,766 | +0.5% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,012 | 27,783 | -0.8% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,984 | 13,019 | -13.1% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,772 | 11,112 | +3.2% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 249.8 | 250.0 | +0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 500.0 | 499.7 | -0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | -0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,552 | 29,321 | -0.8% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,539 | 29,041 | -1.7% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,248 | 29,823 | +9.4% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,540 | 19,525 | -13.4% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,797 | 21,194 | -2.8% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 4,929 | 3,553 | -27.9% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 4,987 | 4,346 | -12.8% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,918 | 4,988 | +1.4% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 4,181 | 5,167 | +23.6% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,906 | 5,262 | +7.3% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,839 | 5,299 | +9.5% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 7→8: `5bbbd95` → `4e5221b`

- **Précédent:** `5bbbd95` — perf: micro-optimize MQTTMatcher.iter_match
- **Courant:** `4e5221b` — perf: skip PUBLISH topic decode when logging is disabled
- **Δ% médian (capacity pub*):** +2.3%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 248.0 | 249.0 | +0.4% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 509.7 | 498.7 | -2.2% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 750.6 | 752.0 | +0.2% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 894.1 | 896.3 | +0.2% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | -0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,376 | 2,852 | +20.1% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.3 | 1,000.0 | +0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.9 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 998.6 | 999.6 | +0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 26,828 | 28,938 | +7.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 489.0 | 717.0 | +46.6% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,090 | 8,658 | +7.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,881 | 31,245 | +1.2% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,171 | 30,576 | +8.5% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,637 | 21,141 | +2.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,914 | 26,585 | -4.8% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,341 | 5,301 | -0.7% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 12,989 | 13,289 | +2.3% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 13,766 | 15,144 | +10.0% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,783 | 28,803 | +3.7% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 13,019 | 14,887 | +14.4% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,112 | 7,832 | -29.5% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 250.0 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.7 | 499.7 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | +0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,321 | 27,876 | -4.9% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,041 | 29,406 | +1.3% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,823 | 27,574 | -7.5% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 19,525 | 17,133 | -12.3% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,194 | 19,881 | -6.2% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 3,553 | 5,237 | +47.4% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 4,346 | 5,031 | +15.8% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,988 | 5,008 | +0.4% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,167 | 5,095 | -1.4% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,262 | 5,095 | -3.2% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,299 | 5,058 | -4.6% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 8→9: `4e5221b` → `9e502e7`

- **Précédent:** `4e5221b` — perf: skip PUBLISH topic decode when logging is disabled
- **Courant:** `9e502e7` — perf: speed up rich MQTT v5 property decoding
- **Δ% médian (capacity pub*):** -11.0%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 249.0 | 248.3 | -0.3% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 498.7 | 500.3 | +0.3% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 752.0 | 752.6 | +0.1% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 896.3 | 886.3 | -1.1% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | +0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,852 | 2,242 | -21.4% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | -0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 998.9 | -0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,938 | 24,978 | -13.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 717.0 | 523.2 | -27.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,658 | 7,961 | -8.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 31,245 | 29,225 | -6.5% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,576 | 26,509 | -13.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,141 | 20,455 | -3.2% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 26,585 | 24,347 | -8.4% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,301 | 4,691 | -11.5% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 13,289 | 11,829 | -11.0% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 15,144 | 12,193 | -19.5% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,803 | 25,297 | -12.2% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,887 | 10,833 | -27.2% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 7,832 | 7,328 | -6.4% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 250.0 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.7 | 499.7 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | +0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,876 | 25,596 | -8.2% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,406 | 24,325 | -17.3% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,574 | 26,193 | -5.0% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 17,133 | 18,558 | +8.3% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 19,881 | 14,215 | -28.5% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,237 | 4,605 | -12.1% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 5,031 | 4,521 | -10.1% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 5,008 | 4,865 | -2.8% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,095 | 4,225 | -17.1% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,095 | 4,496 | -11.8% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,058 | 4,890 | -3.3% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 9→10: `9e502e7` → `07e6cd9`

- **Précédent:** `9e502e7` — perf: speed up rich MQTT v5 property decoding
- **Courant:** `07e6cd9` — perf: optimize network hot paths
- **Δ% médian (capacity pub*):** +2.0%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 248.3 | 254.3 | +2.4% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 500.3 | 495.3 | -1.0% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 752.6 | 746.6 | -0.8% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 886.3 | 913.0 | +3.0% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 4,184 | -16.3% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,242 | 1,805 | -19.5% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | -0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 998.9 | 1,000.0 | +0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 998.9 | -0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 24,978 | 20,224 | -19.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 523.2 | 472.1 | -9.8% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 7,961 | 8,217 | +3.2% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,225 | 21,288 | -27.2% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 26,509 | 25,594 | -3.5% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,455 | 16,557 | -19.1% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 24,347 | 22,440 | -7.8% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 4,691 | 5,660 | +20.7% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,829 | 14,845 | +25.5% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 12,193 | 15,129 | +24.1% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 25,297 | 27,659 | +9.3% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,833 | 15,223 | +40.5% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 7,328 | 10,677 | +45.7% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 250.0 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.7 | 499.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.7 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | -0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 25,596 | 21,684 | -15.3% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 24,325 | 22,591 | -7.1% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 26,193 | 22,351 | -14.7% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 18,558 | 18,927 | +2.0% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,215 | 14,611 | +2.8% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 4,605 | 2,985 | -35.2% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 4,521 | 4,061 | -10.2% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,865 | 4,108 | -15.6% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 4,225 | 3,932 | -6.9% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,496 | 2,516 | -44.0% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,890 | 2,777 | -43.2% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 10→11: `07e6cd9` → `7c33f50`

- **Précédent:** `07e6cd9` — perf: optimize network hot paths
- **Courant:** `7c33f50` — perf: decode buffered packets directly
- **Δ% médian (capacity pub*):** -8.9%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 254.3 | 250.7 | -1.4% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 495.3 | 499.7 | +0.9% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 746.6 | 744.2 | -0.3% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 913.0 | 902.3 | -1.2% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,184 | 5,000 | +19.5% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,805 | 2,022 | +12.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 998.9 | 1,000.0 | +0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,224 | 27,179 | +34.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 472.1 | 228.6 | -51.6% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,217 | 5,005 | -39.1% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,288 | 21,012 | -1.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 25,594 | 22,192 | -13.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,557 | 16,067 | -3.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,440 | 22,381 | -0.3% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,660 | 4,674 | -17.4% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,845 | 16,154 | +8.8% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 15,129 | 9,852 | -34.9% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,659 | 13,062 | -52.8% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 15,223 | 11,585 | -23.9% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,677 | 3,953 | -63.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 249.7 | -0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.6 | 500.0 | +0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.7 | 749.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | +0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,684 | 28,525 | +31.6% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,591 | 19,076 | -15.6% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,351 | 28,166 | +26.0% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 18,927 | 17,238 | -8.9% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 14,611 | 15,499 | +6.1% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 2,985 | 5,211 | +74.5% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 4,061 | 5,150 | +26.8% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,108 | 5,002 | +21.7% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 3,932 | 5,243 | +33.3% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 2,516 | 5,220 | +107.5% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 2,777 | 5,054 | +82.0% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 11→12: `7c33f50` → `8011c9f`

- **Précédent:** `7c33f50` — perf: decode buffered packets directly
- **Courant:** `8011c9f` — perf: batch inflight refill after ACK bursts
- **Δ% médian (capacity pub*):** +34.7%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.7 | 249.0 | -0.7% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.7 | 501.7 | +0.4% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 744.2 | 755.9 | +1.6% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 902.3 | 904.0 | +0.2% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | +0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,022 | 2,083 | +3.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 999.0 | -0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,179 | 29,412 | +8.2% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 228.6 | 592.2 | +159.1% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,005 | 8,507 | +70.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,012 | 29,611 | +40.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,192 | 28,606 | +28.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,067 | 21,635 | +34.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,381 | 28,752 | +28.5% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 4,674 | 5,831 | +24.8% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,154 | 21,511 | +33.2% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 9,852 | 15,415 | +56.5% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 13,062 | 28,312 | +116.8% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,585 | 15,112 | +30.4% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 3,953 | 11,825 | +199.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 249.7 | 250.0 | +0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 500.0 | 499.6 | -0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | -0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,525 | 29,704 | +4.1% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 19,076 | 30,304 | +58.9% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,166 | 22,922 | -18.6% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 17,238 | 21,422 | +24.3% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 15,499 | 22,318 | +44.0% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,211 | 5,114 | -1.9% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 5,150 | 5,213 | +1.2% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 5,002 | 5,046 | +0.9% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,243 | 5,037 | -3.9% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,220 | 5,240 | +0.4% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,054 | 5,194 | +2.8% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 12→13: `8011c9f` → `be0d5b2`

- **Précédent:** `8011c9f` — perf: batch inflight refill after ACK bursts
- **Courant:** `be0d5b2` — perf: stage reconnect replay in bounded batches
- **Δ% médian (capacity pub*):** -1.4%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 249.0 | 250.6 | +0.7% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 501.7 | 505.3 | +0.7% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 755.9 | 755.3 | -0.1% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 904.0 | 897.3 | -0.7% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 5,000 | -0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,083 | 2,565 | +23.2% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.0 | 999.9 | +0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | +0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,412 | 26,928 | -8.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 592.2 | 641.7 | +8.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 8,507 | 7,188 | -15.5% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,611 | 26,831 | -9.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,606 | 30,259 | +5.8% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,635 | 21,259 | -1.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,752 | 29,233 | +1.7% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,831 | 5,809 | -0.4% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,511 | 19,893 | -7.5% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 15,415 | 17,205 | +11.6% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,312 | 27,915 | -1.4% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 15,112 | 16,639 | +10.1% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 11,825 | 10,207 | -13.7% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 250.0 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.6 | 499.7 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | -0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,704 | 16,697 | -43.8% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,304 | 28,229 | -6.8% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,922 | 27,078 | +18.1% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,422 | 21,328 | -0.4% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 22,318 | 20,105 | -9.9% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,114 | 5,169 | +1.1% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 5,213 | 5,094 | -2.3% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 5,046 | 4,763 | -5.6% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,037 | 3,473 | -31.0% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,240 | 4,939 | -5.7% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,194 | 4,409 | -15.1% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Pas 13→14: `be0d5b2` → `6634d03`

- **Précédent:** `be0d5b2` — perf: stage reconnect replay in bounded batches
- **Courant:** `6634d03` — perf: segment large immutable publish payloads
- **Δ% médian (capacity pub*):** -5.3%

| Point | prev msg/s | curr msg/s | Δ% | prev | curr |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.6 | 247.7 | -1.2% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 505.3 | 501.0 | -0.9% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 755.3 | 746.7 | -1.1% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 897.3 | 899.3 | +0.2% | valid | valid |
| burst_recovery · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=burst · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 5,000 | 4,998 | -0.0% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=burst · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 2,565 | 2,338 | -8.9% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos_publish=0 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 999.0 | -0.1% | valid | valid |
| e2e_integrity · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.9 | 1,000.0 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 1,000.0 | 999.1 | -0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=1 · qos_subscribe=1 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos_publish=2 · qos_subscribe=2 · cadence=steady50 · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 999.6 | 999.6 | -0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 26,928 | 24,817 | -7.8% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 641.7 | 539.9 | -15.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 7,188 | 7,135 | -0.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 26,831 | 29,418 | +9.6% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 30,259 | 25,423 | -16.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,259 | 16,975 | -20.2% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 29,233 | 23,902 | -18.2% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=1 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 5,809 | 5,569 | -4.1% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=100 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 19,893 | 21,800 | +9.6% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 17,205 | 17,357 | +0.9% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,915 | 20,921 | -25.1% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,639 | 13,645 | -18.0% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos_publish=2 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 10,207 | 11,361 | +11.3% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.25 · protocol=MQTTv311 | 250.0 | 250.0 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.5 · protocol=MQTTv311 | 499.7 | 500.0 | +0.1% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.75 · protocol=MQTTv311 | 749.6 | 749.6 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos_publish=1 · qos_subscribe=0 · cadence=loaded75 · inflight=20 · subscription=exact · topic_topology=single · load_fraction=0.9 · protocol=MQTTv311 | 899.6 | 899.6 | +0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 16,697 | 25,414 | +52.2% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 28,229 | 27,460 | -2.7% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 27,078 | 25,283 | -6.6% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 21,328 | 20,194 | -5.3% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 20,105 | 9,899 | -50.8% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=1 · protocol=MQTTv311 | 5,169 | 5,160 | -0.2% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=16 · protocol=MQTTv311 | 5,094 | 5,153 | +1.2% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · callback_filters=256 · protocol=MQTTv311 | 4,763 | 4,955 | +4.0% | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=exact · topic_topology=single · protocol=MQTTv311 | 3,473 | 3,885 | +11.9% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,939 | 4,297 | -13.0% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=hash · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_uniform · protocol=MQTTv311 | 4,409 | 4,569 | +3.6% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos_publish=0 · qos_subscribe=0 · cadence=capacity · inflight=20 · subscription=plus · topic_topology=fleet4k_zipf · protocol=MQTTv311 | — | — | — | inconclusive | inconclusive |

## Caveats

- Profil `smoke`: fenêtres courtes, 1 run/point, marqué non comparable pour verdicts fins.
- Même harness, même broker local, seed 42 ; charge machine non contrôlée finement.
- Les points `inconclusive` / `not_implemented:*` n'ont pas de taux fiable (affichés —).
