# 18 - Segmented Outbound Payloads

## Analysis

`_send_publish()` builds one contiguous `bytearray` and copies the entire
payload. For large immutable `bytes`, this duplicates memory and delays the
first socket write until the copy completes.

Mutable `bytearray` inputs must remain on the current contiguous construction
path. This project must not silently change the existing QoS queue semantics
for a mutable object waiting behind the inflight limit. TLS and WebSocket also
retain their current contiguous plaintext/frame buffers.

## Preparation

- Measure construction and traced allocations at 128 B, 1 MiB, and 64 MiB.
- Compare paired TCP/Unix transmission, total time, first send, and send calls.
- Test QoS 0/QoS 1, immutable and mutable inputs, partial writes, EAGAIN at the
  segment boundary, reference lifetime, WebSocket fallback, and small messages.
- Keep project 16 excluded: its `sendmsg()` prototype remains isolated.

## Expected Gain

Priority: P1/P2, focused on large-payload publishers.

- At least 50 percent lower additional memory for a 64-MiB immutable payload.
- At least 10 percent higher throughput, or neutral throughput with the memory
  criterion met.
- Much earlier first-byte submission, with no intentional queueing delay.
- No gain expected for mutable, TLS, WebSocket, or small-message paths.

## Acceptance Criteria

- At least 50 percent lower peak additional memory at 64 MiB on TCP/Unix.
- At least 10 percent higher throughput, or within 2 percent while meeting the
  memory target.
- No regression above 2 percent below 1 KiB.
- `bytearray` stays on the current contiguous-copy path.
- QoS 0 releases the immutable source at packet completion; QoS 1/2 retains it
  only while required for retransmission.
- Partial writes across header/payload boundaries update positions correctly.
- QoS callbacks, `MQTTMessageInfo`, ordering, DUP, and replay remain unchanged.
- TLS, WebSocket, and payloads below the threshold remain contiguous.

## Before Measurement

The baseline is the current contiguous writer; project 16 is not included.
Construction/allocation measurements use two warmups and 15 runs, with the
source payload allocated before tracing:

| Immutable payload | Median construction | Peak traced allocation |
| ---: | ---: | ---: |
| 128 B | 0.061 ms | 795 B |
| 1 MiB | 0.276 ms | 1,049,332 B |
| 64 MiB | 43.018 ms | 67,109,621 B |

In the paired local-socket control, a contiguous 64-MiB PUBLISH takes 58.101 ms
on Unix and 67.899 ms on TCP. Its first `send()` starts after 38.776 ms and
40.764 ms respectively because packet construction first copies the payload.

## Implementation

- For immutable `bytes` of at least 16 KiB on plain TCP/Unix, retain a private
  `(header, payload)` tuple instead of extending one `bytearray`.
- `_packet_write()` sends both segments immediately when writable; it never
  waits for another message or a batch.
- The existing global packet position maps partial writes across the boundary;
  no second queue or packet class is introduced.
- Payloads below 16 KiB, `bytearray`, TLS, and WebSocket retain the exact
  contiguous builder.
- QoS 0 releases the payload reference at packet completion. QoS 1/2 retain it
  in the authoritative message until ACK completion for retransmission.
- EAGAIN after the header leaves the payload queued at the correct position.

Two reusable evaluators cover construction/allocation and paired local
TCP/Unix transmission. Tests cover identity retention, exact wire bytes,
partial writes, EAGAIN, reference release, mutable input, WebSocket, and small
payload fallback.

## After Measurements

Construction/allocation after segmentation:

| Immutable payload | Median construction | Peak traced allocation | Reduction |
| ---: | ---: | ---: | ---: |
| 128 B | 0.043 ms | 795 B | unchanged path |
| 1 MiB | 0.052 ms | 872 B | **99.92%** |
| 64 MiB | 0.055 ms | 874 B | **>99.99%** |

Paired local-socket results (two warmups, seven ABBA runs):

| Transport/payload | Contiguous | Segmented | Gain | First send | Calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unix, 1 MiB | 0.416 ms | 0.264 ms | **+57.3%** | 0.155 -> 0.013 ms | 1 -> 2 |
| Unix, 64 MiB | 58.101 ms | 14.667 ms | **+296.1%** | 38.776 -> 0.031 ms | 1 -> 2 |
| TCP, 1 MiB | 0.717 ms | 0.399 ms | **+79.8%** | 0.143 -> 0.018 ms | 1 -> 2 |
| TCP, 64 MiB | 67.899 ms | 21.425 ms | **+216.9%** | 40.764 -> 0.032 ms | 1 -> 2 |

The 128-byte path is unchanged by construction. Its socket/thread harness time
is too small and noisy to use as a regression signal; the 16-KiB threshold
prevents it from entering segmented code.

Focused tests passed 25/25. The enlarged suite passed **196 tests with 21
skipped**.

## Results Analysis

Paho no longer allocates a second 64-MiB payload-sized packet. The application
source remains live until protocol-safe completion; the reduction concerns
additional Paho allocation, not application-owned memory.

The extra `send()` does not offset the removed copy at 1 MiB or 64 MiB. Time to
first byte improves by one to three orders of magnitude because the header can
be submitted without copying the payload. This benefit is independent of
project 16 and does not rely on `sendmsg()`.

The threshold isolates the small-message workloads that dominate realistic
publish smoke results. TLS and WebSocket are unchanged. Remaining risk is
transport realism: a broker-backed run should confirm RSS, QoS 1 ACK/replay,
connection loss, and p95/p99 latency before upstream submission.

## Verdict

**GO with conditions.** Keep segmentation only for immutable `bytes` payloads
of at least 16 KiB on plain TCP/Unix. Before upstream submission, validate
16 KiB, 1 MiB, and 64 MiB QoS 0/QoS 1 against a real broker, including slow
receivers, disconnect/replay, RSS, and tail latency. Any mutation, ordering,
lifecycle, or small-message regression changes the verdict to `NO GO`.
