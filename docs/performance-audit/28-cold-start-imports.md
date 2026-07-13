# 28 - Cold Start and Imports

## Analysis

Importing `paho.mqtt.client` eagerly imports `urllib.parse` and
`urllib.request`, although they are used only by private proxy discovery.
Typical installations without PySocks return from that proxy path immediately,
so importing the relatively large `urllib.request` graph at module load cannot
benefit their import or first connection.

Python 3.9 also makes several compatibility fallbacks obsolete. Direct
`time.monotonic`, SSL-context facilities, `Literal`, `Protocol`, `TypedDict`,
and built-in generic types simplify the module. These maintenance changes must
remain separate from the measured lazy-import change so they cannot obscure
its result. `Required` and `NotRequired` are newer than Python 3.9 and need an
appropriate typing-only treatment if touched.

## Preparation

- Add a fresh-process benchmark reporting import wall time, process CPU, RSS,
  and imported-module count for `paho.mqtt.client`.
- Measure import-only, helper startup without PySocks, normal first connection,
  and proxy discovery with an explicit proxy, environment proxy, `no_proxy`,
  and platform proxy behavior.
- Capture `-X importtime` evidence without using it as the final wall-clock
  metric.
- Use two warmups and seven runs while tuning, then at least fifteen fresh
  processes per paired final result with stable CPU affinity.
- Keep `ssl` eager in the initial candidate; its central transport role and
  smaller measured cost do not justify broader lazy-loading complexity.

## Expected Gain

Priority: P2.

A fresh interpreter currently imports `paho.mqtt.client` in about 98 ms.
Exploratory import-time attribution assigns about 23 ms to `urllib.request`,
5.6 ms to `ssl`, and 3.1 ms to `typing`. Deferring `urllib` should materially
reduce cold-start CPU, latency, imported modules, and initial RSS for ordinary
non-proxy users. It does not affect MQTT packet throughput or network bytes.

Typing and compatibility cleanup is expected to improve maintainability, not
runtime performance, and receives no performance claim.

## Acceptance Criteria

- Reduce median cold import and no-PySocks helper startup time by at least 15
  percent in fresh-process paired measurements.
- Do not regress normal connection setup by more than 2 percent.
- Preserve explicit proxy, proxy environment variables, `no_proxy`, system
  proxy discovery, proxy authentication, and optional-dependency behavior.
- Do not make `ssl` lazy in the first candidate.
- Commit measured lazy imports separately from typing and compatibility-only
  cleanup.

## Before Measurement

The final baseline will be the committed result of plan 27. Current
exploratory attribution is:

| Cold-start component | Indicative time |
| --- | ---: |
| Import `paho.mqtt.client` | 97.8 ms |
| `urllib.request` import graph | 23.0 ms |
| `ssl` | 5.6 ms |
| `typing` | 3.1 ms |

These figures are not additive and will not be used as final evidence. The
accepted result requires fresh-process ABBA measurements of the actual module.

## Implementation

Pending. The first candidate will remove module-level `urllib` imports and
import `urllib.parse` and `urllib.request` inside `_get_proxy()` only after the
fast return when PySocks is unavailable. Proxy users keep the same behavior
and pay the import once through Python's module cache.

Obsolete Python compatibility paths and typing aliases will be evaluated as a
separate maintenance commit after the performance verdict.

## After Measurements

Pending implementation and final paired measurement.

## Results Analysis

Pending. The analysis must report cold-start wall/CPU/RSS separately from
connection setup and proxy behavior. Import-time attribution alone cannot
justify retaining the change.

## Verdict

**Pending.** Stop for explicit evaluation after the final cold-start and proxy
guardrail results.
