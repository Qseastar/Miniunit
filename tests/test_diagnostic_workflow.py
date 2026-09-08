import copy
import json
from pathlib import Path

import pytest

from introai_tutor.diagnostic_state_integration import DiagnosticStateIntegrationService
from introai_tutor.diagnostic_tutoring import DiagnosticTutorService
from introai_tutor.diagnostic_workflow import (
    DiagnosticWorkflowError,
    DiagnosticWorkflowService,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.learner import load_learner_state
from introai_tutor.recommend import recommend_next_concept
from introai_tutor.questions import load_diagnostic_questions


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
QUESTIONS_FILE = PROJECT_ROOT / "data" / "diagnostic_questions.json"
TRACKS_FILE = PROJECT_ROOT / "data" / "diagnostic_tracks.json"
LEARNER_STATE_FILE = PROJECT_ROOT / "data" / "demo_student_state.json"


SESSION = {
    "track_id": "bfs_equal_cost_ucs",
    "status": "in_progress",
    "step_index": 0,
    "attempt_in_step": 0,
    "history": [],
}
SUMMARY = {
    "track_id": "bfs_equal_cost_ucs",
    "total_steps": 1,
    "passed_steps": 1,
    "unresolved_steps": 0,
    "concept_observations": {"breadth_first_search": [1.0]},
    "misconception_ids": [],
    "step_results": [
        {
            "question_id": "dq_bfs_expansion_001",
            "status": "passed",
            "best_score": 1.0,
            "attempts": 1,
        }
    ],
}


class FakeDiagnostic:
    def __init__(self, results=None, error=None):
        self.starts = []
        self.submits = []
        self.results = list(results or [])
        self.error = error

    def start(self, *, track_id, variant_round=0):
        self.starts.append((track_id, variant_round))
        return {"status": "in_progress", "session": copy.deepcopy(SESSION)}

    def submit(self, *, session, answer):
        self.submits.append((session, answer))
        session["mutated_by_fake"] = True
        if self.error is not None:
            raise self.error
        return self.results.pop(0)


class FakeIntegration:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result if result is not None else {"recommendation": {"concept_id": "bfs"}}
        self.error = error

    def apply(self, *, learner_state, diagnostic_summary):
        self.calls.append((copy.deepcopy(learner_state), copy.deepcopy(diagnostic_summary)))
        learner_state["mutated_by_fake"] = True
        diagnostic_summary["mutated_by_fake"] = True
        if self.error is not None:
            raise self.error
        return self.result


def _workflow(diagnostic, integration):
    return DiagnosticWorkflowService(
        diagnostic_service=diagnostic,
        state_integration_service=integration,
    )


def test_start_calls_diagnostic_once_and_defers_state_update():
    diagnostic = FakeDiagnostic()
    result = _workflow(diagnostic, FakeIntegration()).start()

    assert diagnostic.starts == [("bfs_equal_cost_ucs", 0)]
    assert result["state_update"] is None
    assert result["diagnostic"]["status"] == "in_progress"


def test_start_forwards_variant_round_once():
    diagnostic = FakeDiagnostic()

    _workflow(diagnostic, FakeIntegration()).start(variant_round=3)

    assert diagnostic.starts == [("bfs_equal_cost_ucs", 3)]


def test_start_rejects_invalid_track_id():
    diagnostic = FakeDiagnostic()
    service = _workflow(diagnostic, FakeIntegration())
    for track_id in ("", "   ", None, 1):
        with pytest.raises(DiagnosticWorkflowError, match="track_id"):
            service.start(track_id=track_id)
    assert diagnostic.starts == []


@pytest.mark.parametrize("variant_round", [-1, True, 1.5, "1"])
def test_start_rejects_invalid_variant_round(variant_round):
    diagnostic = FakeDiagnostic()

    with pytest.raises(DiagnosticWorkflowError, match="variant_round"):
        _workflow(diagnostic, FakeIntegration()).start(variant_round=variant_round)
    assert diagnostic.starts == []


def test_start_result_isolated_from_downstream_result():
    diagnostic = FakeDiagnostic()
    service = _workflow(diagnostic, FakeIntegration())
    result = service.start()
    result["diagnostic"]["session"]["history"].append("caller mutation")

    fresh = service.start()
    assert fresh["diagnostic"]["session"]["history"] == []


def test_non_completed_submit_does_not_call_integration():
    diagnostic_result = {
        "status": "in_progress",
        "session": copy.deepcopy(SESSION),
        "question": {"id": "dq_bfs_expansion_001"},
        "evaluation": None,
        "summary": None,
    }
    diagnostic = FakeDiagnostic(results=[diagnostic_result])
    integration = FakeIntegration()
    learner_state = {"mastery": {"breadth_first_search": 0.4}}
    original_session = copy.deepcopy(SESSION)
    original_state = copy.deepcopy(learner_state)

    result = _workflow(diagnostic, integration).submit(
        session=SESSION, answer="answer", learner_state=learner_state
    )

    assert result["state_update"] is None
    assert integration.calls == []
    assert SESSION == original_session
    assert learner_state == original_state
    assert diagnostic.submits[0][0] != SESSION


def test_failed_retry_and_next_question_remain_diagnostic_only():
    first = {
        "status": "in_progress",
        "session": copy.deepcopy(SESSION),
        "question": {"id": "dq_bfs_expansion_001", "attempt_number": 2},
        "evaluation": {"passed": False},
        "summary": None,
    }
    second = {
        "status": "in_progress",
        "session": {**copy.deepcopy(SESSION), "step_index": 1},
        "question": {"id": "dq_bfs_order_001"},
        "evaluation": {"passed": True},
        "summary": None,
    }
    diagnostic = FakeDiagnostic(results=[first, second])
    integration = FakeIntegration()
    service = _workflow(diagnostic, integration)

    first_result = service.submit(session=SESSION, answer="wrong", learner_state={})
    second_result = service.submit(
        session=first_result["diagnostic"]["session"],
        answer="correct",
        learner_state={},
    )

    assert first_result["state_update"] is None
    assert second_result["state_update"] is None
    assert len(diagnostic.submits) == 2
    assert integration.calls == []


def test_legacy_reveal_without_a_model_answer_does_not_mark_assisted_retry():
    diagnostic_result = {
        "status": "in_progress",
        "session": copy.deepcopy(SESSION),
        "question": {"id": "dq_bfs_expansion_001", "attempt_number": 2},
        "evaluation": {
            "question_id": "dq_bfs_expansion_001",
            "concept_ids": ["breadth_first_search"],
            "score": 0.0,
            "passed": False,
            "attempts_used": 1,
            "max_attempts": 2,
            "feedback": ["安全缺失提示"],
        },
        "summary": None,
    }

    result = _workflow(
        FakeDiagnostic(results=[diagnostic_result]), FakeIntegration()
    ).submit(session=SESSION, answer="wrong", learner_state={"mastery": {}})

    assert result["teaching_feedback"]["mode"] == "reveal"
    assert result["teaching_feedback"]["model_answer"] is None
    assert "full_answer_revealed" not in result["diagnostic"]["session"]


def test_completed_open_diagnostic_is_formative_only_and_never_calls_integration():
    completed = {
        "status": "completed",
        "session": {**copy.deepcopy(SESSION), "status": "completed", "step_index": 1},
        "question": None,
        "evaluation": {"passed": True},
        "summary": copy.deepcopy(SUMMARY),
    }
    diagnostic = FakeDiagnostic(results=[completed])
    integration = FakeIntegration()
    learner_state = {"mastery": {"breadth_first_search": 0.4}}

    result = _workflow(diagnostic, integration).submit(
        session=SESSION, answer="correct", learner_state=learner_state
    )

    assert integration.calls == []
    assert result["purpose"] == "formative"
    assert result["evidence_eligible"] is False
    assert result["state_update"] is None
    assert result["diagnostic"] == completed


def test_completed_open_diagnostic_never_uses_summary_for_integration():
    completed = {
        "status": "completed",
        "summary": copy.deepcopy(SUMMARY),
        "extra": {"do_not_use": True},
    }
    integration = FakeIntegration()
    _workflow(FakeDiagnostic(results=[completed]), integration).submit(
        session=SESSION, answer="correct", learner_state={}
    )

    assert integration.calls == []


def test_completed_open_diagnostic_without_summary_remains_formative_only():
    diagnostic = FakeDiagnostic(results=[{"status": "completed", "summary": None}])
    integration = FakeIntegration()

    result = _workflow(diagnostic, integration).submit(
        session=SESSION, answer="correct", learner_state={}
    )
    assert result["state_update"] is None
    assert result["purpose"] == "formative"
    assert integration.calls == []


def test_non_completed_result_with_summary_does_not_integrate():
    result = {"status": "in_progress", "summary": copy.deepcopy(SUMMARY)}
    integration = FakeIntegration()

    output = _workflow(FakeDiagnostic(results=[result]), integration).submit(
        session=SESSION, answer="answer", learner_state={}
    )

    assert output["state_update"] is None
    assert integration.calls == []


def test_diagnostic_exception_propagates_without_integration():
    diagnostic_error = RuntimeError("diagnostic failed")
    integration = FakeIntegration()

    with pytest.raises(RuntimeError, match="diagnostic failed"):
        _workflow(FakeDiagnostic(error=diagnostic_error), integration).submit(
            session=SESSION, answer="answer", learner_state={}
        )
    assert integration.calls == []


def test_legacy_open_workflow_does_not_call_integration_even_when_it_would_fail():
    diagnostic = FakeDiagnostic(results=[{"status": "completed", "summary": SUMMARY}])
    integration = FakeIntegration(error=RuntimeError("integration failed"))
    learner_state = {"mastery": {"breadth_first_search": 0.4}}
    original = copy.deepcopy(learner_state)

    result = _workflow(diagnostic, integration).submit(
        session=SESSION, answer="answer", learner_state=learner_state
    )
    assert result["state_update"] is None
    assert integration.calls == []
    assert learner_state == original


@pytest.mark.parametrize(
    "bad_session,bad_answer,bad_state,match",
    [
        (None, "answer", {}, "session"),
        (SESSION, "", {}, "answer"),
        (SESSION, "   ", {}, "answer"),
        (SESSION, None, {}, "answer"),
        (SESSION, "answer", None, "learner_state"),
        (SESSION, "answer", [], "learner_state"),
    ],
)
def test_submit_rejects_invalid_public_inputs(bad_session, bad_answer, bad_state, match):
    with pytest.raises(DiagnosticWorkflowError, match=match):
        _workflow(FakeDiagnostic(), FakeIntegration()).submit(
            session=bad_session, answer=bad_answer, learner_state=bad_state
        )


@pytest.mark.parametrize(
    "diagnostic, integration, match",
    [
        (object(), FakeIntegration(), "diagnostic_service"),
        (type("BadDiagnostic", (), {"start": lambda self, **_: {}})(), FakeIntegration(), "diagnostic_service"),
        (FakeDiagnostic(), object(), "state_integration_service"),
    ],
)
def test_invalid_service_interfaces_are_rejected(diagnostic, integration, match):
    with pytest.raises(DiagnosticWorkflowError, match=match):
        DiagnosticWorkflowService(
            diagnostic_service=diagnostic,
            state_integration_service=integration,
        )


def test_downstream_results_are_isolated_from_caller_mutations():
    diagnostic_result = {"status": "in_progress", "nested": {"items": []}}
    diagnostic = FakeDiagnostic(results=[diagnostic_result])
    result = _workflow(diagnostic, FakeIntegration()).submit(
        session=SESSION, answer="answer", learner_state={}
    )
    result["diagnostic"]["nested"]["items"].append("caller")
    assert diagnostic_result["nested"]["items"] == []


def test_legacy_open_workflow_never_returns_an_integration_result():
    output = _workflow(
        FakeDiagnostic(results=[{"status": "completed", "summary": SUMMARY}]),
        FakeIntegration(),
    ).submit(session=SESSION, answer="answer", learner_state={})
    assert output["state_update"] is None


def _real_workflow(recommendation_fn=recommend_next_concept, semantic_adjudicator=None):
    knowledge = load_knowledge_points(KNOWLEDGE_FILE)
    questions = load_diagnostic_questions(QUESTIONS_FILE, knowledge)
    tracks = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    diagnostic = DiagnosticTutorService(
        questions_data=questions,
        tracks_data=tracks,
        valid_concept_ids={point["id"] for point in knowledge["knowledge_points"]},
        semantic_adjudicator=semantic_adjudicator,
    )
    integration = DiagnosticStateIntegrationService(
        knowledge_data=knowledge,
        recommendation_fn=recommendation_fn,
    )
    return DiagnosticWorkflowService(
        diagnostic_service=diagnostic,
        state_integration_service=integration,
    )


class _AdvisorySemantic:
    def __init__(self, judgments):
        self.judgments = judgments
        self.calls = 0

    def adjudicate(self, **_kwargs):
        self.calls += 1
        return {"judgments": copy.deepcopy(self.judgments), "confidence": 1.0}


def test_semantic_advisory_marks_only_the_next_retry_as_clarification_assisted():
    semantic = _AdvisorySemantic(
        [{"criterion_id": "layer_order", "status": "entailed"}]
    )
    learner_state = load_learner_state(LEARNER_STATE_FILE, load_knowledge_points(KNOWLEDGE_FILE))
    learner_state["mastery"] = {}
    workflow = _real_workflow(semantic_adjudicator=semantic)
    started = workflow.start()

    advisory = workflow.submit(
        session=started["diagnostic"]["session"],
        answer="BFS 使用队列保存 frontier。",
        learner_state=learner_state,
    )

    assert semantic.calls == 1
    assert advisory["diagnostic"]["evaluation"]["passed"] is False
    assert advisory["diagnostic"]["evaluation"]["needs_clarification"] is True
    assert advisory["diagnostic"]["evaluation"]["mastery_score"] == pytest.approx(0.2)
    assert advisory["diagnostic"]["question"]["step_number"] == 1
    assert advisory["diagnostic"]["question"]["attempt_number"] == 2
    assert advisory["state_update"] is None
    assert advisory["teaching_feedback"]["mode"] == "scaffold"
    assert "full_answer_revealed" not in advisory["diagnostic"]["session"]
    assert advisory["diagnostic"]["session"]["pending_assistance"] == {
        "level": "clarification",
        "source": "semantic_advisory",
    }
    assert advisory["diagnostic"]["session"]["history"][-1]["score"] == pytest.approx(0.2)
    assert advisory["diagnostic"]["session"]["history"][-1]["assisted"] is False

    passed = workflow.submit(
        session=advisory["diagnostic"]["session"],
        answer="BFS 按层逐层扩展，frontier 用 FIFO 队列维护。",
        learner_state=learner_state,
    )
    assert passed["diagnostic"]["evaluation"]["passed"] is True
    assert passed["diagnostic"]["evaluation"]["assisted"] is True
    assert passed["diagnostic"]["evaluation"]["assistance_level"] == "clarification"
    assert "pending_assistance" not in passed["diagnostic"]["session"]


def test_semantic_clarification_retry_can_pass_without_becoming_independent_mastery():
    recommendation_calls = []

    def recommendation(_knowledge, learner_state):
        recommendation_calls.append(copy.deepcopy(learner_state))
        return {"concept_id": None}

    semantic = _AdvisorySemantic(
        [{"criterion_id": "layer_order", "status": "entailed"}]
    )
    learner_state = load_learner_state(LEARNER_STATE_FILE, load_knowledge_points(KNOWLEDGE_FILE))
    learner_state["mastery"] = {}
    original_state = copy.deepcopy(learner_state)
    workflow = _real_workflow(recommendation, semantic)
    result = workflow.start()

    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="BFS 使用队列保存 frontier。",
        learner_state=learner_state,
    )
    assert result["diagnostic"]["evaluation"]["mastery_score"] == pytest.approx(0.2)
    assert result["diagnostic"]["session"]["pending_assistance"]["level"] == (
        "clarification"
    )
    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="BFS 按层逐层扩展，frontier 使用 FIFO 队列维护。",
        learner_state=learner_state,
    )
    assert result["diagnostic"]["evaluation"]["passed"] is True
    assert result["diagnostic"]["evaluation"]["assistance_level"] == "clarification"

    # Finish the remaining steps without adding a later independent correct
    # BFS observation; the clarification retry must not supply one itself.
    for answer in ("不知道。", "还是不知道。", "不知道。", "还是不知道。"):
        result = workflow.submit(
            session=result["diagnostic"]["session"],
            answer=answer,
            learner_state=learner_state,
        )

    assert result["diagnostic"]["status"] == "completed"
    history = result["diagnostic"]["session"]["history"]
    assert [entry["assistance_level"] for entry in history[:2]] == [
        "none",
        "clarification",
    ]
    summary = result["diagnostic"]["summary"]
    assert summary["concept_observation_assistance_levels"]["breadth_first_search"][:2] == [
        "none",
        "clarification",
    ]
    assert result["purpose"] == "formative"
    assert result["evidence_eligible"] is False
    assert result["state_update"] is None
    assert recommendation_calls == []
    assert learner_state == original_state
    assert semantic.calls == 1


