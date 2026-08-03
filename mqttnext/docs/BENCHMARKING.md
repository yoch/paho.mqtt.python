# Benchmarking contract

Benchmark results are build artefacts, not source-code claims.

- `perf_sprint.py` detects local implementation regressions.
- `compare_libs.py` compares only equivalent public contracts. A library is
  reported as `N/A` instead of receiving artificial synchronization barriers.
- `realworld.py` uses fresh publisher processes plus an independent
  `mosquitto_sub`, and reports broker ACK and confirmed delivery separately.

Every result must record Python, broker, host, payload, QoS, inflight window,
transport, library versions, CPU, RSS and latency percentiles. PUBACK confirms
broker acceptance; it never proves consumer delivery.

CI uploads JSON artefacts and never commits or pushes generated numbers.
