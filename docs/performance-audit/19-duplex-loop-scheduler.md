# 19 - Duplex Loop Scheduler

## Analysis

The built-in loop bounds reads to 100 packets but `_packet_write()` drains until
the queue is empty or the socket blocks. A producer that continuously appends
faster than the transport drains can therefore prevent reads, ACK handling,
callbacks, and `loop_misc()` from running. Conversely, a 100-packet read batch
can delay generated ACK writes until the entire batch completes.

The loop needs an internal work scheduler rather than independent unbounded
drains. Fairness must not reorder MQTT packets or reduce unidirectional
throughput through excessive selector calls.

## Preparation

- Create a full-duplex brokerless transport that is continuously readable and
  writable while another thread appends outgoing packets.
- Add local broker scenarios with outbound QoS 0 flood plus inbound PUBLISH,
  and outbound QoS 1 with delayed ACKs.
- Test 16-B, 1-KiB, and 64-KiB packets with queue depths up to 100,000.
- Measure aggregate throughput, per-direction throughput, p50/p95/p99 incoming
  callback latency, ACK latency, keepalive drift, selector calls, and queue
  high-water marks.
- Compare packet-only, byte-only, and combined packet/byte/time budgets during
  preparation, but use the fixed combined policy below for the candidate.

## Expected Gain

Priority: P1.

- At least 50 percent lower p95/p99 latency for the starved direction under
  sustained full-duplex saturation.
- Fewer artificial inflight stalls caused by delayed ACK reads.
- No more than 2 percent loss in pure publish or pure subscribe throughput.

## Acceptance Criteria

- Each private loop turn stops a direction at the first of 100 packets,
  256 KiB, or 2 ms; time is checked every eight completed operations.
- When both directions are ready, the direction served first alternates between
  turns.
- Remaining local work forces a zero-timeout next turn rather than a blocking
  selector wait.
- At least 50 percent lower p95 or p99 latency for incoming delivery or ACK
  processing in the primary saturated scenario.
- No keepalive miss during a ten-minute overload run.
- No unidirectional throughput regression above 2 percent.
- No isolated-message latency regression above 5 percent.
- Public `loop_read()` and `loop_write()` retain their existing explicit drain
  behavior; budgets apply only to the built-in scheduler.
- MQTT packet order is never changed and no priority queue is introduced.

## Before Measurement

Pending. Baseline must be recorded after projects 14-16 decisions so the
scheduler is measured against the final read/write engines it will coordinate.

Required baseline rows:

| Workload | Aggregate msg/s | Inbound p95/p99 | ACK p95/p99 | Keepalive |
| --- | ---: | ---: | ---: | ---: |
| Outbound QoS 0 flood + inbound QoS 0 | pending | pending | n/a | pending |
| Outbound QoS 1 + delayed ACK | pending | pending | pending | pending |
| Publish-only | pending | n/a | pending | pending |
| Subscribe-only | pending | pending | n/a | pending |

## Implementation

Planned prototype:

- Add private read and write budget objects/counters scoped to one built-in
  loop turn.
- Make the private read pump and writer return whether locally available work
  remains after reaching a budget.
- Track the last first-served direction and alternate only when both sides are
  ready.
- Run `loop_misc()` at every completed turn even when work remains.
- Re-enter readiness polling with timeout zero when buffered input or queued
  output remains; otherwise compute the normal wait.
- Keep public manual/external loop methods outside this scheduler.
- Remove the prototype if tail latency improves only by sacrificing the
  unidirectional guardrail.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Report throughput and tail latency together; a throughput-neutral
latency win is acceptable, but a result that merely moves starvation from one
direction to the other is not.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
