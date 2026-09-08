# FDU Preliminary Video Storyboard

## Title

**From Answering Questions to Guiding Learning: IntroAI Tutor for Introductory Artificial Intelligence Education**

## Target Length

6 minutes.

Suggested spoken length: around 5 minutes 20 seconds to 5 minutes 40 seconds, leaving time for slide transitions and natural pauses.

## Core Message

IntroAI Tutor is not a general chatbot. It is a lightweight tutoring prototype that turns one student question into a guided learning path: diagnosis, explanation, assessment, mastery update, and next-concept recommendation.

## 0:00-0:35 Opening

Good morning, respected judges and teachers.

Our project is called **IntroAI Tutor: From Answering Questions to Guiding Learning**.

It focuses on students who use AI tools to study search algorithms in an Introduction to Artificial Intelligence course.

This is not a large learning platform. It is a small prototype with one clear idea: AI should not only give answers; it should help students move forward.

## 0:35-1:15 Background

Today, when students get stuck, they often ask a chatbot a question such as:

> Why can Breadth-First Search find the shortest path, while Depth-First Search usually cannot?

A chatbot can usually give a correct explanation.

But one correct answer is not always enough for real learning.

The chatbot may not know what the student has already learned, where the confusion comes from, or what the student should learn next.

A good teacher gives not only an answer, but also guidance.

This is the gap our project addresses.

## 1:15-2:00 Research Problem

Our research problem comes from the Search Algorithms unit.

Students often mix up related ideas.

For example, they may confuse BFS with DFS, or think that “fewest steps” always means “lowest cost.”

They may also know the names of A* Search and Greedy Search, but still misunderstand when each method should be used.

These are not just small mistakes. They show that the student is still building a mental map of the course.

So our research question is:

**How can we design a lightweight AI tutor that answers a question, diagnoses the misconception behind it, and recommends the next suitable concept?**

## 2:00-2:40 Research Goal

Our goal is to build one complete adaptive learning loop.

The loop starts with a student question.

Then the system identifies the key concept, asks a diagnostic question, gives a targeted explanation, checks the student’s answer, updates mastery, and recommends the next concept.

In short, we want to turn one question into a guided learning path.

The purpose is not to replace teachers, but to make AI-assisted learning more structured and learner-aware.

## 2:40-3:25 Method

IntroAI Tutor has three simple parts.

First, **course knowledge**: a map of important concepts and prerequisites in the Search Algorithms unit.

Second, **learner state**: a record of what the student understands and where mistakes may appear.

Third, **tutoring workflow**: the process of diagnosis, explanation, assessment, and recommendation.

Together, these parts make the system more like a tutor, not just a chatbot.

## 3:25-4:40 Demo Scenario

Let me show one demo scenario.

The student asks:

> Why can BFS find the shortest path while DFS usually cannot?

IntroAI Tutor does not immediately give a long answer.

First, it checks the related concepts, such as BFS, DFS, and optimality.

Then it asks a diagnostic question:

> If one path has fewer steps but a higher total cost, and another path has more steps but a lower total cost, which path should we choose?

This question checks whether the student understands the difference between “fewest steps” and “lowest cost.”

Suppose the student says:

> BFS works because it expands nodes level by level.

This answer is partly correct, but incomplete.

The missing point is that BFS is optimal only when every step has the same cost.

So the tutor identifies the misconception, gives a short explanation, updates the student’s mastery, and recommends **Uniform-Cost Search** as the next concept.

In this way, one question becomes diagnosis, feedback, and a next learning step.

## 4:40-5:20 Main Findings

From this prototype, we have three main findings.

First, structured course knowledge keeps AI tutoring connected to the course.

Second, misconception diagnosis matters. Students need to know not only the correct answer, but also why their understanding is incomplete.

Third, recommendation becomes more meaningful when it follows prerequisite relationships.

Compared with a direct chatbot answer, IntroAI Tutor makes the learning process clearer and more transparent.

## 5:20-6:00 Significance and Conclusion

Finally, why does this project matter?

For students, it supports active learning, misconception correction, and a clearer learning path.

For teachers, it provides a way to organize AI-assisted learning around course goals.

For AI education, it shows that language models can become more educational when they are connected with course structure and learner state.

IntroAI Tutor is still an MVP, and future work includes expanding the knowledge base and testing it with real students.

To conclude, our goal is not to replace teachers or simply give faster answers.

We hope to move from **AI that answers questions** to **AI that guides learning**.

Thank you very much.
