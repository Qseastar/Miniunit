import copy
import json
from pathlib import Path

import pytest

from introai_tutor.diagnostic_tutoring import (
    DiagnosticTutorError,
    DiagnosticTutorService,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.questions import load_diagnostic_questions


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
QUESTIONS_FILE = PROJECT_ROOT / "data" / "diagnostic_questions.json"
TRACKS_FILE = PROJECT_ROOT / "data" / "diagnostic_tracks.json"


def _service(*, max_attempts_per_step=2, semantic_adjudicator=None):
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    questions_data = load_diagnostic_questions(QUESTIONS_FILE, knowledge_data)
    tracks_data = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    valid_concept_ids = {point["id"] for point in knowledge_data["knowledge_points"]}
    return DiagnosticTutorService(
        questions_data=questions_data,
        tracks_data=tracks_data,
        valid_concept_ids=valid_concept_ids,
        max_attempts_per_step=max_attempts_per_step,
        semantic_adjudicator=semantic_adjudicator,
    )


class _SemanticAdjudicator:
    def __init__(self, judgments):
        self.judgments = judgments
        self.calls = []

    def adjudicate(self, *, answer, criteria, question_context=None):
        self.calls.append(
            {
                "answer": answer,
                "criteria": copy.deepcopy(criteria),
                "question_context": question_context,
            }
        )
        return {"judgments": copy.deepcopy(self.judgments), "confidence": 0.9}


def test_default_track_is_a_valid_three_step_bfs_to_ucs_sequence():
    service = _service()
    started = service.start()

    assert started["question"]["id"] == "dq_bfs_expansion_001"
    assert started["question"]["step_number"] == 1
    assert started["question"]["total_steps"] == 3
    assert started["question"]["attempt_number"] == 1
    assert started["session"] == {
        "track_id": "bfs_equal_cost_ucs",
        "status": "in_progress",
        "step_index": 0,
        "attempt_in_step": 0,
        "history": [],
        "variant_round": 0,
        "selected_prompt_ids": [
            "dq_bfs_expansion_001",
            "dq_bfs_order_001",
            "dq_ucs_when_costs_differ_001",
        ],
    }


def test_formative_skip_advances_without_creating_an_observation():
    service = _service()
    started = service.start()
    original = copy.deepcopy(started["session"])

    skipped = service.skip_current(session=started["session"])

    assert started["session"] == original
    assert skipped["status"] == "in_progress"
    assert skipped["question"]["step_number"] == 2
    assert skipped["session"]["history"] == []
    assert skipped["session"]["skipped_steps"] == [0]


def test_student_question_does_not_leak_hidden_answer_or_rubric():
    question = _service().start()["question"]
    assert set(question) == {
        "id",
        "prompt_id",
        "prompt",
        "concept_ids",
        "step_number",
        "total_steps",
        "attempt_number",
        "max_attempts",
    }
    assert "expected_answer" not in question
    assert "assessment" not in question
    assert question["prompt_id"] == question["id"]


def test_variant_round_selects_canonical_then_human_verified_prompts_stably():
    service = _service()

    canonical = service.start(variant_round=0)
    variant = service.start(variant_round=1)
    repeated_variant = service.start(variant_round=1)
    wrapped = service.start(variant_round=2)

    assert canonical["question"]["id"] == "dq_bfs_expansion_001"
    assert canonical["question"]["prompt"] == (
        "BFS 通常如何从 frontier 中选择下一个节点扩展？请说明它的扩展顺序，并可说明哪种数据结构与此顺序相匹配。"
    )
    assert canonical["session"]["selected_prompt_ids"] == [
        "dq_bfs_expansion_001",
        "dq_bfs_order_001",
        "dq_ucs_when_costs_differ_001",
    ]
    assert variant["session"]["variant_round"] == 1
    assert variant["session"]["selected_prompt_ids"] == [
        "bfs_expansion_frontier_v2",
        "bfs_equal_cost_path_v2",
        "ucs_frontier_cost_choice_v2",
    ]
    assert "A、B、C" in variant["question"]["prompt"]
    assert set(variant["question"]) == {
        "id",
        "prompt_id",
        "prompt",
        "concept_ids",
        "step_number",
        "total_steps",
        "attempt_number",
        "max_attempts",
    }
    assert "variant_round" not in variant["question"]
    assert "selected_prompt_ids" not in variant["question"]
    assert variant["question"]["prompt_id"] == "bfs_expansion_frontier_v2"
    assert repeated_variant == variant
    assert wrapped["session"]["selected_prompt_ids"] == canonical["session"][
        "selected_prompt_ids"
    ]


@pytest.mark.parametrize("variant_round", [-1, True, 1.5, "1"])
def test_variant_round_must_be_a_non_negative_integer(variant_round):
    with pytest.raises(DiagnosticTutorError, match="variant_round"):
        _service().start(variant_round=variant_round)


def test_variant_prompt_is_stable_on_retry_and_next_step_was_selected_at_start():
    service = _service()
    started = service.start(variant_round=1)
    initial_prompt = started["question"]["prompt"]

    retry = service.submit(session=started["session"], answer="不知道。")
    advanced = service.submit(
        session=retry["session"], answer="BFS 按层逐层扩展，使用 FIFO 队列。"
    )

    assert retry["question"]["prompt"] == initial_prompt
    assert retry["question"]["attempt_number"] == 2
    assert advanced["question"]["id"] == "dq_bfs_order_001"
    assert "代价为 100" in advanced["question"]["prompt"]
    assert advanced["session"]["history"][0]["question_id"] == "dq_bfs_expansion_001"
    assert advanced["session"]["history"][1]["question_id"] == "dq_bfs_expansion_001"


def test_current_question_recovers_canonical_ucs_step_from_latest_session_only():
    service = _service()
    result = service.start()
    result = service.submit(
        session=result["session"], answer="BFS 按层逐层扩展，使用 FIFO 队列。"
    )
    result = service.submit(
        session=result["session"],
        answer="BFS 只保证边数少；只有每条边的花费都一样时，边数少才等于总成本低。",
    )

    question = service.current_question(session=result["session"])

    assert result["session"]["step_index"] == 2
    assert question["step_number"] == 3
    assert question["id"] == "dq_ucs_when_costs_differ_001"
    assert question["prompt_id"] == "dq_ucs_when_costs_differ_001"
    assert "路径甲只走2步" not in question["prompt"]
    assert "动作或边的代价不同时" in question["prompt"]

    completed = service.submit(
        session=result["session"],
        answer="UCS 在动作代价不同时，按累计路径代价 g(n) 最小选择节点。",
    )
    assert completed["evaluation"]["question_id"] == question["id"]
    with pytest.raises(DiagnosticTutorError, match="in-progress"):
        service.current_question(session=completed["session"])


def test_explicit_complete_bfs_cost_answer_advances_without_semantic_or_assistance():
    adjudicator = _SemanticAdjudicator([])
    service = _service(semantic_adjudicator=adjudicator)
    started = service.start()
    step_two = service.submit(
        session=started["session"], answer="BFS 按层逐层扩展，使用 FIFO 队列。"
    )
    result = service.submit(
        session=step_two["session"],
        answer=(
            "BFS 会先找到路径甲，因为它按层数（步数）逐层扩展，"
            "2 步的目标会早于 4 步的目标被发现。这说明 BFS 的“最优”是指"
            "最少边数、最少步数，而不是总代价最小。只有在无权图或所有边的"
            "代价相同且非负时，最少步数才等价于最小总代价，BFS 才能保证代价最优。"
        ),
    )

    assert result["status"] == "in_progress"
    assert result["question"]["step_number"] == 3
    assert result["evaluation"]["passed"] is True
    assert result["evaluation"]["mastery_score"] == 1.0
    assert result["evaluation"]["assistance_level"] == "none"
    assert result["evaluation"]["needs_clarification"] is False
    assert adjudicator.calls == []


def test_concise_conditional_bfs_answer_advances_without_assistance():
    adjudicator = _SemanticAdjudicator([])
    service = _service(semantic_adjudicator=adjudicator)
    started = service.start()
    step_two = service.submit(
        session=started["session"], answer="BFS 按层逐层扩展，使用 FIFO 队列。"
    )
    result = service.submit(
        session=step_two["session"],
        answer=(
            "BFS 会先找到路径甲，因为它优先找到步数更少的路径。"
            "只有所有边的代价相同时，步数最少才等价于路径总代价最小。"
        ),
    )

    assert result["status"] == "in_progress"
    assert result["question"]["step_number"] == 3
    assert result["evaluation"]["passed"] is True
    assert result["evaluation"]["mastery_score"] == 1.0
    assert result["evaluation"]["assistance_level"] == "none"
    assert result["evaluation"]["needs_clarification"] is False
    assert adjudicator.calls == []


def test_current_question_recovers_selected_ucs_variant_after_step_advance_and_retry():
    service = _service()
    result = service.start(variant_round=1)
    result = service.submit(
        session=result["session"], answer="BFS 按层逐层扩展，使用 FIFO 队列。"
    )
    result = service.submit(
        session=result["session"],
        answer="BFS 只保证边数少；只有每条边的花费都一样时，边数少才等于总成本低。",
    )

    ucs_question = service.current_question(session=result["session"])
    assert ucs_question["step_number"] == 3
    assert ucs_question["id"] == "dq_ucs_when_costs_differ_001"
    assert ucs_question["prompt_id"] == "ucs_frontier_cost_choice_v2"
    assert "g(n)=3" in ucs_question["prompt"]
    assert "路径甲只走2步" not in ucs_question["prompt"]

    retry = service.submit(session=result["session"], answer="不知道。")
    retry_question = service.current_question(session=retry["session"])
    assert retry_question["prompt"] == ucs_question["prompt"]
    assert retry_question["prompt_id"] == ucs_question["prompt_id"]
    assert retry_question["attempt_number"] == 2


def test_semantic_step_two_advisory_keeps_the_submitted_question_current():
    adjudicator = _SemanticAdjudicator(
        [
            {"criterion_id": "fewest_steps", "status": "entailed"},
            {"criterion_id": "equal_step_cost_condition", "status": "entailed"},
        ]
    )
    service = _service(semantic_adjudicator=adjudicator)
    result = service.start()
    result = service.submit(
        session=result["session"], answer="BFS 按层逐层扩展，使用 FIFO 队列。"
    )
    submitted_question = result["question"]
    result = service.submit(
        session=result["session"],
        answer="BFS 更可能选路径甲；只有统一成本时它才是总代价最优。",
    )

    current = service.current_question(session=result["session"])
    assert len(adjudicator.calls) == 1
    assert result["evaluation"]["semantic_used"] is True
    assert result["evaluation"]["needs_clarification"] is True
    assert result["evaluation"]["passed"] is False
    assert submitted_question["id"] == "dq_bfs_order_001"
    assert current["id"] == "dq_bfs_order_001"
    assert current["step_number"] == 2
    assert current["attempt_number"] == 2


def test_prompt_variants_share_the_canonical_question_teaching_support():
    service = _service()
    canonical = service.get_teaching_support(question_id="dq_bfs_expansion_001")
    variant_run = service.start(variant_round=1)
    retry = service.submit(session=variant_run["session"], answer="不知道。")

    assert retry["evaluation"]["question_id"] == "dq_bfs_expansion_001"
    assert service.get_teaching_support(
        question_id=retry["evaluation"]["question_id"]
    ) == canonical


def test_variant_prompt_uses_canonical_rubric_with_optional_semantic_adjudication():
    adjudicator = _SemanticAdjudicator(
        [{"criterion_id": "cumulative_path_cost", "status": "entailed"}]
    )
    service = _service(semantic_adjudicator=adjudicator)
    started = service.start(variant_round=1)
    first = service.submit(
        session=started["session"],
        answer="BFS 先处理离起点更近的节点。",
    )
    second = service.submit(
        session=first["session"],
        answer=(
            "BFS 保证动作次数最少；只有每一步代价一样时，"
            "步数最少才等价于路径总代价最低。"
        ),
    )
    advisory = service.submit(
        session=second["session"],
        answer="UCS 面对不同开销时，要比较从起点走到节点已经花掉的全部成本。",
    )
    final = service.submit(
        session=advisory["session"],
        answer="动作代价不同时使用 UCS，并按累计路径代价 g(n) 最小选择节点。",
    )

    assert final["status"] == "completed"
    assert advisory["evaluation"]["semantic_used"] is True
    assert advisory["evaluation"]["needs_clarification"] is True
    assert advisory["evaluation"]["passed"] is False
    assert final["evaluation"]["passed"] is True
    assert final["session"]["history"][-1]["score"] == 1.0
    assert final["session"]["history"][-1]["coverage_score"] == 1.0
    assert "semantic_judgments" not in final["session"]["history"][-1]
    assert len(adjudicator.calls) == 1
    assert "g(n)=3" in adjudicator.calls[0]["question_context"]


def test_teaching_support_never_enters_history_or_summary():
    service = _service(max_attempts_per_step=1)
    result = service.start()
    for answer in ("不知道。", "不知道。", "不知道。"):
        result = service.submit(session=result["session"], answer=answer)

    assert result["status"] == "completed"
    serialized = repr({"history": result["session"]["history"], "summary": result["summary"]})
    assert "model_answer" not in serialized
    assert "explanation" not in serialized
    assert "scaffold" not in serialized


def test_legacy_structured_question_without_teaching_support_remains_compatible():
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    questions_data = load_diagnostic_questions(QUESTIONS_FILE, knowledge_data)
    legacy_questions = copy.deepcopy(questions_data)
    target = next(
        question
        for question in legacy_questions["diagnostic_questions"]
        if question["id"] == "dq_bfs_expansion_001"
    )
    target.pop("teaching_support")
    tracks_data = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    service = DiagnosticTutorService(
        questions_data=legacy_questions,
        tracks_data=tracks_data,
        valid_concept_ids={point["id"] for point in knowledge_data["knowledge_points"]},
    )

    retry = service.submit(session=service.start()["session"], answer="不知道。")

    assert retry["question"]["attempt_number"] == 2
    assert service.get_teaching_support(question_id="dq_bfs_expansion_001") is None


def test_variant_session_tampering_is_rejected_without_mutating_caller_input():
    service = _service()
    started = service.start(variant_round=0)
    tampered_round = copy.deepcopy(started["session"])
    tampered_round["variant_round"] = 1
    original_round = copy.deepcopy(tampered_round)
    tampered_selection = copy.deepcopy(started["session"])
    tampered_selection["selected_prompt_ids"][0] = "bfs_expansion_frontier_v2"
    original_selection = copy.deepcopy(tampered_selection)
    malformed_selection = copy.deepcopy(started["session"])
    malformed_selection["selected_prompt_ids"] = "not-a-list"
    original_malformed = copy.deepcopy(malformed_selection)

    with pytest.raises(DiagnosticTutorError, match="selected_prompt_ids"):
        service.submit(session=tampered_round, answer="逐层")
    with pytest.raises(DiagnosticTutorError, match="selected_prompt_ids"):
        service.submit(session=tampered_selection, answer="逐层")
    with pytest.raises(DiagnosticTutorError, match="selected_prompt_ids"):
        service.submit(session=malformed_selection, answer="逐层")

    assert tampered_round == original_round
    assert tampered_selection == original_selection
    assert malformed_selection == original_malformed


def test_legacy_track_without_prompt_variants_keeps_its_original_session_schema():
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    questions_data = load_diagnostic_questions(QUESTIONS_FILE, knowledge_data)
    tracks_data = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    for step in tracks_data["tracks"][0]["steps"]:
        step.pop("prompt_variants")
    service = DiagnosticTutorService(
        questions_data=questions_data,
        tracks_data=tracks_data,
        valid_concept_ids={point["id"] for point in knowledge_data["knowledge_points"]},
    )

    started = service.start(variant_round=9)

    assert set(started["session"]) == {
        "track_id",
        "status",
        "step_index",
        "attempt_in_step",
        "history",
    }
    assert started["question"]["prompt"].startswith("BFS 通常如何")


def test_pass_advances_to_second_step_without_mutating_input_session():
    service = _service()
    started = service.start()
    original = copy.deepcopy(started["session"])

    result = service.submit(
        session=started["session"], answer="BFS 按层逐层扩展，使用 FIFO 队列。"
    )

    assert started["session"] == original
    assert result["status"] == "in_progress"
    assert result["question"]["id"] == "dq_bfs_order_001"
    assert result["session"]["step_index"] == 1
    assert result["session"]["attempt_in_step"] == 0
    assert result["evaluation"]["passed"] is True


def test_first_failed_attempt_retries_same_question_with_safe_feedback():
    service = _service()
    result = service.submit(session=service.start()["session"], answer="BFS 使用栈并沿一条路径一直深入。")

    assert result["status"] == "in_progress"
    assert result["question"]["id"] == "dq_bfs_expansion_001"
    assert result["question"]["attempt_number"] == 2
    assert result["session"]["attempt_in_step"] == 1
    assert result["evaluation"]["misconception_ids"] == ["bfs_is_depth_first"]
    assert result["evaluation"]["feedback"] == [
        "还需要说明：BFS 的逐层扩展顺序。",
        "BFS 不是沿单一路径持续深入；请关注它按层扩展。",
    ]
    assert "逐层" not in result["question"]["prompt"]
    assert result["session"]["history"][-1]["assisted"] is False


def test_second_failure_marks_step_unresolved_and_advances():
    service = _service()
    first = service.submit(session=service.start()["session"], answer="不知道。")
    second = service.submit(session=first["session"], answer="还是不知道。")

    assert second["question"]["id"] == "dq_bfs_order_001"
    assert second["session"]["step_index"] == 1
    assert second["session"]["attempt_in_step"] == 0
    assert len(second["session"]["history"]) == 2


def test_second_attempt_can_pass_and_then_advance():
    service = _service()
    first = service.submit(session=service.start()["session"], answer="不知道。")
    second = service.submit(session=first["session"], answer="BFS 按层逐层扩展。")

    assert second["evaluation"]["passed"] is True
    assert second["evaluation"]["assisted"] is False
    assert second["session"]["history"][-1]["assisted"] is False
    assert second["question"]["id"] == "dq_bfs_order_001"


@pytest.mark.parametrize("field_value", ["true", 1, None])
def test_invalid_reveal_marker_type_is_rejected_without_mutating_input(field_value):
    service = _service()
    session = service.start()["session"]
    session["full_answer_revealed"] = field_value
    original = copy.deepcopy(session)

    with pytest.raises(DiagnosticTutorError, match="assisted|full_answer_revealed|assistance"):
        service.submit(session=session, answer="BFS 按层扩展。")
    assert session == original


def test_inconsistent_reveal_marker_and_assisted_history_are_rejected():
    service = _service()
    first = service.submit(session=service.start()["session"], answer="不知道。")
    inconsistent_reveal = copy.deepcopy(first["session"])
    inconsistent_reveal["full_answer_revealed"] = True
    inconsistent_reveal["history"][-1]["assisted"] = True
    original_reveal = copy.deepcopy(inconsistent_reveal)

    with pytest.raises(DiagnosticTutorError, match="assisted|full_answer_revealed|assistance"):
        service.submit(session=inconsistent_reveal, answer="BFS 按层扩展。")
    assert inconsistent_reveal == original_reveal


@pytest.mark.parametrize(
    "pending",
    [
        "clarification",
        {"level": "clarification"},
        {"level": "clarification", "source": "model_answer"},
        {"level": "none", "source": None},
    ],
)
def test_invalid_pending_assistance_is_rejected_without_mutating_session(pending):
    service = _service()
    first = service.submit(session=service.start()["session"], answer="不知道。")
    session = copy.deepcopy(first["session"])
    session["pending_assistance"] = pending
    original = copy.deepcopy(session)

    with pytest.raises(DiagnosticTutorError, match="pending_assistance|assistance"):
        service.submit(session=session, answer="BFS 按层逐层扩展。")
    assert session == original


def test_legacy_reveal_marker_still_records_reveal_provenance():
    service = _service()
    first = service.submit(session=service.start()["session"], answer="不知道。")
    session = copy.deepcopy(first["session"])
    session["full_answer_revealed"] = True

    retry = service.submit(session=session, answer="BFS 按层逐层扩展。")

    assert retry["evaluation"]["assisted"] is True
    assert retry["evaluation"]["assistance_level"] == "reveal"
    assert retry["session"]["history"][-1]["assistance_source"] == "model_answer"


def test_complete_three_step_demo_records_misconception_and_summary():
    service = _service()
    result = service.start()
    result = service.submit(
        session=result["session"], answer="BFS 按层逐层扩展，使用 FIFO 队列。"
    )
    result = service.submit(
        session=result["session"], answer="BFS 总能找到总代价最低路径。"
    )
    assert result["question"]["id"] == "dq_bfs_order_001"
    assert result["evaluation"]["misconception_ids"] == ["bfs_always_cost_optimal"]
    result = service.submit(
        session=result["session"],
        answer="BFS 并不总能保证总代价最低，只有每步代价相同时才成立。",
    )
    result = service.submit(
        session=result["session"],
        answer="UCS 不是按步数，而是按累计路径代价 g(n) 用优先队列扩展。",
    )

    assert result["status"] == "completed"
    assert result["question"] is None
    summary = result["summary"]
    assert summary["passed_steps"] == 3
    assert summary["unresolved_steps"] == 0
    assert summary["misconception_ids"] == ["bfs_always_cost_optimal"]
    assert summary["concept_observations"]["breadth_first_search"] == [1.0, 0.0, 1.0]
    assert summary["concept_observations"]["completeness_optimality_complexity"] == [0.0, 1.0]
    assert summary["concept_coverage_observations"]["breadth_first_search"] == [
        1.0,
        0.0,
        1.0,
    ]
    assert summary["concept_observations"]["uniform_cost_search"] == [1.0]
    assert summary["step_results"][1] == {
        "question_id": "dq_bfs_order_001",
        "status": "passed",
        "best_score": 1.0,
        "best_coverage_score": 1.0,
        "attempts": 2,
        "attempt_assistance": [False, False],
        "attempt_assistance_levels": ["none", "none"],
        "attempt_assistance_sources": [None, None],
        "final_attempt_assisted": False,
        "final_attempt_assistance_level": "none",
        "final_attempt_assistance_source": None,
    }


def test_completion_with_unresolved_steps_and_duplicate_misconceptions_is_stable():
    service = _service()
    result = service.start()
    for answer in (
        "使用栈。",
        "使用栈。",
        "BFS 总能找到总代价最低路径。",
        "BFS 总能找到总代价最低路径。",
        "按层数选择。",
        "按层数选择。",
    ):
        result = service.submit(session=result["session"], answer=answer)

    summary = result["summary"]
    assert result["status"] == "completed"
    assert summary["passed_steps"] == 0
    assert summary["unresolved_steps"] == 3
    assert summary["misconception_ids"] == [
        "bfs_is_depth_first",
        "bfs_always_cost_optimal",
        "ucs_uses_depth_or_step_count",
    ]
    assert [item["attempts"] for item in summary["step_results"]] == [2, 2, 2]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda session: session.update({"step_index": 1}),
        lambda session: session.update({"attempt_in_step": 1}),
        lambda session: session.update({"status": "completed"}),
        lambda session: session.update({"unexpected": True}),
        lambda session: session["history"].append(
            {
                "question_id": "dq_ucs_when_costs_differ_001",
                "concept_ids": ["uniform_cost_search"],
                "step_index": 2,
                "attempt_number": 1,
                "score": 1.0,
                "passed": True,
                "misconception_ids": [],
            }
        ),
    ],
)
def test_invalid_or_jumped_session_is_rejected(mutate):
    service = _service()
    session = service.start()["session"]
    mutate(session)
    with pytest.raises(DiagnosticTutorError):
        service.submit(session=session, answer="BFS 按层扩展。")


