
# Demo Script

## Demo Goal

This demo shows that IntroAI Tutor is not a general chatbot, but a course-grounded adaptive learning agent.

The system demonstrates one complete tutoring loop for the Search Algorithms unit in an introductory artificial intelligence course.

## Competition Context

The preliminary-round video is an English academic presentation.

The presentation should explain:

- background;
- research problem;
- method;
- result;
- conclusion and significance.

## Project Title

IntroAI Tutor: A Course-Grounded Adaptive Learning Agent for Introductory Artificial Intelligence Education

## Core Problem

General-purpose large language models can answer isolated questions, but they usually do not maintain a stable model of:

- course knowledge structure;
- prerequisite relationships;
- learner mastery;
- learner misconceptions;
- next-step learning recommendations.

Therefore, they may not provide coherent and traceable learning support across a course unit.

## Research Question

How can we build a lightweight course-grounded learning agent that supports an adaptive tutoring loop for students learning search algorithms?

## Demo Scenario

Student question:

> Why can BFS find the shortest path while DFS usually cannot?

This question is selected because students often confuse BFS, DFS, shortest path, path cost, completeness, and optimality.

## Expected Flow

1. Read student question.
2. Read learner state.
3. Identify related knowledge points.
4. Detect likely misconception.
5. Retrieve course-grounded knowledge.
6. Give personalized explanation.
7. Provide a short exercise.
8. Assess the student's answer.
9. Update learner mastery.
10. Recommend the next concept.

## Expected Output

The system should show:

- related knowledge points;
- likely misconception;
- personalized explanation;
- diagnostic exercise;
- assessment result;
- updated mastery;
- next concept recommendation.

## Six-Minute Presentation Structure

### 0:00-0:40 Background

Large language models are increasingly used for learning, but direct answers are often isolated from course structure and learner history.

### 0:40-1:20 Problem

Students learning search algorithms often confuse BFS, DFS, path cost, optimality, and heuristics. A useful tutor should know what the student has learned and what should come next.

### 1:20-2:00 Goal

Our goal is to build a minimal adaptive tutoring prototype for the Search Algorithms unit.

### 2:00-3:10 Method

The system uses structured course knowledge, learner state, and a tutoring workflow.

### 3:10-4:40 Demo

The student asks why BFS can find the shortest path while DFS usually cannot. The system diagnoses the misconception, explains the concept, gives an exercise, evaluates the answer, updates mastery, and recommends Uniform-Cost Search.

### 4:40-5:30 Result

The prototype demonstrates a complete adaptive learning loop on a small but meaningful course unit.

### 5:30-6:00 Conclusion

IntroAI Tutor shows a feasible path toward course-grounded adaptive learning agents.
