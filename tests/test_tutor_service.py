import copy
import logging
from pathlib import Path

import pytest

from introai_tutor.course_materials import load_course_chunks
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.retrieval import retrieve_course_chunks
from introai_tutor.tutor_service import TutorService, TutorServiceError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeUnderstandingService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def understand(self, question):
        self.calls.append(question)
        return self.result


class FakeAnswerService:
    def __init__(self, result=None):
        self.result = result or {
            "status": "answered",
            "answer": "grounded answer",
            "answer_blocks": [],
            "used_chunk_ids": [],
            "limitations": [],
            "confidence": 0.8,
        }
        self.calls = []

    def answer(self, *, question, understanding, retrieval_results):
        self.calls.append(
            {
                "question": question,
                "understanding": understanding,
                "retrieval_results": retrieval_results,
            }
        )
        return self.result


class FakeRetriever:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def __call__(self, course_data, **kwargs):
        self.calls.append({"course_data": course_data, **kwargs})
        return self.results


class FakeDiagnosticPlanService:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def plan_from_qa_result(self, *, qa_result):
        self.calls.append(copy.deepcopy(qa_result))
        return copy.deepcopy(self.plan)


def _understanding(**changes):
    result = {
        "in_scope": True,
        "intent": "explanation",
        "topic_ids": ["breadth_first_search"],
        "search_terms": ["BFS"],
        "needs_clarification": False,
        "clarifying_question": None,
        "confidence": 0.9,
    }
    result.update(changes)
    return result


def _candidate(
    chunk_id,
    *,
    topics=("breadth_first_search",),
    matched_topics=None,
    source_role="course_core",
):
    return {
        "chunk": {
            "id": chunk_id,
            "topic_ids": list(topics),
            "source_role": source_role,
            "source_file": f"{chunk_id}.pdf",
            "page_start": 1,
            "page_end": 1,
            "section_title": chunk_id,
            "content": f"content for {chunk_id}",
            "review_status": "codex_draft",
        },
        "score": 100.0,
        "matched_topic_ids": list(topics if matched_topics is None else matched_topics),
        "matched_terms": [],
        "score_breakdown": {"topic": 100.0},
    }


def _service(
    *,
    understanding=None,
    candidates=None,
    answer_result=None,
    valid_topic_ids=("breadth_first_search", "uniform_cost_search", "a_star_search"),
    **kwargs,
):
    understanding_service = FakeUnderstandingService(understanding or _understanding())
    answer_service = FakeAnswerService(answer_result)
    retriever = FakeRetriever(candidates if candidates is not None else [_candidate("bfs")])
    kwargs.setdefault(
        "max_prerequisite_chunks",
        min(3, kwargs.get("max_evidence_chunks", 6)),
    )
    service = TutorService(
        understanding_service=understanding_service,
        answer_service=answer_service,
        course_data={"chunks": [{"id": f"fixture_{index}"} for index in range(20)]},
        valid_topic_ids=valid_topic_ids,
        retriever=retriever,
        **kwargs,
    )
    return service, understanding_service, answer_service, retriever


def test_normal_flow_calls_understanding_retriever_and_answer_once():
    service, understanding_service, answer_service, retriever = _service()

    result = service.ask("  What is BFS?  ")

    assert understanding_service.calls == ["What is BFS?"]
    assert len(retriever.calls) == 1
    assert len(answer_service.calls) == 1
    assert result["question"] == "What is BFS?"
    assert result["retrieval"]["candidate_count"] == 1
    assert result["retrieval"]["selected_chunk_ids"] == ["bfs"]


def test_available_reviewed_diagnostic_request_returns_safe_transition_without_answer_call():
    planner = FakeDiagnosticPlanService(
        {"available": True, "template_ids": ["reviewed_template"]}
    )
    service, _, answer_service, retriever = _service(
        understanding=_understanding(intent="diagnostic_request"),
        diagnostic_plan_service=planner,
    )

    result = service.ask("请用一道审核题测试 BFS。")

    assert result["response"]["status"] == "diagnostic_available"
    assert "审核诊断题" in result["response"]["answer"]
    assert result["response"]["answer_blocks"] == []
    assert result["diagnostic_plan"]["template_ids"] == ["reviewed_template"]
    assert retriever.calls == []
    assert answer_service.calls == []
    assert planner.calls[0]["understanding"]["topic_ids"] == ["breadth_first_search"]


