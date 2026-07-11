# 23 - `publish.multiple()` Pipeline

## Analysis

The one-shot `publish.multiple()` helper submits its first message on CONNACK
and submits each following message only from `on_publish`. Its effective window
is therefore one. QoS 1 and QoS 2 throughput is limited to roughly one message
per broker round trip even though `Client` already supports an inflight window
of 20 and ordered queueing.

A bounded sliding window inside the helper can preserve its signature, blocking
behavior, input order, and completion semantics while using the existing
client pipeline.

## Preparation

- Add helper-level scenarios for 1, 20, 100, and 1,000 messages.
- Test QoS 0, QoS 1, QoS 2, and mixed sequences.
- Use controlled ACK delays of 0, 20, and 100 ms without requiring network
  shaping privileges.
- Measure total helper wall time, publish order, outstanding count, queue/RSS
  high-water mark, callback count, CPU, and disconnect timing.
- Include MID wrap/collision, publish failure, connection failure, and an empty
  remainder after initial fill.

## Expected Gain

Priority: P1, narrow scope but potentially multiplicative.

- At least fivefold higher QoS 1 throughput with 20-ms ACK delay.
- Up to the existing 20-message inflight factor on latency-bound brokers.
- Neutral behavior for one message and loopback QoS 0.

## Acceptance Criteria

- Use an internal fixed submission window of 20 messages; no public parameter
  or signature change.
- At least 5x higher throughput for 100 QoS 1 messages with 20-ms ACK delay.
- At least 70 percent lower wall time for the primary 100-ms-delay scenario.
- No regression above 5 percent for one message or zero-delay loopback.
- At most 20 additional wire packets are materialized simultaneously by the
  helper.
- Input publish order is preserved; callback completion may follow normal MQTT
  QoS timing but every accepted message completes exactly once.
- Disconnect occurs only after the source is exhausted and outstanding count
  reaches zero.
- Mixed QoS, queue rejection, callback reentrancy, MID wrap, reconnect, and
  exception cleanup are covered.

## Before Measurement

Pending. Record the current window-one helper before changing its userdata
state machine.

Required baseline rows:

| Messages | QoS | ACK delay | Wall time | msg/s | Peak outstanding |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 0 ms | pending | pending | pending |
| 100 | 1 | 0 ms | pending | pending | pending |
| 100 | 1 | 20 ms | pending | pending | pending |
| 100 | 1 | 100 ms | pending | pending | pending |
| 100 | mixed | 20 ms | pending | pending | pending |

## Implementation

Planned prototype:

- Replace the helper's raw userdata deque with a private state object holding
  remaining messages, outstanding count, and terminal error.
- On successful CONNACK, submit up to 20 messages in input order.
- On each `on_publish`, decrement outstanding and refill back to 20.
- Queue DISCONNECT only when no remaining or outstanding message exists.
- Check every `publish()` result and terminate cleanly on rejection/error rather
  than hanging.
- Keep authentication, TLS, proxy, protocol, transport, and public helper
  arguments unchanged.
- Remove the prototype if the zero-delay guardrail fails or memory is not
  bounded by the chosen window.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Report separately the RTT-pipelining gain, local CPU overhead, memory
high-water mark, QoS mix, and disconnect correctness.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
