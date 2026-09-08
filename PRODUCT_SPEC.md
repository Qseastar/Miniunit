
# IntroAI Tutor Product Spec

## 1. Project Name

IntroAI Tutor: A Course-Grounded Adaptive Learning Agent

## 2. MVP Goal

Build a minimal tutoring prototype for the Search Algorithms unit in Introduction to Artificial Intelligence.

The MVP should demonstrate one complete learning loop:

Student question or learning goal
→ read learner state
→ diagnose the problem
→ retrieve relevant course knowledge
→ provide personalized explanation
→ give a short exercise
→ evaluate the answer
→ update mastery
→ recommend the next concept

## 3. Target User

The first target user is a student learning the Search Algorithms module in an introductory AI course.

The student may understand basic programming but may confuse concepts such as BFS, DFS, path cost, optimality, completeness, heuristics, and A*.

## 4. Core Problem

General-purpose LLMs can answer isolated questions, but they do not reliably track:

* the course knowledge structure;
* prerequisite relationships between concepts;
* the learner's current mastery;
* the learner's previous mistakes;
* the next suitable learning step.

IntroAI Tutor aims to provide course-grounded and learner-aware tutoring instead of one-off question answering.

## 5. MVP Scope

The first version only covers the Search Algorithms unit.

It should include:

* 8–12 manually defined knowledge points;
* prerequisite relationships between knowledge points;
* common misconceptions;
* basic mastery criteria;
* a simple learner state format;
* a minimal diagnostic and recommendation workflow.

## 6. Out of Scope

The MVP will not include:

* full Introduction to AI course coverage;
* complex multi-agent architecture;
* graph database;
* user account system;
* full web platform;
* automatic course generation;
* large-scale educational experiment;
* automatic grading of full programming assignments;
* Streamlit or frontend implementation in the first skeleton round.

## 7. Success Criteria

The first skeleton version is successful if:

* `knowledge_points.json` exists and can be parsed;
* each knowledge point has required fields;
* each prerequisite refers to an existing knowledge point ID;
* the project has clear rules in `CLAUDE.md`;
* the first Git Issue is small enough to finish in 30–60 minutes;
* no unnecessary framework or database has been introduced.

## 8. Demo Direction

The preferred demo scenario is:

A student asks why BFS can find the shortest path while DFS usually cannot.

The system should identify related concepts, check prerequisite knowledge, explain the difference, give a short exercise, update mastery, and recommend Uniform-Cost Search or A* as the next topic depending on the student's state.