def test_unavailable_diagnostic_request_keeps_normal_course_answer_without_creating_evidence():
    planner = FakeDiagnosticPlanService({"available": False, "template_ids": []})
    service, _, answer_service, retriever = _service(
        understanding=_understanding(intent="diagnostic_request"),
        diagnostic_plan_service=planner,
    )

    result = service.ask("请测试一个还没有审核模板的概念。")

    assert len(planner.calls) == 1
    assert len(retriever.calls) == 1
    assert len(answer_service.calls) == 1
    assert result["response"]["status"] == "answered"
    assert result["diagnostic_plan"]["available"] is False


def test_retriever_receives_question_understanding_inputs_and_configuration():
    understanding = _understanding(
        topic_ids=["breadth_first_search", "uniform_cost_search"],
        search_terms=["BFS", "UCS", "path cost"],
    )
    service, _, _, retriever = _service(
        understanding=understanding,
        candidate_top_k=9,
        include_prerequisite_support=False,
    )

    service.ask("BFS and UCS")

    call = retriever.calls[0]
    assert call["query"] == "BFS and UCS"
    assert call["topic_ids"] == ["breadth_first_search", "uniform_cost_search"]
    assert call["search_terms"] == ["BFS", "UCS", "path cost"]
    assert call["top_k"] == 20
    assert call["include_prerequisite_support"] is False


def test_retrieval_uses_all_topics_while_preserving_diagnostic_roles():
    understanding = _understanding(
        intent="comparison",
        topic_ids=[
            "breadth_first_search",
            "completeness_optimality_complexity",
            "uniform_cost_search",
        ],
        diagnostic_topic_ids=[
            "breadth_first_search",
            "completeness_optimality_complexity",
        ],
        supporting_topic_ids=["uniform_cost_search"],
        search_terms=["BFS", "path cost", "UCS"],
    )
    candidates = [
        _candidate("bfs", topics=("breadth_first_search",)),
        _candidate(
            "optimality", topics=("completeness_optimality_complexity",)
        ),
        _candidate("ucs", topics=("uniform_cost_search",)),
    ]
    service, _, answer_service, retriever = _service(
        understanding=understanding,
        candidates=candidates,
        valid_topic_ids=(
            "breadth_first_search",
            "completeness_optimality_complexity",
            "uniform_cost_search",
        ),
    )

    result = service.ask("BFS 找到的是步数最少还是总代价最低？")

    assert retriever.calls[0]["topic_ids"] == understanding["topic_ids"]
    assert result["understanding"] == understanding
    assert answer_service.calls[0]["understanding"] == understanding


def test_single_topic_keeps_candidate_top_k_window():
    service, _, _, retriever = _service(candidate_top_k=9)

    service.ask("BFS")

    assert retriever.calls[0]["top_k"] == 9


def test_out_of_scope_short_circuits_retrieval_but_calls_answer_service():
    understanding = _understanding(
        in_scope=False,
        intent="out_of_scope",
        topic_ids=[],
        search_terms=[],
    )
    service, _, answer_service, retriever = _service(understanding=understanding)

    result = service.ask("What is the weather?")

    assert retriever.calls == []
    assert len(answer_service.calls) == 1
    assert answer_service.calls[0]["retrieval_results"] == []
    assert result["retrieval"] == {
        "candidate_count": 0,
        "selected_count": 0,
        "selected_chunk_ids": [],
        "topic_coverage": {},
        "results": [],
    }


def test_clarification_short_circuits_retrieval_but_calls_answer_service():
    understanding = _understanding(
        needs_clarification=True,
        clarifying_question="你想问哪种最优性？",
    )
    service, _, answer_service, retriever = _service(understanding=understanding)

    service.ask("最优是什么意思？")

    assert retriever.calls == []
    assert len(answer_service.calls) == 1
    assert answer_service.calls[0]["retrieval_results"] == []


def test_no_candidate_evidence_is_forwarded_to_answer_service():
    insufficient = {
        "status": "insufficient_evidence",
        "answer": "evidence is insufficient",
        "answer_blocks": [],
        "used_chunk_ids": [],
        "limitations": ["no chunks"],
        "confidence": 0.0,
    }
    service, _, answer_service, retriever = _service(candidates=[], answer_result=insufficient)

    result = service.ask("BFS")

    assert len(retriever.calls) == 1
    assert answer_service.calls[0]["retrieval_results"] == []
    assert result["response"] == insufficient


