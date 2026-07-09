# 04 - Callback Dispatch and Topic Matching

## Problem

Message delivery can spend non-trivial CPU in callback dispatch and topic
matching when applications register many filtered callbacks. The relevant code
paths are `Client._handle_on_message()` and `MQTTMatcher`.

Likely symptoms:

- Subscriber CPU increases with number of filtered callbacks.
- Wildcard-heavy filters create deeper recursive matching.
- Topic bytes are decoded to string more than once across validation, matching,
  logging, and user callback access.
- Callback list creation allocates even when there are few or no matches.
- Lock scope around callback lookup can add contention when callbacks are added
  or removed dynamically.

Common workloads:

- Gateways subscribing to `#` plus many specific per-device handlers.
- Aggregators using `message_callback_add()` for routing.
- Topics with many path segments and wildcard subscriptions.

## Theoretical Rationale

The matcher already uses a trie, which is the right algorithmic shape. The audit
should focus on constant factors:

- Recursive generators allocate frames and generator state.
- `topic.split("/")` allocates one string per segment.
- `list(iter_match(...))` allocates even if only one callback matches.
- Repeated topic decoding can dominate for short payloads.
- Locking around lookup protects callback data but may include work that does
  not need to run while locked.

Trie lookup should be proportional to topic depth and number of wildcard
branches, not total callback count. Benchmarks should confirm whether that
property holds for realistic filters.

## Expected Gain

Priority: P1.

Conservative expected gain:

- 5 to 20 percent CPU reduction for subscribers with many filtered callbacks.
- Lower allocation count in no-filter and single-filter cases.
- Better p95 callback dispatch latency for wildcard-heavy configurations.

No large gain is expected for clients using only `on_message` without filtered
callbacks.

## Before/After Measurements

Microbenchmarks:

- Match one topic against 0, 1, 10, 100, 1000, and 10,000 filters.
- Use exact filters, single-level wildcard filters, multi-level wildcard
  filters, and mixed filters.
- Measure `Client._handle_on_message()` with no filtered callbacks, one matching
  callback, and many non-matching callbacks.
- Include topics starting with `$` to preserve MQTT system-topic semantics.

Broker scenarios:

- Local subscriber receiving QoS 0 messages with a no-op global callback.
- Same subscriber with 100 and 1000 filtered callbacks.
- Wildcard-heavy subscription routing workload.

Metrics:

- Dispatch time per message.
- Allocations per message.
- p95 dispatch latency.
- Scaling curve by filter count and topic depth.

## Implementation Guidelines

Allowed implementation directions:

- Add a fast path in `_handle_on_message()` when there are no filtered callbacks.
- Avoid creating a list of matched callbacks when only iteration is needed, while
  preserving behavior if callbacks mutate registrations.
- Consider iterative trie traversal to replace recursive generator overhead.
- Cache split topic segments or decoded topic string per message if it reduces
  repeated work without changing `MQTTMessage.topic` behavior.
- Keep `$` topic matching rules exactly as implemented.
- Keep callback invocation outside structural mutation risk.

Risks:

- Callback mutation during dispatch is supported and must remain safe.
- Iterating directly over matcher internals may break if callbacks remove other
  callbacks.
- Preserving callback order may matter for users even if not explicitly
  documented.

## Acceptance Criteria

Functional criteria:

- Existing matcher tests pass.
- Add tests for callback add/remove during callback execution.
- Add tests for `$` topic matching with exact, `+`, and `#` filters.
- Add tests for multiple matching callbacks.

Performance criteria:

- No-filter `_handle_on_message()` path is at least 5 percent faster or has
  measurably fewer allocations.
- 1000-filter exact/wildcard benchmark improves by at least 10 percent without
  changing matches.
- No regression above 2 percent for simple global `on_message` dispatch.

Documentation criteria:

- Record the matching complexity observed for exact, wildcard, and mixed
  filters.
- Document callback mutation semantics used by the implementation.

## Verdict

GO with conditions.

Justification: topic matching is algorithmically sound but likely has avoidable
constant overhead. Proceed after P0 parser/codec work unless profiling shows
callback routing dominates a target workload.
