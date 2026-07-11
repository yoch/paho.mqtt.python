# 22 - Callback and State-Lock Decoupling

## Analysis

PUBACK/PUBCOMP handling currently invokes `on_publish` while
`_out_message_mutex` is held. A slow callback therefore blocks concurrent
QoS publishing even though user code does not need the internal message map
lock. PUBREL handling similarly invokes `on_message` while
`_in_message_mutex` is held, coupling arbitrary application work to reconnect
and inbound-state operations.

Callbacks must remain synchronous on the network thread and preserve their
ordering and exception behavior. The optimization is to reserve the state
transition, release the state mutex for user code, and finalize afterward.

## Preparation

- Measure concurrent `publish(qos=1)` latency while `on_publish` sleeps for
  0, 1, 10, and 200 ms.
- Measure reconnect/reset attempts from another thread and from inside
  `on_publish`/`on_message`.
- Add QoS 2 PUBREL callbacks with reconnect, publish, callback removal, and
  exceptions.
- Profile the no-callback and no-op-callback paths as regression guards.
- Record producer p50/p95/p99 latency, lock wait, callback throughput,
  deadlock/timeouts, state-map contents, and `MQTTMessageInfo` publication time.

## Expected Gain

Priority: P1.

- Concurrent producers no longer inherit the full duration of `on_publish`.
- Reconnect/inbound-state operations no longer wait on arbitrary QoS 2 message
  callbacks.
- Neutral throughput in the common no-callback and short-callback cases.

## Acceptance Criteria

- With a 200-ms `on_publish`, concurrent `publish(qos=1)` p95 lock-induced
  latency remains below 10 ms.
- No callback is executed while `_out_message_mutex` or `_in_message_mutex` is
  held.
- `MQTTMessageInfo.is_published()` remains false during `on_publish` and becomes
  true at the same logical completion point afterward.
- Inflight capacity remains reserved during the callback so a concurrent
  publisher cannot overtake already queued messages.
- Callback order, callback thread, suppression/propagation of exceptions,
  duplicate ACK behavior, and reconnect semantics remain unchanged.
- No regression above 2 percent without callbacks and 3 percent with a no-op
  callback.
- Callback-triggered publish, disconnect, reconnect, callback exception,
  duplicate ACK/PUBREL, and concurrent reset are race-tested.

## Before Measurement

Pending. Record lock-hold and producer-latency baselines before introducing a
completion-reservation state.

Required baseline rows:

| Callback delay | Concurrent producer p95 | ACK/s | Lock wait | Result |
| ---: | ---: | ---: | ---: | --- |
| 0 ms | pending | pending | pending | pending |
| 1 ms | pending | pending | pending | pending |
| 10 ms | pending | pending | pending | pending |
| 200 ms | pending | pending | pending | pending |

## Implementation

Planned prototype:

- Add a private, normally empty set of outgoing mids whose ACK callback is in
  progress.
- Under `_out_message_mutex`, validate the ACK and reserve its message/inflight
  slot without completing `MQTTMessageInfo` or freeing capacity.
- Release the mutex, invoke `on_publish`, then reacquire it to remove the
  message, release the slot, refill inflight, and publish the info flag.
- If an unsuppressed callback exception escapes, clear the reservation and
  leave the authoritative message recoverable as in the current behavior.
- Make reconnect reset skip a reserved completion; finalization removes the
  already-ACKed message afterward.
- For PUBREL, pop the inbound message under lock, release the lock, invoke
  `on_message`, then continue the existing completion/refill path.
- Do not add an executor, callback queue, or public asynchronous mode.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. The primary verdict is based on producer/reconnect latency and
correctness, not on hiding the callback's unavoidable execution time from the
network thread.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