def test_topic_coverage_prefers_course_core_over_higher_ranked_support():
    support = _candidate("support_first", source_role="prerequisite_support")
    core = _candidate("core_second")
    service, _, _, _ = _service(candidates=[support, core], max_evidence_chunks=1)

    result = service.ask("BFS")

    assert result["retrieval"]["selected_chunk_ids"] == ["core_second"]
    assert result["retrieval"]["topic_coverage"] == {
        "breadth_first_search": ["core_second"]
    }


def test_topic_without_core_uses_prerequisite_support_when_available():
    support = _candidate("only_support", source_role="prerequisite_support")
    service, _, _, _ = _service(candidates=[support], max_evidence_chunks=1)

    result = service.ask("BFS")

    assert result["retrieval"]["selected_chunk_ids"] == ["only_support"]
    assert result["retrieval"]["topic_coverage"] == {
        "breadth_first_search": ["only_support"]
    }


def test_shared_chunk_covers_multiple_topics_without_duplicate_selection():
    shared = _candidate(
        "shared_core",
        topics=("breadth_first_search", "uniform_cost_search"),
    )
    understanding = _understanding(
        topic_ids=["breadth_first_search", "uniform_cost_search"],
        search_terms=["BFS", "UCS"],
    )
    service, _, _, _ = _service(
        understanding=understanding,
        candidates=[shared],
        max_evidence_chunks=2,
    )

    result = service.ask("BFS versus UCS")

    assert result["retrieval"]["selected_chunk_ids"] == ["shared_core"]
    assert result["retrieval"]["topic_coverage"] == {
        "breadth_first_search": ["shared_core"],
        "uniform_cost_search": ["shared_core"],
    }


def test_topic_coverage_uses_next_unselected_core_when_generic_chunk_is_already_selected():
    generic = _candidate(
        "generic_first",
        topics=("breadth_first_search", "uniform_cost_search"),
    )
    ucs = _candidate("ucs_specific", topics=("uniform_cost_search",))
    understanding = _understanding(
        topic_ids=["breadth_first_search", "uniform_cost_search"],
        search_terms=["BFS", "UCS"],
    )
    service, _, _, _ = _service(
        understanding=understanding,
        candidates=[generic, ucs],
        max_evidence_chunks=2,
    )

    result = service.ask("BFS versus UCS")

    assert result["retrieval"]["selected_chunk_ids"] == ["generic_first", "ucs_specific"]
    assert "ucs_specific" in result["retrieval"]["topic_coverage"]["uniform_cost_search"]


def test_topic_specificity_beats_higher_ranked_broad_core_candidate():
    broad = _candidate(
        "broad_first",
        topics=(
            "breadth_first_search",
            "uniform_cost_search",
            "a_star_search",
        ),
    )
    focused = _candidate("focused_second", topics=("breadth_first_search",))
    service, _, _, _ = _service(
        candidates=[broad, focused],
        max_evidence_chunks=1,
    )

    result = service.ask("BFS")

    assert result["retrieval"]["selected_chunk_ids"] == ["focused_second"]


def test_equal_specificity_keeps_original_retrieval_rank():
    first = _candidate("first", topics=("breadth_first_search",))
    second = _candidate("second", topics=("breadth_first_search",))
    service, _, _, _ = _service(
        candidates=[first, second],
        max_evidence_chunks=1,
    )

    assert service.ask("BFS")["retrieval"]["selected_chunk_ids"] == ["first"]


def test_phase_two_adds_core_evidence_when_topic_selection_selected_only_support():
    support = _candidate("support", source_role="prerequisite_support")
    unrelated_core = _candidate("core", topics=("a_star_search",), matched_topics=[])
    service, _, _, _ = _service(candidates=[support, unrelated_core], max_evidence_chunks=2)

    result = service.ask("BFS")

    assert result["retrieval"]["selected_chunk_ids"] == ["support", "core"]


