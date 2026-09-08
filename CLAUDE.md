
# CLAUDE.md

## Project Goal

Build IntroAI Tutor, a course-grounded adaptive tutoring prototype for the Search Algorithms unit of Introduction to Artificial Intelligence.

The project is a two-week MVP. The goal is to demonstrate a small but complete tutoring loop, not to build a full learning platform.

## Current MVP Scope

Only support the Search Algorithms unit.

The MVP learning loop is:

1. read student question or learning goal;
2. read learner state;
3. diagnose the relevant knowledge gap;
4. retrieve structured course knowledge;
5. generate a personalized explanation;
6. provide a short exercise;
7. evaluate the student's answer;
8. update mastery;
9. recommend the next concept.

## Do Not Build Yet

Do not introduce the following unless explicitly approved:

* complex multi-agent architecture;
* graph database;
* web frontend;
* Streamlit app;
* full course platform;
* automatic course ingestion pipeline;
* large-scale user system;
* unnecessary frameworks;
* unnecessary dependencies;
* complete assignment solution generation.

## Technical Direction

Use a simple Python project.

Current expected structure:

```text
data/
  knowledge_points.json

src/
  introai_tutor/

tests/
```

Use JSON for the first version of the course knowledge structure.

Do not introduce a database in the first skeleton round.

Do not modify original course materials.

## Coding Rules

* Keep functions small and readable.
* Prefer standard library before adding dependencies.
* Do not add a dependency without explaining why.
* Every new feature should have a minimal test.
* Do not modify unrelated files.
* Do not rewrite the project structure without approval.
* Do not implement future features while working on a small Issue.

## Knowledge Point Rules

`knowledge_points.json` is the source of truth for the first MVP concept graph.

Each knowledge point should include:

* `id`
* `title_zh`
* `title_en`
* `module`
* `description`
* `prerequisites`
* `learning_objectives`
* `common_misconceptions`
* `mastery_criteria`

All prerequisite IDs must refer to existing knowledge point IDs.

## Academic Integrity Rule

When the system handles course assignments or programming projects, it should provide hints, explanations, debugging guidance, and related concepts.

It should not directly generate complete graded assignment solutions.

## Agent Tooling Rule

When using Claude Code or any coding agent:

1. read relevant files first;
2. produce a short plan before editing;
3. limit changes to the current Issue;
4. run tests after changes;
5. report modified files and verification results.

Never ask the coding agent to “build the whole tutor system” in one step.
