# 05 - Inflight Message State

## Problem

QoS 1 and QoS 2 publishing can spend CPU scanning message state. The relevant
state is `_out_messages`, `_in_messages`, `_inflight_messages`, and methods such
as `_update_inflight()`, `_messages_reconnect_reset_out()`,
`_messages_reconnect_reset_in()`, `_handle_pubackcomp()`, `_handle_pubrec()`,
and `_handle_pubrel()`.

Likely symptoms:

- CPU spikes when the outgoing queue is large and inflight slots free up.
- `_update_inflight()` scans `_out_messages.values()` to find queued messages.
- Reconnect reset walks all messages and can call send paths repeatedly.
- `OrderedDict` may preserve useful order but creates overhead compared with a
  queue of queued mids plus a mapping by mid.
- Topic bytes may be re-encoded on resend because `MQTTMessage.topic` exposes a
  decoded property.

Common workloads:

- Gateways publishing QoS 1 messages faster than the broker can ACK.
- High inflight limits with bursty network availability.
- Persistent sessions with many queued messages across reconnect.

## Theoretical Rationale

Scanning all outgoing messages to find the next queued message is O(n) per freed
inflight slot. Under saturation this can approach O(n*m), where `m` is the
number of acknowledgements or slots freed. A separate ready queue can make the
common operation O(1) or amortized O(1).

Modern CPUs handle linear scans well in C, but Python object iteration over
message objects and state checks is expensive. Reducing scan frequency should
matter more than micro-optimizing the state comparisons.

## Expected Gain

Priority: P1.

Conservative expected gain:

- 10 to 40 percent CPU reduction in saturated QoS 1 microbenchmarks with large
  queues.
- Lower p95 `publish()` and ACK handling latency when many messages are queued.
- Little or no improvement for QoS 0 or uncongested QoS 1 workloads.

## Before/After Measurements

Microbenchmarks:

- Populate `_out_messages` with 20, 100, 1000, and 10,000 QoS 1 messages.
- Simulate PUBACK handling and `_update_inflight()` with inflight limits 20,
  100, and 1000.
- Measure reconnect reset with mixed states: queued, wait_for_puback,
  wait_for_pubrec, wait_for_pubcomp.
- Measure memory overhead for additional queue/index structures.

Broker scenarios:

- Local QoS 1 publisher with broker ACK delay or limited receive rate.
- Publish burst larger than max inflight, then drain.
- Reconnect with queued QoS 1/QoS 2 messages.

Metrics:

- Time per ACK handled.
- Time to promote next queued message.
- CPU per 100,000 QoS 1 messages.
- Memory per queued message.
- End-to-end throughput under inflight saturation.

## Implementation Guidelines

Allowed implementation directions:

- Maintain a separate deque of queued outgoing mids for messages waiting for an
  inflight slot.
- Keep `_out_messages` as the authoritative mid-to-message mapping for
  compatibility and lookup.
- Ensure queue entries are removed or skipped safely when messages are removed.
- Store encoded topic bytes for outgoing messages to avoid re-encoding on
  resend, while preserving public `MQTTMessage.topic`.
- Consider small helper methods for state transitions to keep QoS correctness
  auditable.

Risks:

- Duplicate queue entries can cause duplicate sends.
- Removing messages from mapping and queue must remain consistent.
- QoS 2 state transitions are more fragile than QoS 1 and need focused tests.
- Memory overhead may outweigh gains for small queues.

## Acceptance Criteria

Functional criteria:

- Existing publish/QoS tests pass.
- Add tests for inflight saturation, queue promotion order, reconnect reset, and
  duplicate ACK/PUBREC/PUBREL handling.
- Preserve callback ordering and `MQTTMessageInfo` publication state.

Performance criteria:

- At least 20 percent faster ACK handling in a 10,000 queued-message saturated
  QoS 1 microbenchmark.
- No more than 5 percent memory increase per queued message unless throughput
  gain exceeds 25 percent.
- No regression above 2 percent for small queues of 20 messages.

Documentation criteria:

- Document the state invariants for mapping, ready queue, and inflight count.
- Record memory/performance tradeoff in the verdict.

## Verdict

GO with conditions.

Justification: this project has high upside for saturated QoS workloads but
adds state-management risk. It should proceed only after a benchmark proves
linear scans dominate and after state invariants are documented.
