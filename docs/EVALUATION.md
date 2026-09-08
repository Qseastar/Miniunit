
# Evaluation Plan

## Evaluation Goal

The evaluation shows whether IntroAI Tutor provides more course-grounded and learner-aware support than a direct LLM answer.

This is an MVP evaluation, not a large-scale classroom study.

## Evaluation Question

Does the prototype demonstrate a complete and traceable adaptive tutoring loop for the Search Algorithms unit?

## Compared Settings

### Setting A: Direct LLM Answer

The student asks a general LLM a question and receives a one-time explanation.

### Setting B: Course-Grounded Answer

The system uses structured course knowledge but does not use learner state.

### Setting C: Full IntroAI Tutor MVP

The system uses both structured course knowledge and learner state.

It detects misconceptions, gives a personalized explanation, asks a diagnostic question, evaluates the answer, updates mastery, and recommends the next concept.

## Demo Questions

1. Why can BFS find the shortest path while DFS usually cannot?
2. What is the difference between BFS and Uniform-Cost Search?
3. Why does A* use both g(n) and h(n)?

## Evaluation Dimensions

| Dimension               | Question                                                            |
| ----------------------- | ------------------------------------------------------------------- |
| Correctness             | Is the explanation technically correct?                             |
| Course Alignment        | Does the answer use defined course knowledge points?                |
| Misconception Detection | Does the system identify likely confusion?                          |
| Personalization         | Does the answer depend on learner state?                            |
| Assessment              | Does the system evaluate the student's response?                    |
| Mastery Update          | Does the system update concept-level mastery?                       |
| Recommendation          | Does the system recommend a reasonable next concept?                |
| Explainability          | Can the audience understand why the system made the recommendation? |

## Scoring Rubric

| Score | Meaning                |
| ----- | ---------------------- |
| 0     | Not demonstrated       |
| 1     | Partially demonstrated |
| 2     | Clearly demonstrated   |

## Evidence to Save

For each demo case, save:

- student input;
- learner state before tutoring;
- detected knowledge points;
- detected misconception;
- generated explanation;
- diagnostic exercise;
- assessment result;
- learner state after tutoring;
- recommended next concept.

## Limitations

The current evaluation has several limitations:

- only a small number of demo cases are used;
- learner state is manually initialized;
- the knowledge base only covers the Search Algorithms unit;
- the assessment logic is still simple;
- no large-scale student experiment has been conducted.

These limitations are acceptable for the MVP because the current goal is to demonstrate feasibility.