def test_ucs_semantic_clarification_retry_is_assisted_but_advances_the_step():
    semantic = _AdvisorySemantic(
        [{"criterion_id": "unequal_costs", "status": "entailed"}]
    )
    learner_state = load_learner_state(LEARNER_STATE_FILE, load_knowledge_points(KNOWLEDGE_FILE))
    learner_state["mastery"] = {}
    workflow = _real_workflow(semantic_adjudicator=semantic)
    result = workflow.start()
    for answer in (
        "BFS 按层逐层扩展，frontier 使用 FIFO 队列维护。",
        "BFS 只保证步数最少；只有每步代价相同时才保证路径总代价最低。",
    ):
        result = workflow.submit(
            session=result["diagnostic"]["session"],
            answer=answer,
            learner_state=learner_state,
        )

    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer=(
            "它会把从起点走到每个候选节点沿途花掉的成本都累计起来，"
            "当前总花费更小的节点先扩展。"
        ),
        learner_state=learner_state,
    )
    assert result["diagnostic"]["evaluation"]["passed"] is False
    assert result["diagnostic"]["evaluation"]["needs_clarification"] is True
    assert result["diagnostic"]["session"]["pending_assistance"] == {
        "level": "clarification",
        "source": "semantic_advisory",
    }
    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="代价不同时使用 UCS；它按累计路径代价 g(n) 最小扩展节点。",
        learner_state=learner_state,
    )
    assert result["diagnostic"]["evaluation"]["passed"] is True
    assert result["diagnostic"]["evaluation"]["assistance_level"] == "clarification"
    assert result["diagnostic"]["question"] is None


