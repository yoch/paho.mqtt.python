# 25 - TLS Session Resumption

## Analysis

Every TLS reconnect currently wraps a new TCP socket and performs a full
blocking TLS handshake. Python's `SSLContext.wrap_socket()` can accept an
`SSLSession`, and a server may resume it without weakening certificate or
hostname verification. Reconnect-heavy gateways and unstable links could save
substantial latency and CPU.

Session behavior varies across TLS 1.2, TLS 1.3, OpenSSL versions, brokers, and
custom contexts. The feature must be a transparent best-effort optimization
with automatic full-handshake fallback and strict target/context identity.

## Preparation

- Configure local TLS 1.2 and TLS 1.3 broker endpoints with session reuse
  enabled and disabled.
- Measure first connect followed by 20 and 100 reconnects over TCP and secure
  WebSocket.
- Test server rejection/expiration, context mismatch, host/port change, client
  certificates, certificate failure, and reinitialise.
- Record TCP-to-CONNACK wall time, handshake wall/CPU time, bytes transferred,
  `session_reused`, success/failure counts, and allocations.
- Run on every locally available supported Python/OpenSSL combination; Python
  3.7 compatibility remains mandatory even if the main matrix starts later.

## Expected Gain

Priority: P2.

- At least 25 percent lower median reconnect latency when resumption succeeds.
- At least 20 percent lower handshake CPU or wire traffic.
- Negligible overhead when the broker refuses or cannot resume.

## Acceptance Criteria

- Cache a session only after a verified successful handshake.
- Reuse only with the identical `SSLContext` object, hostname, port, and TLS
  transport role.
- Clear cached sessions on target/context change, reinitialise, certificate
  error, or incompatible-session error.
- Never change certificate validation, hostname checking, SNI, ALPN, client
  certificate, cipher, or proxy behavior.
- At least 25 percent lower median reconnect time or 20 percent lower handshake
  CPU in at least one representative TLS version, with the other explicitly
  documented.
- No full-handshake fallback regression above 3 percent.
- MQTT CONNACK/session state remains independent of TLS session reuse.
- Secure WebSocket and raw MQTT/TLS both remain correct.
- If portability or fallback cannot be guaranteed across supported Python
  versions, remove the production prototype.

## Before Measurement

Pending. Measure full handshakes with the existing TLS fixtures and a local
broker before storing any session object.

Required baseline rows:

| Transport | TLS | Reconnects | Median connect | CPU | Bytes | Reused |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MQTT/TCP | 1.2 | 20 | pending | pending | pending | 0 |
| MQTT/TCP | 1.3 | 20 | pending | pending | pending | 0 |
| WSS | 1.2 | 20 | pending | pending | pending | 0 |
| WSS | 1.3 | 20 | pending | pending | pending | 0 |

## Implementation

Planned prototype:

- Add private cached session and session-key fields to `Client`.
- After successful handshake, store `ssl_sock.session` and its context/target
  identity when the runtime exposes session APIs.
- On a matching reconnect, pass the cached object through
  `SSLContext.wrap_socket(session=...)`.
- Let OpenSSL perform a normal full handshake when the server declines reuse.
- On a local incompatibility before a valid handshake, discard the session and
  retry through the established safe connection path without suppressing
  certificate errors.
- Record `session_reused` only for tests/benchmarks; add no public property.
- Remove the prototype if resumed sessions are unreliable or the fallback
  requires unsafe socket reuse.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Report TLS 1.2 and 1.3 independently, including resume success rate,
fallback cost, OpenSSL/Python versions, raw TLS versus WSS, and security checks.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