def test_fill_preserves_original_candidate_ranking_order():
    support = _candidate("support_first", source_role="prerequisite_support")
    core = _candidate("core_second")
    extra = _candidate("core_third")
    service, _, _, _ = _service(candidates=[support, core, extra], max_evidence_chunks=3)

    result = service.ask("BFS")

    assert result["retrieval"]["selected_chunk_ids"] == [
        "support_first",
        "core_second",
        "core_third",
    ]


def test_support_count_is_limited_while_core_can_fill_remaining_slots():
    candidates = [
        _candidate("support_one", source_role="prerequisite_support"),
        _candidate("support_two", source_role="prerequisite_support"),
        _candidate("support_three", source_role="prerequisite_support"),
        _candidate("core_one"),
        _candidate("core_two"),
    ]
    service, _, _, _ = _service(
        candidates=candidates,
        max_evidence_chunks=4,
        max_prerequisite_chunks=1,
    )

    result = service.ask("BFS")

    selected = result["retrieval"]["results"]
    assert len(selected) == 3
    assert sum(item["chunk"]["source_role"] == "prerequisite_support" for item in selected) == 1
    assert [item["chunk"]["id"] for item in selected] == [
        "support_one",
        "core_one",
        "core_two",
    ]


def test_candidate_count_below_evidence_limit_is_preserved():
    candidates = [_candidate("one"), _candidate("two")]
    service, _, _, _ = _service(candidates=candidates, max_evidence_chunks=4)

    result = service.ask("BFS")

    assert result["retrieval"]["candidate_count"] == 2
    assert result["retrieval"]["selected_count"] == 2


def test_topic_without_evidence_has_empty_coverage():
    candidate = _candidate("bfs", topics=("breadth_first_search",))
    understanding = _understanding(
        topic_ids=["breadth_first_search", "uniform_cost_search"],
        search_terms=["BFS", "UCS"],
    )
    service, _, _, _ = _service(understanding=understanding, candidates=[candidate])

    result = service.ask("BFS and UCS")

    assert result["retrieval"]["topic_coverage"]["uniform_cost_search"] == []


def test_multi_topic_retrieval_requires_valid_non_empty_course_chunk_list():
    understanding = _understanding(
        topic_ids=["breadth_first_search", "uniform_cost_search"],
        search_terms=["BFS", "UCS"],
    )
    service = TutorService(
        understanding_service=FakeUnderstandingService(understanding),
        answer_service=FakeAnswerService(),
        course_data={"chunks": []},
        valid_topic_ids={"breadth_first_search", "uniform_cost_search"},
        retriever=FakeRetriever([]),
    )

    with pytest.raises(TutorServiceError, match="non-empty chunks list"):
        service.ask("BFS versus UCS")


def test_duplicate_candidate_chunk_id_fails_explicitly():
    service, _, answer_service, _ = _service(candidates=[_candidate("same"), _candidate("same")])

    with pytest.raises(TutorServiceError, match="Duplicate candidate chunk id"):
        service.ask("BFS")

    assert answer_service.calls == []


def test_non_string_candidate_source_role_fails_with_domain_error():
    malformed = _candidate("malformed")
    malformed["chunk"]["source_role"] = []
    service, _, answer_service, _ = _service(candidates=[malformed])

    with pytest.raises(TutorServiceError, match="invalid source_role"):
        service.ask("BFS")

    assert answer_service.calls == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"course_data": []}, "course_data"),
        ({"valid_topic_ids": []}, "valid_topic_ids"),
        ({"valid_topic_ids": [" "]}, "valid_topic_ids"),
        ({"candidate_top_k": 0}, "candidate_top_k"),
        ({"candidate_top_k": True}, "candidate_top_k"),
        ({"max_evidence_chunks": 0}, "max_evidence_chunks"),
        ({"max_evidence_chunks": True}, "max_evidence_chunks"),
        ({"candidate_top_k": 2, "max_evidence_chunks": 3}, "greater than or equal"),
        ({"max_prerequisite_chunks": -1}, "max_prerequisite_chunks"),
        ({"max_prerequisite_chunks": True}, "max_prerequisite_chunks"),
        ({"max_prerequisite_chunks": 4, "max_evidence_chunks": 3}, "must not exceed"),
        ({"include_prerequisite_support": 1}, "include_prerequisite_support"),
        ({"retriever": None}, "retriever"),
    ],
)
def test_invalid_constructor_configuration_fails(kwargs, message):
    understanding_service = FakeUnderstandingService(_understanding())
    answer_service = FakeAnswerService()
    defaults = {
        "understanding_service": understanding_service,
        "answer_service": answer_service,
        "course_data": {"chunks": []},
        "valid_topic_ids": {"breadth_first_search"},
        "retriever": FakeRetriever([]),
    }
    defaults.update(kwargs)

    with pytest.raises(TutorServiceError, match=message):
        TutorService(**defaults)