def test_last_semantic_advisory_attempt_is_unresolved_and_reveals_without_semantic_mastery():
    semantic = _AdvisorySemantic(
        [{"criterion_id": "layer_order", "status": "entailed"}]
    )
    learner_state = {
        "student_id": "test",
        "mastery": {},
        "misconceptions": [],
        "learning_evidence": [],
    }
    workflow = _real_workflow(semantic_adjudicator=semantic)
    result = workflow.start()
    for _ in range(2):
        result = workflow.submit(
            session=result["diagnostic"]["session"],
            answer="BFS 使用队列保存 frontier。",
            learner_state=learner_state,
        )

    evaluation = result["diagnostic"]["evaluation"]
    assert evaluation["passed"] is False
    assert evaluation["needs_clarification"] is True
    assert evaluation["mastery_score"] == pytest.approx(0.2)
    assert result["diagnostic"]["question"]["step_number"] == 2
    assert result["teaching_feedback"]["mode"] == "reveal"
    assert result["teaching_feedback"]["remaining_attempts"] == 0
    assert result["state_update"] is None


def test_workflow_current_question_recovers_from_latest_real_session():
    workflow = _real_workflow()
    result = workflow.start()
    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="BFS 按层逐层扩展，使用 FIFO 队列。",
        learner_state={"student_id": "test", "mastery": {}, "misconceptions": [], "learning_evidence": []},
    )
    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="BFS 只保证边数少；只有每条边的花费都一样时，边数少才等于总成本低。",
        learner_state={"student_id": "test", "mastery": {}, "misconceptions": [], "learning_evidence": []},
    )

    current = workflow.current_question(session=result["diagnostic"]["session"])

    assert current["id"] == "dq_ucs_when_costs_differ_001"
    assert current["step_number"] == 3
    assert "路径甲只走2步" not in current["prompt"]


