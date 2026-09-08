# P2g adversarial code review

The P2g tooling is deliberately downstream of production validation and scoring. It uses no API client, `.env` reader, PDF parser, learner-state writer, or promotion action. Candidate templates are loaded only with `candidate_draft` explicitly allowed for offline lint; the production loader and verification service still require `human_verified`.

Fail-closed checks cover invalid JSON, source mismatch, unknown scorer/choice IDs, malformed answers, stale template IDs, and candidate/production ID collisions. The remaining risk is semantic course-content approval: metadata validation cannot certify that a source page supports a pedagogical claim. That decision remains human-owned.