def test_non_contiguous_attempt_history_is_rejected():
    service = _service()
    first = service.submit(session=service.start()["session"], answer="不知道。")
    forged = copy.deepcopy(first["session"])
    forged["history"][0]["attempt_number"] = 2

    with pytest.raises(DiagnosticTutorError, match="numbering"):
        service.submit(session=forged, answer="BFS 按层扩展。")


def test_completed_session_cannot_be_submitted_again():
    service = _service(max_attempts_per_step=1)
    result = service.start()
    for answer in ("逐层", "步数最少，每步代价相同", "边代价不同时，累计路径代价 g(n)"):
        result = service.submit(session=result["session"], answer=answer)

    with pytest.raises(DiagnosticTutorError, match="in-progress"):
        service.submit(session=result["session"], answer="another answer")


@pytest.mark.parametrize("answer", ["", "   ", None])
def test_empty_answer_is_rejected(answer):
    with pytest.raises(DiagnosticTutorError, match="non-empty"):
        _service().submit(session=_service().start()["session"], answer=answer)


@pytest.mark.parametrize("max_attempts", [0, -1, True, 1.5])
def test_invalid_max_attempts_are_rejected(max_attempts):
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    questions_data = load_diagnostic_questions(QUESTIONS_FILE, knowledge_data)
    tracks_data = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    with pytest.raises(DiagnosticTutorError, match="positive integer"):
        DiagnosticTutorService(
            questions_data=questions_data,
            tracks_data=tracks_data,
            valid_concept_ids={point["id"] for point in knowledge_data["knowledge_points"]},
            max_attempts_per_step=max_attempts,
        )


