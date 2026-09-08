
# Issue 001: Load and Validate knowledge_points.json

## Goal

Implement the smallest utility that reads `data/knowledge_points.json` and validates the required fields for each knowledge point.

This Issue is only about data loading and schema validation. It should not implement the tutor agent, retrieval, frontend, memory, or recommendation logic.

## Background

The MVP depends on a stable concept graph. Before building any tutoring workflow, we need to make sure the knowledge point file is valid and internally consistent.

## Files

Expected files:

- `data/knowledge_points.json`
- `src/introai_tutor/knowledge.py`
- `tests/test_knowledge_points.py`

## Required Fields

Each knowledge point must include:

- `id`
- `title_zh`
- `title_en`
- `module`
- `description`
- `prerequisites`
- `learning_objectives`
- `common_misconceptions`
- `mastery_criteria`

## Validation Rules

The validator should check:

1. the JSON file can be parsed;
2. `knowledge_points` exists and is a non-empty list;
3. each knowledge point has all required fields;
4. each `id` is unique;
5. each `prerequisites` value is a list;
6. every prerequisite ID refers to an existing knowledge point ID.

## Non-Goals

Do not implement:

- agent workflow;
- LLM calls;
- retrieval;
- database;
- frontend;
- student memory;
- recommendation algorithm.

## Acceptance Criteria

This Issue is complete when:

- running the validation on `data/knowledge_points.json` succeeds;
- tests pass for a valid file;
- tests fail for missing fields;
- tests fail for duplicate IDs;
- tests fail for unknown prerequisite IDs;
- no unnecessary dependencies are introduced.

## Suggested Command

```bash
python -m pytest
```
