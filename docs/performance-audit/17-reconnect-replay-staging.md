# 17 - Reconnect Replay Staging

## Analysis

Project 13 optimized reconnect state reset and invariant work, but successful
CONNACK replay still queues and drains eligible messages inside the iteration.
Calling `loop_write()` after each retransmit prevents the output queue from
forming a useful batch and repeats writer/registration bookkeeping.

Replay can preserve the same ordered state transitions while staging all
currently eligible retransmits first, then invoking one drain. This project is
about replay execution, not the already-accepted O(N) reset pass.

## Preparation

- Preserve project 13 reset measurements as regression guards.
- Add actual CONNACK-to-wire replay scenarios for 100, 1,000, and 10,000
  messages.
- Measure QoS 1 wait-for-PUBACK, QoS 2 publish/PUBREL states, mixed queues, and
  inflight limits 20, 100, and unlimited.
- Run once against the legacy writer and once after project 16.
- Count `loop_write()` calls, underlying writes, state transitions, duplicate
  flags, CPU, allocations, replay completion time, and peak queue memory.

## Expected Gain

Priority: P1.

- At least 20 percent faster replay of 1,000 messages.
- One explicit drain per replay pass rather than one per eligible message.
- At least 80 percent fewer underlying writes when combined with project 16.
- No change to reset complexity or persistent-session semantics.

## Acceptance Criteria

- At least 20 percent lower CONNACK-to-replay-queued time at 1,000 messages.
- One explicit replay drain for each successful CONNACK pass.
- With project 16, at least 80 percent fewer underlying writes for the same
  replay.
- State, order, inflight count, DUP bit, PUBREL handling, callbacks, and
  `MQTTMessageInfo` behavior remain unchanged.
- A send failure stops staging/drain with the same return code and leaves the
  remaining authoritative messages reconnectable.
- No regression above 2 percent in the project 13 reset-only scenario.

## Before Measurement

Pending. Record both reset-only and actual replay baselines before editing the
CONNACK path.

Required baseline rows:

| QoS/state mix | Messages | Inflight | Replay time | `loop_write` | Writes |
| --- | ---: | ---: | ---: | ---: | ---: |
| QoS 1 publish | 1,000 | 20 | pending | pending | pending |
| QoS 1 publish | 1,000 | 100 | pending | pending | pending |
| QoS 2 mixed | 1,000 | 20 | pending | pending | pending |
| QoS 2 mixed | 10,000 | 100 | pending | pending | pending |

## Implementation

Planned prototype:

- Split replay state transition/packet creation from explicit writer drain.
- Hold existing state locks only while selecting and transitioning messages;
  keep the authoritative `OrderedDict` and original iteration order.
- Queue every currently eligible retransmit while immediate writes are
  suppressed by the existing callback/write guard.
- Invoke one drain after the replay pass.
- Preserve inflight ceilings: queued messages beyond the ceiling remain queued
  and are promoted by the existing mechanism.
- Remove the prototype if it only moves work without improving full replay or
  if its gain depends on unbounded temporary memory.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Report standalone staging gain and combined gain with project 16 so
the dependency is explicit rather than attributed twice.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
