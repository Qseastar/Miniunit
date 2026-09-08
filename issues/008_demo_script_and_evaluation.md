
# Issue 008: Add Demo Script and Evaluation Plan

## Goal

Prepare the demo script and evaluation plan for the competition presentation.

This issue connects the engineering MVP with the academic presentation requirements.

## Background

The project is being prepared for an English academic presentation contest. Therefore, the project needs a clear demo story, evaluation logic, and evidence plan before additional engineering work continues.

## Files

This issue adds:

- `docs/DEMO_SCRIPT.md`
- `docs/EVALUATION.md`

## Scope

This issue should define:

1. the main demo scenario;
2. the six-minute presentation structure;
3. the expected system input and output;
4. the evaluation dimensions;
5. the minimal evidence needed for the presentation;
6. the limitations of the current MVP.

## Non-Goals

This issue should not implement:

- new tutor logic;
- frontend UI;
- LLM API calls;
- database support;
- new knowledge points;
- new assessment algorithms.

## Demo Scenario

Main student question:

> Why can BFS find the shortest path while DFS usually cannot?

The demo should show one complete tutoring loop:

student question
-> learner state
-> concept diagnosis
-> course knowledge retrieval
-> personalized explanation
-> diagnostic exercise
-> assessment
-> mastery update
-> next concept recommendation

## Acceptance Criteria

This issue is complete when:

- `docs/DEMO_SCRIPT.md` explains the demo goal, scenario, expected output, and six-minute presentation structure;
- `docs/EVALUATION.md` defines evaluation settings, dimensions, rubric, evidence, and limitations;
- the documents match the requirement of an English academic research presentation;
- no new dependencies are introduced;
- no unrelated code is modified.

## Verification

Run:

```bash
git status
```
