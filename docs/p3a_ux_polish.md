# P3a UX polish

## Conditional scrolling

Scrolling is a session-local, one-shot progressive enhancement. A request has
only a whitelisted target and an internal event token; it never contains a
learner question, answer, course content, or persisted learner data.

- Ordinary course Q&A does not scroll automatically. When a reviewed plan is
  available, the reviewed-diagnostic area appears after the answer/sources with
  a count such as **已找到 1 道与本题相关的人工审核诊断题，完成后可更新学习记录。**
  It has one primary action, **开始审核诊断（1题）** (or the actual count),
  which starts the diagnostic directly and then locates the first question.
- An explicit diagnostic request with an available reviewed plan scrolls once
  to the handoff card, but never starts a diagnostic automatically and does not
  render a second CTA. The previous two-step “前往审核诊断” flow was removed:
  its first scroll was only a small movement to the already visible handoff
  area, and subsequent one-shot events correctly did nothing.
- Starting a diagnostic and entering a new question scroll once to the current
  prompt. Hint, reveal, option-selection, and ordinary reruns do not request a
  scroll.
- Completion scrolls once to the mastery summary. Returning to Q&A clears old
  diagnostic requests and scrolls once to the Q&A input.
- Browser/profile recovery restores learner state only. It never restores a
  scroll request.

Anchors use fixed IDs. The small local script uses `scrollIntoView`, honors
`prefers-reduced-motion`, and safely does nothing if the parent document cannot
be reached. No external JavaScript, CDN, or third-party component is used.

## Concept labels

Student-facing labels come from the authoritative `title_zh` field in
`data/knowledge_points.json`. Internal concept IDs remain stable in workflow,
persistence, and developer details; student tables, recommendations, and
matched-topic displays use Chinese titles. Unknown IDs render as a safe Chinese
fallback rather than exposing a snake_case implementation identifier.

## Automated and manual verification

Unit tests verify one-shot scroll request consumption, target whitelisting,
new-profile/reset cleanup, reduced-motion markup, and display-name coverage.
Streamlit AppTest can verify rendered anchors and state transitions, but cannot
reliably verify physical browser scrolling inside the browser viewport. Manual
acceptance should therefore verify: ordinary Q&A stays in place; an explicit
diagnostic request reaches the handoff; start/next/completion reach their
respective anchors once; return preserves learning records; refresh and a new
profile do not replay an old scroll.

This P3a scope does not add a knowledge graph, diagnostic content, scoring
rules, telemetry, or changes to mastery and evidence policy.