def test_real_three_step_open_workflow_preserves_feedback_but_never_updates_state():
    knowledge = load_knowledge_points(KNOWLEDGE_FILE)
    learner_state = load_learner_state(LEARNER_STATE_FILE, knowledge)
    original = copy.deepcopy(learner_state)
    workflow = _real_workflow()

    result = workflow.start()
    answers = [
        "BFS 按层逐层扩展，使用 FIFO 队列。",
        "BFS 总能找到总代价最低路径。",
        "BFS 并不总能保证总代价最低，只有每步代价相同时才成立。",
        "UCS 不是按步数，而是按累计路径代价 g(n) 用优先队列扩展。",
    ]
    statuses = []
    for answer in answers:
        result = workflow.submit(
            session=result["diagnostic"]["session"],
            answer=answer,
            learner_state=learner_state,
        )
        statuses.append(result["diagnostic"]["status"])

    assert statuses == ["in_progress", "in_progress", "in_progress", "completed"]
    assert result["diagnostic"]["summary"]["passed_steps"] == 3
    blocking_attempt = result["diagnostic"]["session"]["history"][1]
    assert blocking_attempt["misconception_ids"] == ["bfs_always_cost_optimal"]
    assert blocking_attempt["score"] == 0.0
    assert blocking_attempt["assistance_level"] == "none"
    assert result["purpose"] == "formative"
    assert result["evidence_eligible"] is False
    assert result["state_update"] is None
    assert learner_state == original


