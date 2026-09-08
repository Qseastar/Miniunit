# P2f source-evidence gate hardening progress

## Baseline audit

- Existing branch: `feature/p2f-owner-review-revisions`.
- Existing uncommitted work: the expected owner-review revision files; production data and `src/introai_tutor/` are unchanged.
- Reproduced defect: a sole `context_only` source could pass `_source_status`, including an unrelated chunk.
- Next: centralize source-role validation, then add adversarial tests, inventories, reports, and a short re-review.

## Source-role contract

- Added `source_evidence_role_contract.md` before implementation.
- Contract requires non-context primary evidence and makes context-only supplemental only.
- Blocker: none; proceed with tooling-only implementation.

## Shared validation, adversarial matrix, and inventory

- Added one fail-closed `validate_source_roles()` helper used by the quality gate, candidate lint,
  and source-role inventory; no parallel validator was added.
- `context_only` now has strict boolean validation and never counts toward primary-concept evidence.
  Non-context evidence remains subject to chunk, filename, page-range, and primary-topic checks.
- Added candidate-only `primary_evidence=true` for the IDDFS p.58 core properties page. This anchor
  must be non-context and topic-matching; p.53 remains contextual only.
- Added synthetic/mutation/CLI/inventory regressions. Real p.53+p.58 passes; p.53 alone and p.58
  converted to context-only fail closed.
- Generated source traceability and source-role inventory reports. The pre-promotion result was 13
  production templates and 7 candidates; after P2f promotion the result is 20 production templates,
  0 candidates, 1 blocked slot, 29 refs, 1 context-only ref, and no invalid source roles.

## Final owner decision and pre-commit closure

- The authoritative review card records `approve` for all seven candidates and `keep_blocked` for
  `verify_ucs_frontier_update_v1`; the seven approved entries are now production `human_verified`.
- Generated packet `owner_decision` fields remain blank by design; the packet points reviewers to
  the authoritative review card and never performs approval or promotion.
- Directed tooling tests and the post-promotion source gate pass; source inventory is 20 production /
  0 candidates / 1 blocked with 29 refs and one context-only ref.
- Quick, strict, smoke, full, and collection checks have completed offline. No production data or
  Python changed, and no Git write operation was performed.