def test_constructor_rejects_missing_service_methods():
    with pytest.raises(TutorServiceError, match="understanding_service"):
        TutorService(
            understanding_service=object(),
            answer_service=FakeAnswerService(),
            course_data={},
            valid_topic_ids={"breadth_first_search"},
            retriever=FakeRetriever([]),
        )
    with pytest.raises(TutorServiceError, match="answer_service"):
        TutorService(
            understanding_service=FakeUnderstandingService(_understanding()),
            answer_service=object(),
            course_data={},
            valid_topic_ids={"breadth_first_search"},
            retriever=FakeRetriever([]),
        )


@pytest.mark.parametrize("question", [None, 42, "  "])
def test_invalid_question_fails_before_understanding_call(question):
    service, understanding_service, _, _ = _service()

    with pytest.raises(TutorServiceError, match="question"):
        service.ask(question)

    assert understanding_service.calls == []


def test_qa_failure_exposes_stage_and_logs_bounded_correlation(caplog):
    class FailingUnderstanding:
        def understand(self, question):
            raise RuntimeError("transport failed with api_key=do-not-log")

    service = TutorService(
        understanding_service=FailingUnderstanding(),
        answer_service=FakeAnswerService(),
        course_data={"chunks": []},
        valid_topic_ids={"breadth_first_search"},
        retriever=FakeRetriever([]),
    )

    with caplog.at_level(logging.WARNING, logger="introai_tutor.tutor_service"):
        with pytest.raises(TutorServiceError) as error:
            service.ask("BFS question that must not appear in logs")

    assert error.value.failure_stage == "qa_topic_classification"
    assert error.value.stage == "qa_topic_classification"
    assert len(error.value.correlation_id) == 12
    record_text = " ".join(record.getMessage() for record in caplog.records)
    assert "qa_topic_classification" in record_text
    assert error.value.correlation_id in record_text
    assert "do-not-log" not in record_text
    assert "BFS question" not in record_text


def test_tutor_service_does_not_mutate_inputs_or_candidates():
    course_data = {"chunks": [{"id": "original"}]}
    valid_topic_ids = ["breadth_first_search"]
    understanding = _understanding()
    candidates = [_candidate("bfs")]
    before_course = copy.deepcopy(course_data)
    before_topics = copy.deepcopy(valid_topic_ids)
    before_understanding = copy.deepcopy(understanding)
    before_candidates = copy.deepcopy(candidates)
    understanding_service = FakeUnderstandingService(understanding)
    answer_service = FakeAnswerService()
    retriever = FakeRetriever(candidates)
    service = TutorService(
        understanding_service=understanding_service,
        answer_service=answer_service,
        course_data=course_data,
        valid_topic_ids=valid_topic_ids,
        retriever=retriever,
    )

    result = service.ask("BFS")

    assert course_data == before_course
    assert valid_topic_ids == before_topics
    assert understanding == before_understanding
    assert candidates == before_candidates
    assert result["retrieval"]["results"][0] is candidates[0]
    assert answer_service.calls[0]["retrieval_results"][0] is candidates[0]


@pytest.fixture(scope="module")
def real_data():
    knowledge_data = load_knowledge_points(PROJECT_ROOT / "data" / "knowledge_points.json")
    return (
        load_course_chunks(PROJECT_ROOT / "data" / "course_chunks.json", knowledge_data),
        {point["id"] for point in knowledge_data["knowledge_points"]},
    )


def _real_service(real_data, understanding):
    course_data, valid_topic_ids = real_data
    understanding_service = FakeUnderstandingService(understanding)
    answer_service = FakeAnswerService()
    service = TutorService(
        understanding_service=understanding_service,
        answer_service=answer_service,
        course_data=course_data,
        valid_topic_ids=valid_topic_ids,
    )
    return service, answer_service


