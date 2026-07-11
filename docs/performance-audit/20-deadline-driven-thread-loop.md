# 20 - Deadline-Driven Thread Loop

## Analysis

`loop_start()` enters `loop_forever()` with a one-second timeout, so an idle
client wakes once per second even when its keepalive deadline is a minute away.
`loop_stop()` sets a flag but does not wake the selector, and reconnect backoff
polls termination through one-second sleeps. This wastes idle CPU and makes
lifecycle latency depend on polling intervals.

The existing socketpair can wake the selector for stop as well as publish. A
private event can make reconnect backoff interruptible, while a deadline
calculation can sleep until the next real MQTT timer.

## Preparation

- Measure 1, 10, and 100 idle clients for keepalive values 10, 60, and 300 s.
- Record selector wakeups, user/system CPU, voluntary/involuntary context
  switches, thread count, and RSS over at least ten minutes.
- Measure `loop_stop()` during selector wait, queued output, reconnect backoff,
  and immediately after a wakeup race.
- Measure single-message publish-to-send latency while the thread is sleeping.
- Keep blocking DNS, TCP connect, TLS handshake, proxy, and WebSocket handshake
  outside the sub-50-ms stop guarantee and report them separately.

## Expected Gain

Priority: P1.

- More than 90 percent fewer idle selector wakeups at keepalive 60.
- At least 80 percent lower aggregate idle CPU for 100 clients.
- Sub-50-ms stop latency during selector wait and reconnect backoff.
- No active-traffic throughput or wakeup-latency regression.

## Acceptance Criteria

- At least 90 percent fewer selector wakeups at keepalive 60.
- At least 80 percent lower idle CPU for 100 connected clients.
- `loop_stop()` p95 below 50 ms while in `select()` or reconnect backoff.
- Keepalive/PINGRESP deadline drift remains below 1 percent.
- Single-message publish-to-send p95 does not regress by more than 5 percent.
- Active throughput does not regress by more than 2 percent.
- Public `loop()` and `loop_forever(timeout=...)` timeout semantics remain
  unchanged; deadline-driven waits apply only to the internal `loop_start()`
  thread.
- Stopping does not claim to flush publications; queued state remains valid for
  restart/reconnect as documented.
- Wakeup coalescing from project 06 remains race-free when stop and publish
  occur concurrently.

## Before Measurement

Pending. Record the current one-second polling and stop behavior before adding
the event or changing thread-loop timeout selection.

Required baseline rows:

| State | Clients | Duration | Wakeups | CPU | Stop p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Connected idle, keepalive 60 | 1 | 10 min | pending | pending | pending |
| Connected idle, keepalive 60 | 100 | 10 min | pending | pending | pending |
| Reconnect backoff | 1 | 2 min | pending | pending | pending |
| Active small publish | 1 | pending | pending | pending | pending |

## Implementation

Planned prototype:

- Add a private thread-termination `Event` created/reset with `loop_start()`.
- Wake the existing socketpair in `loop_stop()` under the established wakeup
  mutex/state machine.
- Replace reconnect `sleep()` polling with interruptible event waits.
- For the internal thread only, compute selector timeout from last inbound,
  last outbound, PINGRESP timeout, and the next reconnect deadline; allow an
  indefinite wait when keepalive is disabled because socketpair control remains
  available.
- Exit the thread promptly without waiting for `_out_messages` to become empty.
- Preserve all pending queues/state so a later loop/reconnect can continue.
- Remove deadline-driven waiting if timer accuracy or active wakeup latency
  fails its guardrail.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Separate idle CPU savings, selector wakeup reduction, stop latency,
timer accuracy, and the known limitation of blocking connection establishment.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
