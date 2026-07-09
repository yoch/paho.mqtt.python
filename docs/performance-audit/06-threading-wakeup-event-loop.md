# 06 - Threading Wakeup and Event Loop

## Problem

The network loop must coordinate sockets, callbacks, and cross-thread publish
calls. The relevant code paths include `loop()`, `_loop()`, `loop_start()`,
`loop_stop()`, `_packet_queue()`, `_call_socket_register_write()`,
`_call_socket_unregister_write()`, and locks such as `_callback_mutex`,
`_in_callback_mutex`, `_out_message_mutex`, and `_msgtime_mutex`.

Likely symptoms:

- High system CPU under `loop_start()` with frequent cross-thread publishes.
- Excess socketpair wakeups when many packets are queued before one loop drain.
- Lock contention when publishing, receiving, and callbacks run concurrently.
- Repeated write registration changes for external event loops.
- Wakeup overhead hiding actual packet processing cost in profiles.

Common workloads:

- Application threads publishing telemetry while Paho runs its network thread.
- Async applications using external event loop integration.
- Callbacks that publish follow-up messages.

## Theoretical Rationale

Cross-thread wakeups require kernel involvement and often trigger context
switches. A single wakeup can drain many queued packets, so per-packet wakeups
are wasteful during bursts. Lock acquisition is usually cheap when uncontended
but can become expensive when callbacks, publishing, and loop operations compete
under the GIL.

The design should distinguish three cases:

- Network thread already awake and draining.
- Network thread blocked in `select()`.
- External event loop owns readiness notifications.

Each case has different optimal wakeup behavior.

## Expected Gain

Priority: P1.

Conservative expected gain:

- 10 to 30 percent lower system CPU for threaded publish bursts if wakeups are
  currently per-packet.
- 5 to 15 percent throughput improvement for producer workloads.
- Lower p95 publish-to-send latency during bursts if queue drain is more
  efficient.

The gain is likely small for single-threaded manual `loop()` users.

## Before/After Measurements

Microbenchmarks:

- Count socketpair writes for 1, 10, 100, and 10,000 `_packet_queue()` calls.
- Measure time for publish bursts from one, two, and four producer threads.
- Measure lock wait time using lightweight instrumentation around key locks.
- Measure external event loop registration callback counts.

Broker scenarios:

- `loop_start()` QoS 0 publish burst from a worker thread.
- Callback publishes a response message while receiving.
- External selector integration using `loop_read()`, `loop_write()`, and
  `loop_misc()`.

Metrics:

- Socketpair writes and reads.
- Context-switch proxy metrics where available.
- User/system CPU split.
- Messages per second.
- p95 publish-to-send latency.
- Register/unregister callback counts.

## Implementation Guidelines

Allowed implementation directions:

- Add a private wakeup state flag protected by existing queue semantics or a
  minimal lock.
- Clear the wakeup flag only when the socketpair has been drained and the output
  queue has been observed.
- Avoid wakeup coalescing for external event loop mode unless registration
  semantics are preserved.
- Reduce lock scope around timestamp updates and callback lookup if profiling
  proves contention.
- Keep `_in_callback_mutex` behavior that prevents recursive network writes from
  unsafe contexts.

Risks:

- Lost wakeups can stall outgoing packets until the next keepalive or timeout.
- Over-coalescing can improve throughput while hurting low-volume latency.
- External event loop integration is sensitive to write registration semantics.
- Lock changes can introduce rare races.

## Acceptance Criteria

Functional criteria:

- Existing asyncio/select examples and tests continue to work.
- Add tests for burst publish waking a sleeping loop exactly enough to drain.
- Add tests for external event loop write registration behavior.
- Add tests for publish from callback.

Performance criteria:

- At least 50 percent fewer socketpair writes during a 10,000-message burst.
- At least 10 percent lower system CPU in threaded burst benchmark.
- No p95 latency regression above 5 percent for single-message publish while
  the loop is sleeping.

Documentation criteria:

- Document the wakeup state machine.
- Record which mode is optimized: threaded loop, manual loop, or external loop.

## Verdict

GO with conditions.

Justification: wakeup coalescing can deliver meaningful CPU savings in real
producer workloads, but lost-wakeup risk is serious. Implement only with focused
threaded and external-loop tests.
