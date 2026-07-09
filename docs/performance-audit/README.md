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
| [01 - Packet Read Parser](01-packet-read-parser.md) | P0 | **Done (this round)** | `Client._packet_read()`, `Client._handle_publish()` | Reduce receive-side copies, allocations, and dictionary lookups. |
| [02 - Packet Write Queue](02-packet-write-queue.md) | P0 | **Done (this round)** | `Client._send_publish()`, `Client._packet_queue()`, `Client._packet_write()` | Improve publish throughput and reduce wakeup/write overhead. |
| [03 - MQTT v5 Properties and Reason Codes](03-mqttv5-properties-reasoncodes.md) | P0 | **Done** | `Properties`, `ReasonCode`, MQTT v5 handlers | Remove repeated metadata construction and linear lookups. |
| [04 - Callback Dispatch and Topic Matching](04-callback-dispatch-topic-matching.md) | P1 | **Partial** (round 1 done; eager `match()` NO GO; `iter_match` micro-opt kept) | `Client._handle_on_message()`, `MQTTMatcher` | Bound callback filtering overhead under many subscriptions. |
| [05 - Inflight Message State](05-inflight-message-state.md) | P1 | **NO GO** (ACK path) | `_out_messages`, `_update_inflight()` | Ready-queue rejected; reconnect O(N) scan noted for future. |
| [06 - Threading Wakeup and Event Loop](06-threading-wakeup-event-loop.md) | P1 | **Done** | socketpair wakeups, locks, loop integration | Wakeup coalesce + tests + state machine doc. |
| [07 - WebSocket Transport](07-websocket-transport.md) | P2 | **Out of scope (this PR)** | `_WebsocketWrapper` | Deferred to a future PR. |
| [08 - Logging and Observability](08-logging-observability.md) | P1 | **Done (harness)** | `_easy_log()`, benchmark/profiling workflow | Add low-noise measurement and regression guardrails. |

## Progress Snapshot (2026-07-09)

Landed on branch `benchmarks` (representative commits):

- `238eee8` harness + audit plans (08)
- `f2aaa76` MQTT v5 properties / reason-code metadata cache (03)
- `92008c1` receive dispatch: lazy `MQTTMessageInfo`, filtered-callback fast path (04 round 1)
- `6f6869c` / `65e1671` / `6bb33c5` write path + wakeup coalesce + remaining-length fast path (02, 06 partial)
- plan **01**: reusable `_InPacketState`, index-based `_handle_publish`, v5 empty-props fast path
- plan **04** round 2: eager `match()` rejected; kept `iter_match` micro-opt (`nparts` / `yield from`) + dispatch tests/harness
- plan **05** evaluated: ready-queue **NO GO** on ACK path (scan O(max_inflight)); reconnect reset O(N) deferred
- plan **06** closed: wakeup coalesce (02) + callback/external-loop tests + state machine doc

This PR scope: plans **01–06** and **08** harness. Plan **07** (WebSocket) is explicitly deferred.

Recommended follow-ups (future PRs):

1. **07 WebSocket** if WS transport users are in scope.
2. Revisit **05** only for reconnect-heavy profiles (full `_out_messages` scan on reset).
3. Optional broker-side system-CPU profiles for threaded publish bursts.

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
