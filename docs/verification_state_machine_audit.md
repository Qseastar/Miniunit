# Verification state-machine audit

States are `answering`, `retry_ready`, and `revealing`, with terminal `completed`. Allowed actions are start, submit, hint retry, reveal, reveal acknowledgement, serialization/restore, and a new isolated start. Submit before start, candidate start, wrong-as-correct, stale template submission, malformed answers, repeated completion, and cross-template session mutation must fail closed.

P2g explores bounded representative paths through the production service: correct, wrong/retry, hint-assisted correct, reveal/acknowledge, JSON round trip, and tampered restore. The traversal is intentionally bounded rather than an unbounded model checker; service history validation remains the authority.
