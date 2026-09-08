from introai_tutor.assessment import assess_answer, add_misconception


def print_line():
    print("=" * 72)


def main():
    learner_state = {
        "student_id": "demo_student",
        "mastery": {
            "breadth_first_search": 0.55,
            "uniform_cost_search": 0.20,
        },
        "learning_evidence": [],
        "misconceptions": [],
    }

    concept_id = "breadth_first_search"

    student_question = "Why can BFS find the shortest path while DFS usually cannot?"
    diagnostic_question = (
        "Does BFS always find the lowest-cost path, or only when all step costs are equal?"
    )
    student_answer = "BFS is optimal because it expands nodes level by level."

    result = assess_answer(
        learner_state,
        concept_id,
        student_answer,
        expected_keywords=["level", "equal step costs", "lowest path cost"],
        activity_id="demo_bfs_diagnostic_01",
        learning_rate=0.25,
    )

    add_misconception(
        learner_state,
        concept_id,
        "The student mentions level-by-level expansion, but misses the condition of equal step costs.",
    )

    print_line()
    print("IntroAI Tutor Demo: From Question to Recommendation")
    print_line()

    print("\n[1] Student Question")
    print(student_question)

    print("\n[2] Related Course Concepts")
    print("- Breadth-First Search")
    print("- Depth-First Search")
    print("- Completeness and Optimality")
    print("- Path Cost")

    print("\n[3] Diagnostic Question")
    print(diagnostic_question)

    print("\n[4] Student Answer")
    print(student_answer)

    print("\n[5] Assessment Result")
    print(f"Result: {result['evaluation']['result']}")
    print(f"Matched keywords: {result['evaluation']['matched']}")
    print(f"Missing keywords: {result['evaluation']['missing']}")
    print(
        f"Mastery update for BFS: "
        f"{result['old_mastery']:.2f} -> {result['new_mastery']:.2f}"
    )

    print("\n[6] Detected Misconception")
    print(learner_state["misconceptions"][-1]["description"])

    print("\n[7] Next Recommendation")
    print(
        "Recommended next concept: Uniform-Cost Search, "
        "because it directly explains the difference between fewest steps and lowest path cost."
    )

    print("\n[8] Learning Evidence Recorded")
    print(learner_state["learning_evidence"][-1])

    print_line()


if __name__ == "__main__":
    main()
