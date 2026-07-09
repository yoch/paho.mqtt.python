# 02 - Packet Write Queue

## Problem

The send path is a probable P0 bottleneck for producers and gateways publishing
large message volumes. The hot code paths are `Client.publish()`,
`Client._send_publish()`, `Client._packet_queue()`, and `Client._packet_write()`.

Likely symptoms:

- High CPU use during QoS 0 publish bursts.
- Frequent packet allocation and payload copying.
- Repeated socketpair wakeups when many publishes arrive before the network
  thread drains the queue.
- Repeated `want_write()` checks and socket register/unregister callbacks.
- `MQTTMessageInfo` and condition objects created for every QoS 0 publish even
  when callers do not wait on them.

Common workloads:

- IoT aggregators forwarding many telemetry messages to a broker.
- Producer clients using `loop_start()` and publishing from another thread.
- QoS 0 firehose workloads where the Python client is CPU-bound.
- QoS 1 workloads with high inflight limits and small payloads.

## Theoretical Rationale

Outbound publishing performs several CPU-visible operations per message:

- Topic encoding and validation.
- Payload normalization.
- Remaining length encoding.
- `bytearray` construction and extension.
- Queue object creation.
- Possible immediate `loop_write()` call.
- Socketpair byte write to wake the network loop.

For small messages, fixed per-message overhead dominates payload transmission.
Repeated wakeups can also cause unnecessary context switches, cache disruption,
and syscall overhead. Batching queue drain and coalescing wakeups are often more
valuable than optimizing individual arithmetic operations.

## Expected Gain

Priority: P0.

Conservative expected gain:

- 10 to 30 percent throughput improvement for QoS 0 publish bursts from a worker
  thread into `loop_start()`.
- 5 to 15 percent CPU reduction for single-threaded publish plus loop workloads.
- Reduced system CPU when socketpair wakeups are coalesced.

The largest gain should appear when messages are small and publish rate is much
higher than the network loop wakeup rate.

## Before/After Measurements

Microbenchmarks:

- Call `_send_publish()` with pre-encoded topic and payload against a fake socket
  that accepts all writes.
- Call `publish()` for QoS 0 with 16-byte and 128-byte payloads.
- Call `publish()` for QoS 1 with inflight available and with inflight saturated.
- Measure `_packet_write()` draining 1, 10, 100, and 10,000 queued packets.
- Count socketpair writes per 10,000 queued packets in threaded mode.

Broker scenarios:

- Local TCP QoS 0 publish throughput with `loop_start()`.
- Local TCP QoS 0 publish throughput with manual `loop()`.
- Local TCP QoS 1 publish throughput with inflight limits 20, 100, and 1000.
- TLS publish throughput for 128-byte and 4-KiB payloads.

Metrics:

- Published messages per second.
- CPU user/system split.
- Socketpair wakeups per message.
- Queue length high-water mark.
- p95 time from `publish()` call to socket send where measurable.

## Implementation Guidelines

Allowed implementation directions:

- Add an internal wakeup-pending flag so `_packet_queue()` writes to the
  socketpair only when the network loop has not already been woken.
- Batch `_packet_write()` drain behavior so one readiness event can send more
  queued packets without repeated register/unregister churn.
- Cache `struct.Struct("!H")` or use direct byte construction for common packet
  fields.
- Fast-path MQTT v3 QoS 0 PUBLISH with empty properties and already-bytes
  payloads.
- Avoid avoidable conversions when topic and payload are already bytes.
- Evaluate whether `MQTTMessageInfo` can lazily allocate its condition while
  preserving public behavior.

Risks:

- Wakeup coalescing must not delay messages indefinitely.
- External event loop callbacks must still receive correct register/unregister
  notifications.
- `wait_for_publish()` behavior and callback ordering must remain unchanged.
- QoS 1 and QoS 2 state transitions must remain correct under partial writes.

## Acceptance Criteria

Functional criteria:

- Existing tests pass.
- Add tests for threaded publish wakeup coalescing, external loop write
  registration, partial socket writes, and QoS 0 on_publish ordering.
- Preserve return values and `MQTTMessageInfo` behavior.

Performance criteria:

