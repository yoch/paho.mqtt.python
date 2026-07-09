# Paho MQTT Python Performance Audit

This directory contains a performance-oriented audit plan for the Paho MQTT
Python client. It is written as a set of independent project files so each
suspected bottleneck can be profiled, prototyped, accepted, or rejected without
coupling it to unrelated work.

The audit is intentionally compatible with the current CI/tox baseline
(`python >=3.9`). Python 3.12+ implementation ideas may be recorded as optional
future notes, but they are not acceptance requirements for these projects.

## Project Index

| Project | Priority | Status | Main code paths | Expected outcome |
| --- | --- | --- | --- | --- |
| [01 - Packet Read Parser](01-packet-read-parser.md) | P0 | **Next** | `Client._packet_read()`, `Client._handle_publish()` | Reduce receive-side copies, allocations, and dictionary lookups. |
| [02 - Packet Write Queue](02-packet-write-queue.md) | P0 | **Done (this round)** | `Client._send_publish()`, `Client._packet_queue()`, `Client._packet_write()` | Improve publish throughput and reduce wakeup/write overhead. |
| [03 - MQTT v5 Properties and Reason Codes](03-mqttv5-properties-reasoncodes.md) | P0 | **Done** | `Properties`, `ReasonCode`, MQTT v5 handlers | Remove repeated metadata construction and linear lookups. |
| [04 - Callback Dispatch and Topic Matching](04-callback-dispatch-topic-matching.md) | P1 | **Partial** | `Client._handle_on_message()`, `MQTTMatcher` | Bound callback filtering overhead under many subscriptions. |
| [05 - Inflight Message State](05-inflight-message-state.md) | P1 | Not started | `_out_messages`, `_in_messages`, `_update_inflight()` | Reduce linear scans and QoS bookkeeping cost. |
| [06 - Threading Wakeup and Event Loop](06-threading-wakeup-event-loop.md) | P1 | **Partial** (wakeup coalesce landed via 02) | socketpair wakeups, locks, loop integration | Reduce cross-thread wakeups and lock contention. |
| [07 - WebSocket Transport](07-websocket-transport.md) | P2 | Not started | `_WebsocketWrapper` | Reduce pure-Python masking and buffering overhead. |
| [08 - Logging and Observability](08-logging-observability.md) | P1 | **Done (harness)** | `_easy_log()`, benchmark/profiling workflow | Add low-noise measurement and regression guardrails. |

## Progress Snapshot (2026-07-09)

Landed on branch `benchmarks` (representative commits):

- `238eee8` harness + audit plans (08)
- `f2aaa76` MQTT v5 properties / reason-code metadata cache (03)
- `92008c1` receive dispatch: lazy `MQTTMessageInfo`, filtered-callback fast path (04 partial)
- `6f6869c` / `65e1671` / `6bb33c5` write path + wakeup coalesce + remaining-length fast path (02, 06 partial)

Recommended order for the next round:

1. **01 Packet Read Parser** — last open P0; receive path still uses dict `_in_packet` and copy-heavy unpack.
2. Finish **04** only if profiles show matcher cost after 01 (trie iteration / list materialization).
3. **05 Inflight** after a QoS1-saturated profile proves `_update_inflight` scans dominate.
4. Keep **06** residual work (external-loop / asyncio docs+tests) opportunistic; core coalesce is done.
5. **07 WebSocket** only if WS users are in scope.

Do not reopen rejected 02 tracks (`_OutPacket` slots shim, PUBLISH prealloc, fire-and-forget `MQTTMessageInfo`) unless a new profile contradicts the earlier NO GO evidence.

## Measurement Method

Every project must produce a baseline measurement before any implementation
change is accepted. Measurements should be reproducible on a developer laptop
without mandatory external services.

Use two layers of measurement:

1. Brokerless microbenchmarks for isolated CPU costs.
2. Optional local broker scenarios for end-to-end network behavior.

Minimum metrics:

- Messages per second.
- User and system CPU time.
- Median, p50, and p95 time per message where applicable.
- Allocation count and allocated bytes using `tracemalloc` or an equivalent
  standard-library method.
- RSS when running longer broker scenarios.
- Approximate syscall or wakeup counts when measuring loop behavior.

Minimum run protocol:

- Run at least 5 iterations per scenario.
- Report the median and the spread.
- Warm up the interpreter before recording.
- Pin scenario inputs: payload size, QoS, protocol version, transport, number of
  subscriptions, inflight limit, and queued message count.
- Compare baseline and prototype in the same environment.

## Benchmark Harness Shape

The recommended harness is documentation-backed and can later become executable
tests or scripts. It should avoid mandatory third-party dependencies.

Brokerless scenarios:

- Decode MQTT fixed header and remaining length for many small packets.
- Parse inbound PUBLISH packets for MQTT v3 and MQTT v5.
- Pack outbound PUBLISH packets for QoS 0 and QoS 1.
- Pack and unpack MQTT v5 properties with empty, common, and heavy user-property
  sets.
- Match topics against many exact and wildcard filtered callbacks.
- Update inflight state with small, medium, and saturated outgoing queues.

Optional broker scenarios:

- TCP QoS 0 publish-only throughput with small IoT payloads.
- TCP QoS 1 publish with PUBACK latency and inflight pressure.
- TCP subscribe throughput with callback dispatch.
- MQTT v5 publish/subscribe with properties.
- TLS receive and send throughput.
- WebSocket publish/subscribe throughput.

## Go/No-Go Matrix

Use this common decision matrix in each project verdict:

| Verdict | Meaning |
| --- | --- |
| `GO` | Measured gain is meaningful, implementation risk is controlled, and compatibility is preserved. |
| `GO with conditions` | Worth implementing only if the listed risks are addressed or a threshold is met. |
| `NO GO` | Expected gain is too small, measurement is inconclusive, or compatibility risk outweighs benefit. |

Default thresholds:

- P0 projects should target at least 10 percent throughput improvement or at
  least 15 percent CPU reduction in their primary hot path.
- P1 projects should target at least 5 percent end-to-end improvement in a
  relevant workload or a clearly bounded latency/CPU reduction.
- P2 projects should proceed only when the affected transport or feature is
  demonstrably important for users.

## Compatibility Rules

- Preserve public API behavior and callback signatures.
- Preserve supported Python versions.
- Keep optional dependencies optional.
- Do not require a specific broker for brokerless benchmarks.
- Do not optimize by weakening MQTT correctness, TLS behavior, message ordering,
  or QoS guarantees.