def test_real_bfs_ucs_candidates_select_core_evidence_for_both_topics(real_data):
    service, _ = _real_service(
        real_data,
        _understanding(
            intent="comparison",
            topic_ids=["breadth_first_search", "uniform_cost_search"],
            search_terms=["BFS", "UCS", "步数最少", "路径代价"],
        ),
    )

    result = service.ask("BFS 找到的是步数最少还是总代价最低？")

    selected = result["retrieval"]["results"]
    selected_core_topics = {
        topic_id
        for candidate in selected
        if candidate["chunk"]["source_role"] == "course_core"
        for topic_id in candidate["chunk"]["topic_ids"]
    }
    assert {"breadth_first_search", "uniform_cost_search"} <= selected_core_topics
    coverage = result["retrieval"]["topic_coverage"]
    bfs_coverage_id = coverage["breadth_first_search"][0]
    ucs_coverage_id = coverage["uniform_cost_search"][0]
    selected_by_id = {item["chunk"]["id"]: item["chunk"] for item in selected}
    bfs_coverage = selected_by_id[bfs_coverage_id]
    ucs_coverage = selected_by_id[ucs_coverage_id]
    assert bfs_coverage_id != ucs_coverage_id
    assert bfs_coverage["source_role"] == "course_core"
    assert ucs_coverage["source_role"] == "course_core"
    assert "breadth_first_search" in bfs_coverage["topic_ids"]
    assert "uniform_cost_search" in ucs_coverage["topic_ids"]
    assert len(bfs_coverage["topic_ids"]) <= 2
    assert len(ucs_coverage["topic_ids"]) <= 2


def test_real_queue_bfs_keeps_core_and_prerequisite_support(real_data):
    service, _ = _real_service(
        real_data,
        _understanding(search_terms=["队列", "BFS"]),
    )

    result = service.ask("队列为什么适合 BFS？")

    selected = result["retrieval"]["results"]
    assert any(item["chunk"]["source_role"] == "course_core" for item in selected)
    assert any(
        item["chunk"]["id"] == "support_queue_fifo" for item in selected
    )


def test_real_dijkstra_ucs_keeps_distinct_support_and_core(real_data):
    service, _ = _real_service(
        real_data,
        _understanding(
            intent="comparison",
            topic_ids=["uniform_cost_search"],
            search_terms=["Dijkstra", "UCS"],
        ),
    )

    result = service.ask("Dijkstra 和 UCS 有什么关系？")

    selected = result["retrieval"]["results"]
    assert any(item["chunk"]["id"] == "support_dijkstra_shortest_path" for item in selected)
    assert any(
        item["chunk"]["source_role"] == "course_core"
        and "uniform_cost_search" in item["chunk"]["topic_ids"]
        for item in selected
    )


def test_single_topic_selection_does_not_needlessly_add_unrelated_topic_fixture():
    a_star = _candidate("a_star", topics=("a_star_search",))
    unrelated = _candidate("unrelated", topics=("uniform_cost_search",))
    service, _, _, _ = _service(
        understanding=_understanding(topic_ids=["a_star_search"], search_terms=["A*"]),
        candidates=[a_star, unrelated],
        valid_topic_ids=("a_star_search", "uniform_cost_search"),
        max_evidence_chunks=1,
    )

    result = service.ask("A* 是什么？")

    assert result["retrieval"]["selected_chunk_ids"] == ["a_star"]


def test_real_ucb_does_not_include_default_disabled_review_chunk(real_data):
    service, _ = _real_service(
        real_data,
        _understanding(
            topic_ids=["upper_confidence_bound"],
            search_terms=["UCB"],
        ),
    )

    result = service.ask("UCB 如何平衡探索和利用？")

    assert "lec6_adversarial_mcts_statistics" not in result["retrieval"]["selected_chunk_ids"]


def test_real_retriever_fixture_remains_deterministic_for_trace(real_data):
    course_data, valid_topic_ids = real_data
    expected = retrieve_course_chunks(
        course_data,
        query="BFS 是什么？",
        valid_topic_ids=valid_topic_ids,
        topic_ids=["breadth_first_search"],
        search_terms=["BFS"],
        top_k=12,
        include_prerequisite_support=True,
    )
    service, _ = _real_service(real_data, _understanding())

    result = service.ask("BFS 是什么？")

    assert result["retrieval"]["candidate_count"] == len(expected)
