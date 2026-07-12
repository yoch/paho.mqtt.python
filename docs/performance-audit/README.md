# Paho MQTT Python Performance Audit

This directory contains a performance-oriented audit plan for the Paho MQTT
Python client. It is written as a set of independent project files so each
suspected bottleneck can be profiled, prototyped, accepted, or rejected without
coupling it to unrelated work.

The audit is intentionally compatible with the package baseline
(`requires-python >=3.7`). The local tox matrix may start on a newer version,
but Python 3.12+ implementation ideas are optional notes and cannot become
acceptance requirements for these projects.

## Project Index

| Project | Priority | Status | Main code paths | Expected outcome |
| --- | --- | --- | --- | --- |
| [01 - Packet Read Parser](01-packet-read-parser.md) | P0 | **Done (this round)** | `Client._packet_read()`, `Client._handle_publish()` | Reduce receive-side copies, allocations, and dictionary lookups. |
| [02 - Packet Write Queue](02-packet-write-queue.md) | P0 | **Done (this round)** | `Client._send_publish()`, `Client._packet_queue()`, `Client._packet_write()` | Improve publish throughput and reduce wakeup/write overhead. |
| [03 - MQTT v5 Properties and Reason Codes](03-mqttv5-properties-reasoncodes.md) | P0 | **Done** | `Properties`, `ReasonCode`, MQTT v5 handlers | Remove repeated metadata construction and linear lookups. |
| [04 - Callback Dispatch and Topic Matching](04-callback-dispatch-topic-matching.md) | P1 | **Partial** (round 1 done; eager `match()` NO GO; `iter_match` micro-opt kept) | `Client._handle_on_message()`, `MQTTMatcher` | Bound callback filtering overhead under many subscriptions. |
| [05 - Inflight Message State](05-inflight-message-state.md) | P1 | **NO GO** (ACK path) | `_out_messages`, `_update_inflight()` | Ready-queue rejected; reconnect O(N) scan noted for future. |
| [06 - Threading Wakeup and Event Loop](06-threading-wakeup-event-loop.md) | P1 | **Done** | socketpair wakeups, locks, loop integration | Wakeup coalesce + tests + state machine doc. |
| [07 - WebSocket Transport](07-websocket-transport.md) | P2 | **Done** | `_WebsocketWrapper` | Hybrid native masking and zero-copy partial-send cursor. |
| [08 - Logging and Observability](08-logging-observability.md) | P1 | **Done (harness)** | `_easy_log()`, benchmark/profiling workflow | Add low-noise measurement and regression guardrails. |
| [09 - Read-Ahead and Packet Batching](09-read-ahead-packet-batching.md) | P0 | **Done** | `_loop()`, `_packet_read()`, `_sock_recv()` | Batch inbound packets and amortize socket reads. |
| [10 - Publish ACK Completion](10-publish-ack-completion.md) | P1 | **Done** | `_handle_pubackcomp()`, `_do_on_publish()` | Skip callback metadata when MQTT v3 has no publish callback. |
| [11 - MQTT v5 Rich Property Codec](11-mqttv5-rich-property-codec.md) | P1 | **Done** | `Properties`, `VariableByteIntegers` | Cursor parsing and native UTF validation. |
| [12 - Outbound Topic Encoding Cache](12-outbound-topic-encoding-cache.md) | P1 | **NO GO** | `Client.publish()` | Rejected due to high-cardinality regression. |
| [13 - Reconnect Reset and Replay](13-reconnect-replay.md) | P2 | **Done** | reconnect reset, CONNACK replay | Remove repeated invariant work without a second queue. |
| [14 - Contiguous Ingress Decoder](14-contiguous-ingress-decoder.md) | P0 | **GO with conditions** | built-in ingress pump, `loop_read()` | Direct buffered decode kept; public batching prototype rejected. |
| [15 - Batched ACK Inflight Refill](15-batched-ack-inflight-refill.md) | P0 | **GO with conditions** | ACK completion, `_update_inflight()` | Refill all slots once per ACK batch. |
| [16 - Transport-Aware Batched Writer](16-transport-aware-batched-writer.md) | P0 | **Prototype branch; field validation required** | `_packet_write()`, transport send paths | Submit several queued packets per transport write. |
| [17 - Reconnect Replay Staging](17-reconnect-replay-staging.md) | P1 | **GO with conditions** | successful CONNACK replay | Stage ordered retransmits in bounded drains. |
| [18 - Segmented Outbound Payloads](18-segmented-outbound-payloads.md) | P1/P2 | **Planned** | PUBLISH construction, vector writer | Avoid copying large immutable payloads. |
| [19 - Duplex Loop Scheduler](19-duplex-loop-scheduler.md) | P1 | **Planned** | private built-in event loop | Bound and alternate read/write work. |
| [20 - Deadline-Driven Thread Loop](20-deadline-driven-thread-loop.md) | P1 | **Planned** | `loop_start()`, `loop_stop()`, reconnect wait | Replace polling with timer/control wakeups. |
| [21 - WebSocket Inbound Streaming](21-websocket-inbound-streaming.md) | P2 | **Planned** | `_WebsocketWrapper.recv()` / `pending()` | Decode frames from bounded read-ahead buffers. |
| [22 - Callback and State-Lock Decoupling](22-callback-state-lock-decoupling.md) | P1 | **Planned** | PUBACK/PUBCOMP/PUBREL callbacks | Run user callbacks outside message-state mutexes. |
| [23 - `publish.multiple()` Pipeline](23-publish-multiple-pipeline.md) | P1 | **Planned** | one-shot publish helper | Use a bounded 20-message completion window. |
| [24 - Automatic MQTT v5 Topic Alias](24-mqttv5-automatic-topic-alias.md) | P2 | **Planned** | CONNACK capabilities, PUBLISH packing | Reduce repeated topic bytes with a strict bounded table. |
| [25 - TLS Session Resumption](25-tls-session-resumption.md) | P2 | **Planned** | TLS handshake/reconnect | Reuse verified TLS sessions when supported. |

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

