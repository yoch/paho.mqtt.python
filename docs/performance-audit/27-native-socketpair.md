# 27 - Native Socket Pair

## Analysis

The threaded-loop wakeup channel is created by a private compatibility helper
that binds a TCP listener on loopback, connects a client socket, accepts the
connection, and closes the listener. This emulates `socket.socketpair()` at
the cost of several syscalls, an ephemeral TCP port, and extra failure paths.

`socket.socketpair()` is available on Windows since Python 3.5 and is therefore
guaranteed on every platform supported by the new Python 3.9 floor. The
existing helper can remain as the private abstraction while its implementation
becomes a native pair with both endpoints set non-blocking.

## Preparation

- Extend wakeup tests to cover repeated creation/destruction, `loop_start()` /
  `loop_stop()`, pair replacement while a wakeup is pending, coalesced writes,
  concurrent restart, and file-descriptor cleanup.
- Add a benchmark for pair creation, first-wakeup latency, and preparation and
  teardown of 1, 100, and 1,000 clients.
- Record wall and CPU time, p50/p95/p99, socket-related syscall counts where
  available, descriptor counts, and failures.
- Use two warmups and seven runs during tuning, then fifteen paired final runs;
  pin sub-millisecond measurements to one CPU.
- Validate on Linux locally and make Python 3.9 Windows a mandatory final
  portability gate.

## Expected Gain

Priority: P2.

The exploratory helper-only median is 67.7 microseconds for the loopback TCP
emulation and 9.1 microseconds for `socket.socketpair()`, a 7.4-fold speedup or
about 86.6 percent less creation time. The improvement affects client
preparation, threaded-loop restart, descriptor pressure, and reliability; it
does not claim a steady-state MQTT throughput or wire-traffic gain.

## Acceptance Criteria

- Reduce pair-creation median by at least 50 percent.
- Reduce the preparation phase for many clients by at least 10 percent.
- Do not regress first-wakeup or `loop_start()` / `loop_stop()` latency by more
  than 2 percent.
- Preserve non-blocking behavior, wakeup coalescing, callback ordering,
  concurrent restart, and descriptor cleanup with no lost wakeup or deadlock.
- Pass the focused suite on Python 3.9 for Windows before an unconditional
  final verdict; a local-only result must remain `GO with conditions`.

## Before Measurement

The final baseline will use the committed result of plan 26, whether its
prototype is retained or removed. The initial isolated probe is:

| Pair implementation | Median creation time |
| --- | ---: |
| Loopback TCP compatibility helper | 67.7 us |
| Native `socket.socketpair()` | 9.1 us |

This probe is motivational only. It does not yet establish the many-client
preparation gain or Windows behavior required by the acceptance criteria.

## Implementation

Pending. Keep `_socketpair_compat()` as the single call site and return a
native pair after setting both sockets non-blocking. No new public option or
platform-specific event primitive is planned.

## After Measurements

Pending implementation and final paired measurement.

## Results Analysis

Pending. The result must separate the large helper microbenchmark delta from
the smaller end-to-end client lifecycle effect, and must report portability
validation rather than assuming it from the local platform.

## Verdict

**Pending.** Stop for explicit evaluation after correctness, lifecycle, and
paired performance results.
