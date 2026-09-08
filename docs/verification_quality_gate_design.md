# Verification quality gate design

## Current architecture

The production chain is intentionally singular:

`template data → loader / validator → selector → verification service → history / summary → evidence gate → state integration → recommendation`

`template_selection.py`, `verification_diagnostics.py`, `dual_track_diagnostics.py`, and `diagnostic_state_integration.py` remain the authorities. P2g tooling calls them read-only; it does not create a parallel loader, scorer registry, selector, evidence pipeline, or learner-state updater.

## Existing automated coverage

Existing acceptance, scorer, selector, handoff, dual-track, history/tamper, and Streamlit AppTest suites cover individual boundaries. Smoke tests cover stable offline release paths. P2g adds a derived manifest and one offline CLI to make the cross-bank assertions repeatable and reviewable.

## Missing unified capabilities addressed by P2g

- One CLI and one derived benchmark view instead of scattered entry points.
- Exhaustive legal answer-space tests for all current single/multiple choice templates.
- Synthetic contract matrices for registered numeric and ordering scorers.
- Data-driven mutation, selector/handoff, replay, and tamper regressions.
- Reproducible source traceability, capability coverage, and review-packet reports.
- Structural candidate lint, local/CI parity, and a documented local gate.

## Reuse boundaries

Production imports are allowed only for validation, selection, scoring, sessions, and integration replay. `tools/` may derive inventories and render reports. It must not change templates, state, review status, or promotion status. Synthetic templates belong only in tests and never enter the loader, selector, or UI.

## Quality-gate stages

1. inventory; 2. schema; 3. source metadata; 4. scoring; 5. exhaustive answers; 6. mutation; 7. selector; 8. handoff; 9. verification replay; 10. history/evidence; 11. UI; 12. reporting; 13. candidate isolation; 14. CI.

## Candidate source roles

Candidate source validation is fail-closed and shared by the gate, candidate lint, and generated inventories. A source is normal evidence unless `context_only=true`. Context pages still need valid chunk, filename, and physical-page metadata, but cannot satisfy primary-concept coverage. Each active candidate needs at least one non-context source covering its primary concept. Reviewed entries may declare the source that anchors the core claim with `primary_evidence=true`; that source must itself be non-context and topic-matching. After promotion, the role metadata remains in the acceptance/source audit contract so context chains stay auditable; the runtime template schema is unchanged.

## Report schema

The JSON gate report contains `schema_version`, `run_metadata`, bank counts, inventories, source/answer-position/eligibility summaries, positive/wrong/malformed summaries, candidate-isolation summary, `warnings`, and `failures`. Each template entry contains identity, bank, concept, review status, scorer/type, scoring counts, source status, expected position, eligible intents, capability boundary, status, warnings, and failures.

## Exit codes

- `0`: all required checks passed.
- `1`: quality failure.
- `2`: configuration or input error.
- `3`: internal tool error.
- `4`: strict-mode warning escalation.

Warnings never silently hide failures. Candidate structural readiness is not human course approval.