- At least 10 percent throughput improvement or 10 percent CPU reduction in the
  threaded QoS 0 small-payload benchmark.
- At least 50 percent fewer socketpair writes per publish burst when the network
  loop is already awake.
- No regression above 2 percent in single-message latency for non-threaded
  publish.

Documentation criteria:

- Record wakeup counts before and after.
- Document whether gains come from fewer syscalls, fewer allocations, or faster
  packet construction.

## Verdict

GO with conditions.

Justification: send-side CPU and wakeup overhead directly affect high-volume IoT
publishers. Proceed first with measurement of socketpair wakeups and queue drain
behavior, because batching bugs can create subtle latency regressions.

## Progress (2026-07-09)

Status: **GO — project complete for this round**.

### Implemented (accepted)

1. Shared `_PACK_U16 = struct.Struct("!H")` for topic length / mid packing.
2. Drop dead `remaining_bytes` list in `_pack_remaining_length()`.
3. `_send_publish()` packs already-bytes topics without `_force_bytes()`.
4. Lazy `threading.Condition` on `MQTTMessageInfo`. Hot-path
   `_set_as_published()` is lock-free when no waiter exists; waiters create the
   Condition under `_message_info_condition_lock` and re-check `_published`
   under the Condition. Covered by a 200-iteration concurrent race test.
5. Socketpair wakeup coalescing via `_sockpair_wakeup_pending`, guarded by
   `_sockpair_wakeup_mutex` shared by `_packet_queue()` send and `_loop()` drain.
6. Avoid full-buffer slice copy in `_packet_write()` when `pos == 0`.
7. Safe `info is None` handling in QoS 0 completion path.
8. Harness: `sockpair_wakeup_coalesce_10000`, `publish_threaded_qos0_v3_small`.
9. Tests in `tests/test_client_write_performance.py`: lazy Condition, race,
   wakeup coalesce, partial writes, QoS 0 `on_publish` ordering, external-loop
   `on_socket_register_write`.

### Acceptance criteria

| Criterion | Result |
| --- | --- |
| Threaded QoS 0 small-payload ≥ +10% | **PASS** — about +51% vs HEAD (`publish` + drain thread / sockpair) |
| ≥ 50% fewer sockpair writes when loop already awake | **PASS** — 3000 → 6 wakeups on 3000 publishes; 10000 → 1 in coalesce scenario |
| No >2% single-message latency regression (non-threaded) | **PASS** — p50 improved (~−57% vs HEAD in same harness) |
| Functional tests for coalesce / partial write / on_publish / external loop | **PASS** |
| Existing `tests/test_client.py` | **PASS** |

Brokerless deltas vs original Codex write baseline / HEAD:

| Scenario | Delta |
| --- | --- |
| `publish_pack_qos0_v3_small` | about +77% vs early baseline |
| `packet_write_drain_100` | about +200% vs packing-only baseline |
| threaded QoS 0 (HEAD vs candidate) | about +51% |
| sockpair wakeups / burst | −99%+ |

Gain sources: fewer Condition allocations (main QoS 0 win), fewer sockpair
syscalls (threaded win), slightly faster packing, fewer buffer copies on full
sends.

### Evaluated and rejected / deferred

| Track | Verdict | Evidence |
| --- | --- | --- |
| `_OutPacket` `__slots__` class with dict-compatible `__getitem__` | **NO GO** | Construction-only microbench ~+17%, but publish E2E with attribute shim ~−15%. Would need a full `_packet_write` rewrite to attributes; risk > reward after current wins. |
| Skip allocating `MQTTMessageInfo` for fire-and-forget QoS 0 | **NO GO for now** | `_send_publish(..., info=None)` ~+9% isolated, but `publish()` must still return a public `MQTTMessageInfo`. Skipping allocation needs an API-preserving sentinel or lazy object; defer unless a later profile still shows it hot. |
| Preallocate PUBLISH `bytearray` + `pack_into` | **NO GO** | Earlier experiment: QoS 0 regressed vs simple extend packing; code uglier. |
| Unconditional no-copy without `pos == 0` guard | n/a | Kept the safe `pos == 0` form only. |
