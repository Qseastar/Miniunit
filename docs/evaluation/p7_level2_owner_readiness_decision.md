# P7 Level 2 Human-Owner Readiness Decision

## Formal decision

The human owner has formally decided:

`IntroAI Tutor P7 → LEVEL 2 — external assessment items owner-reviewed`

This is a project/research instrument readiness decision. It is not a production promotion and
does not change the candidate-bank lifecycle fields. The machine-readable record is
`data/evaluation/p7_readiness_status.json`.

## Accepted instrument baseline

The owner accepts the current 11-item asymmetric research-only bank across 6 selected concepts:

| Concept | Active items |
| --- | ---: |
| BFS | 2 |
| UCS | 2 |
| A* | 2 |
| Local Search | 1 |
| Minimax | 2 |
| MCTS | 2 |

The owner accepts that the bank is not forced into `6 concepts × 2 items`. The Local Search second
slot remains:

`LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE`

`p7_ext_local_search_representation_b` is not restored to the active bank. The lack of a second
Local Search item is intentional and documented, not accidental missing data.

There is currently no owner-reviewed strict immediate/delayed parallel pair. This does not block
Level 2 because Level 2 is defined as external assessment items owner-reviewed; it remains a
limitation for future delayed-retention study design.

`p7_ext_minimax_two_level_b` remains `TRANSFER_EXPLORATORY_ONLY` and is not represented as a strict
parallel form.

## Scientific interpretation

Level 2 means only that the external assessment instrument has completed human-owner content review.
External results remain an **independent course-grounded performance criterion**. They do not mean:

- mastery validated;
- psychometric validity;
- human-study approval;
- learning gains;
- true mastery or ground-truth knowledge;
- calibrated mastery probability.

## Human-study boundary

```text
human_study_authorized = false
CHECK_BEFORE_REAL_HUMAN_STUDY = UNRESOLVED
```

Before any recruitment or real administration, the separate checkpoint must address voluntary
participation, research-purpose disclosure, no grade consequence, withdrawal rights, minimal data,
retention/deletion, advisor requirements, school/institutional requirements, and participant
protection. This decision does not complete or waive any of those requirements.

## Historical preservation and candidate lifecycle

P7a, P7b, P7c and P7d remain historical records of their real-time states and decisions. They are
not rewritten to retroactively say Level 2. The candidate JSON continues to use
`assessment_status=pending_owner_review` and item-level `human_review_status=pending_owner_review`.
Those fields describe the research-only candidate-bank lifecycle and are intentionally separate from
this project-level readiness record. A future cleanup may introduce an explicit candidate-level
owner approval state; that is representation debt, not part of this promotion.

## Isolation and privacy

The external bank remains outside the production diagnostic registry and cannot write mastery,
learner state, recommendation, exposure or production evidence. No participant identity, learner
UUID, QA transcript, PDF content, secret or device metadata is introduced. Missing external results
remain `null` with a controlled `missing_reason`.