Receive follow-up for `mqtt_zigbee_listener` (2026-07-09):

- Harness: `publish_parse_v3_qos2_small`, `publish_parse_v3_qos2_z2m_filters`, `dispatch_z2m_seven_filters`.
- **GO**: skip PUBLISH `print_topic` UTF-8 decode when no log sink (~+9.5% parse, logger off).
- **Kept**: `MQTTMessage._topic_str` cache (match + callback share one decode).
- **NO GO**: further QoS2 `_in_messages` bookkeeping; further matcher/`list()` work for 7 filters (~+2.5%).
- Remaining listener CPU is largely **outside paho** (SQLAlchemy workers / `orjson` / app logging).

Second audit round (2026-07-10):

- **09 GO:** built-in read-ahead/batching improves a local 1,000-message burst by about 84% and reduces burst reads to one.
- **10 GO:** MQTT v3 ACK completion without `on_publish` improves by about 18%.
- **11 GO:** rich property unpack and end-to-end MQTT v5 rich PUBLISH improve by about 53% and 28% in paired runs.
- **12 NO GO:** a bounded topic cache regresses a 1,000-topic publisher by about 14%; prototype removed.
- **13 GO:** QoS 2 reconnect reset improves by about 24% at 1,000 messages.
- **07 GO:** WebSocket frame creation improves about 154% at 128 bytes with bounded 64-KiB masking chunks.

Third architectural audit plan (2026-07-11):

- **P0 core:** projects 14-16 cover contiguous ingress, batch-level inflight
  refill, and transport-aware grouped writes.
- **Flow/lifecycle:** projects 17-20 cover reconnect staging, large immutable
  payload ownership, duplex fairness, and deadline-driven thread wakeups.
- **Transport/concurrency/helpers:** projects 21-25 cover WebSocket ingress,
  callback lock scope, helper pipelining, MQTT v5 aliases, and TLS resumption.
- No new public execution mode or setting is planned. Shared reactors,
  asynchronous callback executors, streaming APIs, and byte-based public
  backpressure remain out of scope.
- Execution order is 14, 15, 16, 17, 18, 19, 20, 22, 23, 21, 24, 25. Each
  project stops after paired measurements for explicit verdict and commit
  approval before the next project starts.

Third audit execution:

- **14 GO with conditions:** direct contiguous buffered decode improves TCP and
  TLS small-message ingress by about 37%; the public batching prototype was
  removed.
- **15 GO with conditions:** one inflight refill per private ACK batch improves
  the permanent 100-PUBACK scenario by about 132%; retain the isolated-ACK
  guardrail after a measured sub-microsecond (~4.4%) internal-loop cost.
- **16 prototype isolated:** `perf/plan16-sendmsg-prototype` at `25d75f9`
  improves local TCP/Unix throughput and cuts writes by 98%, but is deliberately
  absent here pending real workload, tail-latency, concurrency, and failure-mode
  validation. The CPU-only control regressed, so no production `GO` is implied.
- **17 GO with conditions:** bounded reconnect replay staging improves the
  1,000-message QoS 1 scenario by about 51% and reduces explicit drains from
  1,000 to 16; the faster but unbounded single-drain variant was rejected.

Recommended follow-ups:

1. Optional local-broker TCP/TLS/WS system-CPU profiles.
2. Do not reopen the topic cache without a new profile or explicit opt-in design.
3. Do not reopen rejected 02/05 structures without contradictory evidence.

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

- Use 2 warmup runs.
- Use at least 7 measured runs during exploration and 15 for final evidence.
- Report the median, spread, and p50/p95/p99 where relevant.
- Warm up the interpreter before recording.
- Pin scenario inputs: payload size, QoS, protocol version, transport, number of
  subscriptions, inflight limit, and queued message count.
- Compare baseline and prototype in the same environment.

## Execution Checkpoints

Projects 14-25 use a strict sequential workflow:

1. Verify the expected HEAD and inspect all tracked/untracked changes.
2. Add the isolated scenario/tests and record the before measurement.
3. Implement only the current project's private prototype.
4. Run focused correctness tests and paired exploratory/final measurements.
5. Complete all nine document sections and stop for human evaluation.
6. Commit only after an explicit `GO`, `GO with conditions`, or `NO GO`
   decision. Accepted production code is one signed commit; a rejected
   prototype is removed before its signed benchmark/documentation commit.
7. Start the next project only from a committed, reviewed checkpoint.

Unexpected overlapping edits are never overwritten or stashed implicitly. The
untracked `AGENTS.md` and `.cursorignore` files remain untouched.

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
