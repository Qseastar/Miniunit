# Verification quality gate usage

Run from the repository root; all commands are offline and do not read `.env`.

```bash
bash scripts/quality_gate.sh quick
bash scripts/quality_gate.sh strict
bash scripts/quality_gate.sh ci
```

`quick` runs compile, gate, acceptance, P2g tests, and smoke tests. `strict` adds the full suite. `ci` is the non-interactive strict variant. Reports go to `/tmp/introai_verification_quality.{json,md}` by default.

For one direct gate run:

```bash
PYTHONPATH=src python tools/verification_quality_gate.py --strict \
  --json-report /tmp/introai_verification_quality.json \
  --markdown-report /tmp/introai_verification_quality.md
```

Use `--lint-candidate` or `--promotion-readiness` only for structural staging checks. They never promote a candidate. Missing local PDFs do not affect metadata checks; visual page review remains a local human task.

The gate always validates tracked `data/course_material_manifest.json`, course chunks, source roles, filenames, physical page ranges, and template source refs. It deliberately does not require ignored PDFs in `local_materials/`, so GitHub Actions remains offline and repository-only. To validate real authorized local PDFs separately, run:

```bash
INTROAI_REQUIRE_LOCAL_MATERIALS=1 \
PYTHONPATH=src python tools/verify_local_course_materials.py --require
```

This local integrity command compares SHA-256, file size, and page count with the tracked manifest. It never downloads materials, and placeholder PDFs are prohibited.

Candidate source refs default to evidence. Use `"context_only": true` only for a documented heading or continuity page, never for the primary evidence page. A candidate still needs a non-context source covering its primary concept; use `"primary_evidence": true` when a reviewed source is the explicit core anchor. Typical failures are `SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE`, `SOURCE_NO_PRIMARY_EVIDENCE`, `SOURCE_PRIMARY_TOPIC_MISMATCH`, and `SOURCE_CONTEXT_ONLY_TYPE_INVALID`.

`--promotion-readiness` reports structural source-gate readiness only. Its
`owner_approval_pending=true` means independent production-promotion authorization is still pending;
it does not overwrite the final content decision recorded in the authoritative P2f review card. The
report always keeps `promotion_pending=true` and `automatic_promotion=false`; it never approves or
promotes a template.

Common failures: fix the reported schema/source/scorer contract at its authority, rerun the focused test, then rerun the gate. Do not solve a source failure by inventing a source, a candidate warning by changing production status, or a scoring failure by weakening an assertion.
