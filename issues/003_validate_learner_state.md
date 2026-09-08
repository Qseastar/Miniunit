# Issue 003: Validate Learner State Schema

## Goal

Add a minimal learner state schema for the MVP.

This Issue should only validate a demo learner state file. It should not implement agent workflow, database, frontend, LLM calls, or recommendation logic.

## Expected Files

- `data/demo_student_state.json`
- `src/introai_tutor/learner.py`
- `tests/test_learner_state.py`

## Required Fields

The learner state must include:

- `student_id`
- `course_id`
- `mastery`
- `misconceptions`
- `learning_evidence`
- `preferred_style`

## Validation Rules

The validator should check:

1. the learner state JSON can be parsed;
2. required fields exist;
3. `student_id` is a non-empty string;
4. `mastery` is a dictionary;
5. each mastery score is between 0 and 1;
6. each concept ID in `mastery` exists in `knowledge_points.json`;
7. each misconception concept ID exists in `knowledge_points.json`;
8. `learning_evidence` is a list.

## Non-Goals

Do not implement:

- agent workflow;
- LLM calls;
- database;
- frontend;
- recommendation algorithm;
- mastery update algorithm.

## Acceptance Criteria

This Issue is complete when:

- `data/demo_student_state.json` can be loaded;
- invalid mastery scores fail validation;
- unknown concept IDs fail validation;
- missing required fields fail validation;
- all tests pass;
- no new dependencies are introduced.

## Suggested Test Command

```bash
PYTHONPATH=src python3 -m pytest


---

# 2. 写入 demo 学生状态 JSON

复制执行：

```bash
cat > data/demo_student_state.json <<'EOF'
{
  "student_id": "demo_student",
  "course_id": "intro_ai",
  "mastery": {
    "search_problem_formulation": 0.8,
    "state_space_and_operators": 0.7,
    "tree_search_vs_graph_search": 0.6,
    "frontier_and_explored_set": 0.6,
    "breadth_first_search": 0.45,
    "depth_first_search": 0.5,
    "completeness_optimality_complexity": 0.3,
    "uniform_cost_search": 0.2,
    "informed_search_and_heuristics": 0.1,
    "a_star_search": 0.0
  },
  "misconceptions": [
    {
      "concept_id": "breadth_first_search",
      "description": "Confuses shortest path in number of steps with lowest path cost."
    },
    {
      "concept_id": "depth_first_search",
      "description": "Thinks DFS always finds the shortest path."
    }
  ],
  "learning_evidence": [
    {
      "concept_id": "breadth_first_search",
      "activity_id": "demo_diagnostic_001",
      "result": "incorrect",
      "note": "The student did not distinguish BFS from UCS when edge costs differ."
    }
  ],
  "preferred_style": "visual_example"
}