def test_real_retry_feedback_uses_pre_update_state_and_preserves_last_attempt():
    learner_state = {
        "student_id": "test",
        "mastery": {},
        "misconceptions": [],
        "learning_evidence": [],
    }
    original = copy.deepcopy(learner_state)
    workflow = _real_workflow()
    started = workflow.start(variant_round=1)

    result = workflow.submit(
        session=started["diagnostic"]["session"],
        answer="不知道。",
        learner_state=learner_state,
    )

    feedback = result["teaching_feedback"]
    assert feedback["mode"] == "reveal"
    assert feedback["remaining_attempts"] == 1
    assert feedback["model_answer"]
    assert feedback["explanation"]
    assert feedback["messages"][-1] == "请阅读参考答案后，用自己的话重新作答。"
    assert result["diagnostic"]["question"]["id"] == "dq_bfs_expansion_001"
    assert result["diagnostic"]["question"]["attempt_number"] == 2
    assert result["diagnostic"]["session"]["pending_assistance"] == {
        "level": "reveal",
        "source": "model_answer",
    }
    assert result["state_update"] is None
    assert learner_state == original
    assert "model_answer" not in repr(result["diagnostic"]["session"]["history"])


@pytest.mark.parametrize(
    "mastery,expected_mode",
    [(0.7, "hint"), (0.4, "scaffold")],
)
def test_hint_and_scaffold_retries_are_assisted_but_can_pass(
    mastery, expected_mode
):
    knowledge = load_knowledge_points(KNOWLEDGE_FILE)
    learner_state = load_learner_state(LEARNER_STATE_FILE, knowledge)
    learner_state["mastery"]["breadth_first_search"] = mastery
    workflow = _real_workflow()
    result = workflow.start()

    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="不知道。",
        learner_state=learner_state,
    )

    assert result["teaching_feedback"]["mode"] == expected_mode
    assert result["diagnostic"]["session"]["pending_assistance"] == {
        "level": expected_mode,
        "source": "deterministic_feedback",
    }
    retry = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="BFS 按层逐层扩展。",
        learner_state=learner_state,
    )
    assert retry["diagnostic"]["evaluation"]["passed"] is True
    assert retry["diagnostic"]["evaluation"]["assisted"] is True
    assert retry["diagnostic"]["evaluation"]["assistance_level"] == expected_mode


