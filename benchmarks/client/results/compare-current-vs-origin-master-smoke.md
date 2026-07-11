# Comparaison smoke core — courant vs origin/master

Même harness, même profil smoke, broker local identique.

| Version | Commit Paho | Artefact |
|---|---|---|
| **Courant** (branch benchmarks) | `08d7b1e` | `core-smoke-08d7b1e-20260711T194225Z` |
| **origin/master** | `7a3d161` | `core-smoke-origin-master-7a3d161-20260711T194959Z` |

> Δ% = (courant / master) − 1. Smoke = bruit élevé ; signes seulement si écarts gros et stables.

## Débits principaux

| Scénario / point | master msg/s | courant msg/s | Δ% | master | courant |
|---|---:|---:|---:|---|---|
| application_rtt_qos1 · payload=telemetry256 · qos=1 · cadence=loaded75 · inflight=20 · frac=0.25 | 250 | 252 | +0.8% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos=1 · cadence=loaded75 · inflight=20 · frac=0.5 | 501 | 503 | +0.4% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos=1 · cadence=loaded75 · inflight=20 · frac=0.75 | 756 | 748 | -1.1% | valid | valid |
| application_rtt_qos1 · payload=telemetry256 · qos=1 · cadence=loaded75 · inflight=20 · frac=0.9 | 890 | 900 | +1.1% | valid | valid |
| burst_recovery · payload=telemetry256 · qos=0 · cadence=burst · inflight=20 · sub=hash · topo=fleet4k_uniform | 3,881 | 3,716 | -4.3% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos=0 · cadence=burst · inflight=20 | 11,987 | 28,131 | +134.7% | valid | valid |
| duplex_gateway · payload=telemetry256 · qos=0 · cadence=steady50 · inflight=20 | 1,000 | 999 | -0.1% | valid | valid |
| e2e_integrity · payload=empty0 · qos=0 · cadence=steady50 · inflight=20 | 1,000 | 1,000 | +0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos=0 · cadence=steady50 · inflight=20 | 999 | 1,000 | +0.1% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos=1 · cadence=steady50 · inflight=20 | 1,000 | 1,000 | -0.0% | valid | valid |
| e2e_integrity · payload=telemetry256 · qos=2 · cadence=steady50 · inflight=20 | 1,000 | 1,000 | -0.0% | valid | valid |
| pub_payload_sweep_qos0 · payload=binary64 · qos=0 · cadence=capacity · inflight=20 | 12,837 | 29,592 | +130.5% | valid | valid |
| pub_payload_sweep_qos0 · payload=blob1m · qos=0 · cadence=capacity · inflight=20 | 0 | 0 | — | valid | valid |
| pub_payload_sweep_qos0 · payload=block64k · qos=0 · cadence=capacity · inflight=20 | 8,537 | 8,702 | +1.9% | valid | valid |
| pub_payload_sweep_qos0 · payload=empty0 · qos=0 · cadence=capacity · inflight=20 | 12,456 | 29,981 | +140.7% | valid | valid |
| pub_payload_sweep_qos0 · payload=event1k · qos=0 · cadence=capacity · inflight=20 | 13,915 | 30,649 | +120.3% | valid | valid |
| pub_payload_sweep_qos0 · payload=record16k · qos=0 · cadence=capacity · inflight=20 | 11,450 | 21,115 | +84.4% | valid | valid |
| pub_payload_sweep_qos0 · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 | 12,385 | 27,110 | +118.9% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos=1 · cadence=capacity · inflight=1 | 4,545 | 5,469 | +20.3% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos=1 · cadence=capacity · inflight=20 | 9,887 | 16,449 | +66.4% | valid | valid |
| pub_qos1_inflight · payload=telemetry256 · qos=1 · cadence=capacity · inflight=100 | 8,817 | 19,969 | +126.5% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 | 12,126 | 24,580 | +102.7% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos=1 · cadence=capacity · inflight=20 | 8,952 | 16,293 | +82.0% | valid | valid |
| pub_qos_sweep_telemetry · payload=telemetry256 · qos=2 · cadence=capacity · inflight=20 | 6,985 | 10,561 | +51.2% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos=1 · cadence=loaded75 · inflight=20 · frac=0.25 | 250 | 250 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos=1 · cadence=loaded75 · inflight=20 · frac=0.5 | 500 | 500 | -0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos=1 · cadence=loaded75 · inflight=20 · frac=0.75 | 750 | 750 | +0.0% | valid | valid |
| puback_latency_qos1 · payload=telemetry256 · qos=1 · cadence=loaded75 · inflight=20 · frac=0.9 | 900 | 900 | -0.0% | valid | valid |
| remaining_length_boundaries · payload=rl_126 · qos=0 · cadence=capacity · inflight=20 | 12,777 | 29,076 | +127.6% | valid | valid |
| remaining_length_boundaries · payload=rl_127 · qos=0 · cadence=capacity · inflight=20 | 12,781 | 29,522 | +131.0% | valid | valid |
| remaining_length_boundaries · payload=rl_128 · qos=0 · cadence=capacity · inflight=20 | 13,006 | 28,089 | +116.0% | valid | valid |
| remaining_length_boundaries · payload=rl_16383 · qos=0 · cadence=capacity · inflight=20 | 11,305 | 21,193 | +87.5% | valid | valid |
| remaining_length_boundaries · payload=rl_16384 · qos=0 · cadence=capacity · inflight=20 | 11,691 | 21,508 | +84.0% | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 · sub=hash · topo=fleet4k_uniform · cb=1 | 0 | 0 | — | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 · sub=hash · topo=fleet4k_uniform · cb=16 | 0 | 0 | — | valid | valid |
| sub_callback_matching · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 · sub=hash · topo=fleet4k_uniform · cb=256 | 0 | 0 | — | valid | valid |
| sub_exact_telemetry · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 | 3,771 | 3,656 | -3.1% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 · sub=hash · topo=fleet4k_uniform | 3,970 | 3,231 | -18.6% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 · sub=hash · topo=fleet4k_zipf | 3,885 | 3,730 | -4.0% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 · sub=plus · topo=fleet4k_uniform | 3,831 | 3,679 | -4.0% | valid | valid |
| sub_hierarchy_telemetry · payload=telemetry256 · qos=0 · cadence=capacity · inflight=20 · sub=plus · topo=fleet4k_zipf | 3,765 | 3,768 | +0.1% | valid | valid |
