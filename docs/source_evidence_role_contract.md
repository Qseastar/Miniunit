# Source-evidence role contract

## Scope

This contract applies to production and candidate source metadata, candidate lint, and offline quality reports. It does not change the runtime selector, scorer, evidence pipeline, or learner-state behavior.

## Tracked material manifest and local integrity

`data/course_material_manifest.json` is the CI-verifiable metadata layer for every PDF referenced by `data/course_chunks.json`. It records only a stable material ID, source role, filename, SHA-256, size, current physical page range, and provenance note. It contains no PDF bytes, page text, user data, API data, or absolute local paths.

The actual PDFs remain under ignored `local_materials/` and are never downloaded by CI. Offline validation always checks the tracked manifest against chunks and template source refs. A developer with the authorized local PDFs can separately run `tools/verify_local_course_materials.py --require` to check the actual file, digest, size, and page count. Missing PDFs are `unavailable` in optional mode and fail in required mode.

Do not add placeholder PDFs. If a permitted source PDF changes, regenerate its manifest metadata from the real file and re-review every affected source ref; a digest match does not replace human content review.

## Source ref roles

Every source ref is an **evidence source** unless it explicitly declares `"context_only": true`.

### Evidence source

An evidence source must have a valid ref schema, resolve to an existing chunk, match its source filename, and use an in-range physical page. It must cover the candidate's single primary concept through the chunk's `topic_ids`. Supporting topics alone do not satisfy primary evidence. Evidence sources participate in the candidate's evidence-strength justification. A candidate may mark the source that anchors its core claim with `"primary_evidence": true`; this marker must be a JSON boolean, must not coexist with `context_only: true`, and must itself cover the primary concept.

### Context-only source

A context-only source may establish a section title, continuity, or other explicitly documented context. It must still have a valid ref schema, existing chunk, matching filename, and in-range physical page. It cannot satisfy primary-concept coverage, replace an evidence source, elevate evidence strength, or make a candidate source gate pass by itself. Its role must be explained in the candidate's non-empty source review note.

The gate deliberately does not infer whether the order of otherwise valid context and evidence pages is a
pedagogically sufficient chain. That is an explicit human source-review question; it never relaxes the
non-context primary-evidence invariant.

`context_only` is optional and defaults to `false`; if present, it must be a JSON boolean. Strings, integers, and null are invalid. The same role metadata is retained when an approved candidate is promoted so the production source audit preserves the reviewed evidence chain.

## Required invariants

Every active candidate must have at least one non-context evidence source that covers its primary concept. If it declares a `primary_evidence` anchor, at least one declared anchor must satisfy that rule. A missing or non-matching evidence source is a fail-closed source-gate and candidate-lint error. All-context source lists, context-only-alone lists, and topic-mismatched evidence sources fail.

The accepted IDDFS chain is an example: Lec2 p.53 is a context-only section page; Lec2 p.58 is the non-context, `primary_evidence` page covering `completeness_optimality_complexity`. The BFS/DFS/UCS pages remain non-anchor distractor evidence.

## Evidence strength

- `direct`: the core fact is directly supported by at least one non-context evidence source.
- `supported_inference`: at least one non-context evidence source supports the underlying fact, while the final claim also needs bounded context or inference.
- `insufficient`: no non-context primary evidence exists, the key rule is unrelated, or external knowledge is required.

## Promotion boundary

Passing this contract means only that candidate source metadata is structurally ready for further human review. It never grants owner approval, `human_verified`, promotion, production visibility, or mastery evidence eligibility.
