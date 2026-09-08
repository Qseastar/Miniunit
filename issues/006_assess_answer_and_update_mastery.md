# Issue 006: Assess Answer and Update Mastery

## Goal

Implement the evaluation and mastery update step of the MVP tutoring loop.

When a student answers a question, the system should evaluate the answer, update the mastery score for the corresponding concept, and record the interaction as learning evidence.

## Expected Files

- `src/introai_tutor/assessment.py`
- `tests/test_assessment.py`
- `issues/006_assess_answer_and_update_mastery.md`

## Design

### `evaluate_answer(student_answer, expected_keywords, *, case_sensitive=False)`

Evaluate a free-text answer against a list of expected keywords.

| Match level | Result |
|---|---|
| All keywords found | `"correct"` |
| Some keywords found | `"partially_correct"` |
| No keywords found | `"incorrect"` |
| No keywords provided | `"unknown"` |

Matching is case-insensitive by default.

### `update_mastery(learner_state, concept_id, result, *, learning_rate=0.15)`

Update mastery score using exponential moving average:

```
new = old + learning_rate × (target − old)
```

| Result | Target |
|---|---|
| `"correct"` | 1.0 |
| `"partially_correct"` | 0.7 |
| `"incorrect"` | 0.0 |

The score is always clamped to [0.0, 1.0].

### `record_learning_evidence(learner_state, concept_id, activity_id, result, note)`

Append an evidence entry to `learner_state["learning_evidence"]`.

### `add_misconception(learner_state, concept_id, description)`

Record a detected misconception.

### `assess_answer(learner_state, concept_id, student_answer, expected_keywords, *, activity_id, learning_rate, case_sensitive)`

Full assessment pipeline: evaluate → update mastery → record evidence.

## Validation Rules

1. `update_mastery` rejects invalid result strings (anything outside `correct`/`partially_correct`/`incorrect`).
2. Mastery scores stay within [0.0, 1.0].
3. Missing concepts default to mastery 0.0.
4. When evaluation result is `"unknown"`, mastery is left unchanged.
5. `learning_evidence` and `misconceptions` lists are auto-created if missing.

## Non-Goals

Do not implement:

- LLM-based evaluation;
- natural language understanding;
- rubric-based grading;
- database persistence;
- frontend UI.

## Acceptance Criteria

This Issue is complete when:

- `evaluate_answer` correctly classifies correct / partially_correct / incorrect / unknown;
- `update_mastery` increases mastery for correct, decreases for incorrect;
- mastery converges toward 1.0 after repeated correct answers;
- mastery converges toward 0.0 after repeated incorrect answers;
- invalid result strings raise `ValueError`;
- `assess_answer` runs the full pipeline and records evidence;
- all tests pass;
- no new dependencies are introduced.

## Suggested Test Command

```bash
PYTHONPATH=src python -m pytest tests/test_assessment.py -v
```
