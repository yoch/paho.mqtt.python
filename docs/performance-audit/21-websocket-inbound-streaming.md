# 21 - WebSocket Inbound Streaming

## Analysis

Project 07 optimized outbound WebSocket masking and partial sends. Inbound
processing still follows the MQTT parser's exact `recv(n)` requests, which can
turn command, Remaining Length, and body reads into repeated WebSocket frame
parser and underlying socket work. Fragmented frames and interleaved controls
amplify that overhead.

The wrapper can own a bounded raw-frame buffer and a decoded MQTT byte stream,
read the underlying socket in larger chunks, and make already-decoded bytes
visible through `pending()`.

## Preparation

- Build WebSocket byte streams containing 1, 10, and 100 MQTT PUBLISH packets
  per binary frame.
- Split one MQTT packet across 2, 8, and 100 continuation frames.
- Feed network chunks of 1, 2, 7, 128, 1,024, and 65,536 bytes.
- Interleave PING/PONG/CLOSE frames between continuation fragments.
- Measure plain WS and WSS, small and 64-KiB MQTT payloads.
- Count underlying `recv()` calls, wrapper calls, frame parses, copies,
  allocations, peak RSS, throughput, p50, and p95.

## Expected Gain

Priority: P2, transport-specific but potentially large.

- At least 30 percent higher small-message WebSocket receive throughput.
- At least 80 percent fewer underlying reads.
- Lower allocation and frame-parser overhead under fragmentation.

## Acceptance Criteria

- At least 30 percent higher throughput for 1,000 small MQTT PUBLISH packets
  over WebSocket.
- At least 80 percent fewer underlying socket reads.
- No regression above 2 percent for a 64-KiB MQTT PUBLISH.
- Raw and decoded buffering outside the active payload remains below 128 KiB.
- `pending()` includes complete decoded bytes without reporting incomplete MQTT
  data as a complete packet.
- FIN, continuation, masking rules, binary opcode, PING/PONG, CLOSE, partial
  headers, extended lengths, EOF, and TLS `pending()` remain correct.
- PONG/CLOSE responses tolerate partial writes through the normal writer path.
- No public WebSocket option or signature changes.

## Before Measurement

Pending. Measure the accepted project 07 implementation before changing the
inbound half of `_WebsocketWrapper`.

Required baseline rows:

| Transport/frame shape | MQTT packets | Throughput | Underlying reads | Peak RSS |
| --- | ---: | ---: | ---: | ---: |
| WS, one MQTT packet/frame | 1,000 | pending | pending | pending |
| WS, 100 MQTT packets/frame | 1,000 | pending | pending | pending |
| WS, fragmented MQTT packet | 1,000 | pending | pending | pending |
| WSS, small packets | 1,000 | pending | pending | pending |
| WS, 64-KiB packet | 100 | pending | pending | pending |

## Implementation

Planned prototype:

- Add bounded raw-socket and decoded-stream buffers with independent cursors.
- Read up to 64 KiB from the underlying socket when the decoded stream cannot
  satisfy `recv(n)`.
- Parse as many complete frames as available and append binary/continuation
  payload bytes to the decoded stream.
- Process control frames immediately without corrupting continuation state.
- Compact buffers only after a threshold and release views before mutation.
- Report decoded pending bytes through the wrapper's existing socket-like
  interface.
- Route generated control replies through partial-send-safe buffering.
- Remove the prototype if it improves synthetic frame parsing but not the full
  MQTT-over-WebSocket path.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Separate gains from larger socket reads, fewer frame-parser entries,
and fewer decoded-stream copies, with WS and WSS verdict evidence.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