@pytest.mark.parametrize(
    "mutation, error_match",
    [
        (lambda tracks: tracks["tracks"][0]["steps"][0].update({"question_id": "missing"}), "unknown question"),
        (lambda tracks: tracks["tracks"][0]["steps"][0].update({"concept_ids": ["missing"]}), "unknown or invalid concept"),
        (lambda tracks: tracks["tracks"].append(copy.deepcopy(tracks["tracks"][0])), "Duplicate diagnostic track id"),
    ],
)
def test_invalid_track_references_are_rejected(mutation, error_match):
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    questions_data = load_diagnostic_questions(QUESTIONS_FILE, knowledge_data)
    tracks_data = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    mutation(tracks_data)
    with pytest.raises(DiagnosticTutorError, match=error_match):
        DiagnosticTutorService(
            questions_data=questions_data,
            tracks_data=tracks_data,
            valid_concept_ids={point["id"] for point in knowledge_data["knowledge_points"]},
        )


@pytest.mark.parametrize(
    "mutation,error_match",
    [
        (
            lambda tracks: tracks["tracks"][0]["steps"][0].update(
                {"prompt_variants": []}
            ),
            "non-empty list",
        ),
        (
            lambda tracks: tracks["tracks"][0]["steps"][0]["prompt_variants"][0].update(
                {"id": "   "}
            ),
            "invalid id",
        ),
        (
            lambda tracks: tracks["tracks"][0]["steps"][0]["prompt_variants"][0].update(
                {"prompt": "   "}
            ),
            "invalid prompt",
        ),
        (
            lambda tracks: tracks["tracks"][0]["steps"][0]["prompt_variants"][0].update(
                {"review_status": "codex_draft"}
            ),
            "human_verified",
        ),
        (
            lambda tracks: tracks["tracks"][0]["steps"][0]["prompt_variants"][0].update(
                {"unexpected": True}
            ),
            "invalid schema",
        ),
        (
            lambda tracks: tracks["tracks"][0]["steps"][1]["prompt_variants"][0].update(
                {"id": "bfs_expansion_frontier_v2"}
            ),
            "Duplicate prompt id",
        ),
        (
            lambda tracks: tracks["tracks"][0]["steps"][0]["prompt_variants"][0].update(
                {"id": "dq_bfs_order_001"}
            ),
            "Duplicate prompt id",
        ),
    ],
)
def test_invalid_prompt_variants_are_rejected_without_mutating_input(mutation, error_match):
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    questions_data = load_diagnostic_questions(QUESTIONS_FILE, knowledge_data)
    tracks_data = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    mutation(tracks_data)
    before = copy.deepcopy(tracks_data)

    with pytest.raises(DiagnosticTutorError, match=error_match):
        DiagnosticTutorService(
            questions_data=questions_data,
            tracks_data=tracks_data,
            valid_concept_ids={point["id"] for point in knowledge_data["knowledge_points"]},
        )

    assert tracks_data == before


def test_unknown_track_and_data_inputs_are_not_mutated():
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    questions_data = load_diagnostic_questions(QUESTIONS_FILE, knowledge_data)
    tracks_data = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    questions_before = copy.deepcopy(questions_data)
    tracks_before = copy.deepcopy(tracks_data)
    service = DiagnosticTutorService(
        questions_data=questions_data,
        tracks_data=tracks_data,
        valid_concept_ids={point["id"] for point in knowledge_data["knowledge_points"]},
    )

    with pytest.raises(DiagnosticTutorError, match="Unknown diagnostic track"):
        service.start(track_id="missing")
    assert questions_data == questions_before
    assert tracks_data == tracks_before
