# 15 - Batched ACK Inflight Refill

## Analysis

Every PUBACK or PUBCOMP currently completes one outgoing message and calls
`_update_inflight()` immediately. When the built-in read loop already has a
burst of ACK packets available, this repeats the scan and promotes one queued
message per ACK even though all freed slots could be refilled in one pass.

This is different from the ready-queue rejected in project 05. The authoritative
`OrderedDict` and its O(max_inflight) scan remain unchanged; only the frequency
of refill calls changes at an existing packet-batch boundary.

## Preparation

- Add brokerless ACK bursts of 1, 8, 20, 100, and 1,000 messages.
- Test inflight limits 20, 100, and 1,000 with queues of 100, 1,000, and 10,000
  messages.
- Measure MQTT v3 PUBACK and PUBCOMP separately, then MQTT v5 ACKs with empty
  and rich properties.
- Count `_update_inflight()` calls, scanned messages, promoted messages,
  generated PUBLISH packets, CPU, allocations, and ACK/s.
- Include callbacks that publish another QoS message and callbacks that raise.
- Preserve the project 05 harness as a regression reference.

## Expected Gain

Priority: P0.

- At least 20 percent higher saturated ACK throughput for realistic batches.
- One refill scan per batch instead of one per ACK.
- Larger output batches for project 16 without another persistent queue.
- No meaningful change for an isolated ACK.

## Acceptance Criteria

- At least 20 percent higher end-to-end throughput for 100 ACKs with a
  saturated inflight window.
- Refill calls fall from approximately one per completed ACK to one per
  internal batch.
- No regression above 2 percent for a single ACK or public packet-at-a-time
  `loop_read()`.
- `on_publish`, `MQTTMessageInfo`, ACK ordering, outgoing message ordering,
  inflight accounting, DUP flags, and MQTT v5 validation remain unchanged.
- Unknown and duplicate ACKs do not reserve refill capacity.
- A callback-published message remains ordered behind already queued messages.
- Fatal parse/send errors flush or discard deferred refill work according to
  the existing connection state, without leaving a free-slot count pending.

## Before Measurement

Pending. Record the current per-ACK implementation with 2 warmups, 7 exploratory
runs, and 15 final runs.

Required baseline rows:

| ACK batch | Inflight | Queue | ACK/s | Refill calls | p95 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 20 | 100 | pending | pending | pending |
| 20 | 20 | 1,000 | pending | pending | pending |
| 100 | 100 | 1,000 | pending | pending | pending |
| 1,000 | 100 | 10,000 | pending | pending | pending |

## Implementation

Planned prototype:

- Split outgoing-message completion from inflight refill scheduling.
- Add a batch-local deferred-refill flag/count used only by the private built-in
  read batch.
- Complete callbacks and `MQTTMessageInfo` immediately and in wire order.
- At the batch boundary, invoke the existing `_update_inflight()` once; it can
  fill every available slot in its normal ordered scan.
- Keep immediate refill for public packet-at-a-time paths.
- Do not add a deque, alternate authoritative mapping, or new public setting.
- Remove the prototype if the full ACK path does not cross the threshold even
  when the isolated scan benchmark improves.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Attribute the result between fewer dictionary scans, fewer send-path
entries, and interaction with the writer. Report standalone results before
project 16 as well as the combined result after project 16.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