@pytest.mark.parametrize("variant_round", [0, 1])
def test_reveal_assisted_retry_preserves_raw_score_but_uses_prior_independent_signal(
    variant_round,
):
    recommendation_calls = []

    def recommendation(_knowledge, state):
        recommendation_calls.append(copy.deepcopy(state))
        return {"concept_id": None}

    knowledge = load_knowledge_points(KNOWLEDGE_FILE)
    learner_state = load_learner_state(LEARNER_STATE_FILE, knowledge)
    learner_state["mastery"]["breadth_first_search"] = 0.0
    original_state = copy.deepcopy(learner_state)
    workflow = _real_workflow(recommendation)
    result = workflow.start(variant_round=variant_round)

    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="不知道。",
        learner_state=learner_state,
    )
    assert result["teaching_feedback"]["mode"] == "reveal"
    assert result["diagnostic"]["session"]["pending_assistance"] == {
        "level": "reveal",
        "source": "model_answer",
    }

    result = workflow.submit(
        session=result["diagnostic"]["session"],
        answer="BFS 按层逐层扩展，frontier 使用 FIFO 队列。",
        learner_state=learner_state,
    )
    assert result["diagnostic"]["evaluation"]["passed"] is True
    assert result["diagnostic"]["evaluation"]["assisted"] is True
    assert "pending_assistance" not in result["diagnostic"]["session"]
    assert [entry["assisted"] for entry in result["diagnostic"]["session"]["history"]] == [
        False,
        True,
    ]

    for answer in (
        "不知道。",
        "还是不知道。",
        "动作代价不同时使用 UCS，按累计路径代价 g(n) 最小选择。",
    ):
        result = workflow.submit(
            session=result["diagnostic"]["session"],
            answer=answer,
            learner_state=learner_state,
        )

    assert result["diagnostic"]["status"] == "completed"
    summary = result["diagnostic"]["summary"]
    assert summary["concept_observations"]["breadth_first_search"] == [
        0.0,
        1.0,
        0.0,
        0.0,
    ]
    assert summary["concept_observation_assistance"]["breadth_first_search"] == [
        False,
        True,
        False,
        True,
    ]
    assert result["purpose"] == "formative"
    assert result["state_update"] is None
    assert recommendation_calls == []
    assert learner_state == original_state


