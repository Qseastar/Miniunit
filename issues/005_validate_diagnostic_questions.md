# Issue 005: Validate Diagnostic Questions Schema

## Goal

Create a fixed diagnostic question schema for the Search Algorithms MVP.

This Issue uses a manually written JSON file. It does not generate questions automatically.

## Expected Files

- `data/diagnostic_questions.json`
- `src/introai_tutor/questions.py`
- `tests/test_diagnostic_questions.py`

## Required Fields

Each diagnostic question must include:

- `id`
- `concept_ids`
- `question_text`
- `expected_answer`
- `rubric`
- `difficulty`

## Content Requirement

The first diagnostic question file should include at least 15 questions covering:

- search problem formulation;
- BFS;
- DFS;
- completeness;
- optimality;
- uniform-cost search;
- heuristic functions;
- A*;
- admissibility;
- consistency.

## Validation Rules

The validator should check:

1. the JSON file can be parsed;
2. `diagnostic_questions` exists and is a non-empty list;
3. each question has all required fields;
4. each `id` is a non-empty string;
5. each `id` is unique;
6. each `concept_ids` value is a non-empty list;
7. every concept ID refers to an existing knowledge point ID;
8. each `difficulty` value is one of `easy`, `medium`, or `hard`.

## Non-Goals

Do not implement:

- automatic question generation;
- LLM calls;
- frontend;
- answer grading;
- mastery update logic.

## Acceptance Criteria

This Issue is complete when:

- `data/diagnostic_questions.json` exists;
- at least 15 questions exist;
- invalid concept IDs fail validation;
- duplicate question IDs fail validation;
- invalid difficulty values fail validation;
- all tests pass;
- no unnecessary dependencies are introduced.

## Suggested Test Command

```bash
PYTHONPATH=src python3 -m pytest
```