def test_final_failed_open_step_reveals_without_integration():
    knowledge = load_knowledge_points(KNOWLEDGE_FILE)
    learner_state = load_learner_state(LEARNER_STATE_FILE, knowledge)
    original = copy.deepcopy(learner_state)
    workflow = _real_workflow()
    result = workflow.start()
    for answer in (
        "BFS 按层逐层扩展。",
        "BFS 保证步数最少；只有每步代价相同时才等价于总代价最低。",
        "不知道。",
        "还是不知道。",
    ):
        result = workflow.submit(
            session=result["diagnostic"]["session"],
            answer=answer,
            learner_state=learner_state,
        )

    assert result["diagnostic"]["status"] == "completed"
    assert result["teaching_feedback"]["mode"] == "reveal"
    assert result["teaching_feedback"]["remaining_attempts"] == 0
    assert result["teaching_feedback"]["messages"][-1] == (
        "已展示参考答案，本题暂未解决并进入下一步。"
    )
    assert result["state_update"] is None
    assert learner_state == original
    assert result["teaching_feedback"]["model_answer"] not in repr(
        result["diagnostic"]["summary"]
    )


def test_canonical_and_variant_rounds_share_formative_scoring_without_state_update():
    knowledge = load_knowledge_points(KNOWLEDGE_FILE)
    base_state = load_learner_state(LEARNER_STATE_FILE, knowledge)
    answers = [
        "BFS 按层逐层扩展，使用 FIFO 队列。",
        "BFS 只保证步数最少；只有每步代价相同时才保证路径总代价最低。",
        "动作代价不同时使用 UCS，按累计路径代价 g(n) 最小选择，并用优先队列维护 frontier。",
    ]

    def complete(variant_round):
        workflow = _real_workflow()
        result = workflow.start(variant_round=variant_round)
        first_prompt = result["diagnostic"]["question"]["prompt"]
        for answer in answers:
            result = workflow.submit(
                session=result["diagnostic"]["session"],
                answer=answer,
                learner_state=copy.deepcopy(base_state),
            )
        return first_prompt, result

    canonical_prompt, canonical_result = complete(0)
    variant_prompt, variant_result = complete(1)

    assert canonical_prompt != variant_prompt
    assert canonical_result["diagnostic"]["summary"] == variant_result["diagnostic"][
        "summary"
    ]
    assert all(
        level == "none"
        for levels in canonical_result["diagnostic"]["summary"][
            "concept_observation_assistance_levels"
        ].values()
        for level in levels
    )
    assert canonical_result["state_update"] is None
    assert variant_result["state_update"] is None
