from pathlib import Path

import pytest

from introai_tutor.deterministic_diagnostic_request import (
    DeterministicDiagnosticRequestParser,
    DiagnosticRequestParseError,
)
from introai_tutor.knowledge import load_knowledge_points


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def parser():
    return DeterministicDiagnosticRequestParser(
        knowledge_data=load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    )


@pytest.mark.parametrize(
    ("question", "expected_topic_ids"),
    [
        (
            "请用审核诊断题测试我对一致代价搜索如何选择下一个节点的理解。",
            ["uniform_cost_search"],
        ),
        (
            "请用诊断题测试我对迭代加深深度优先搜索的理解。",
            ["iterative_deepening_search"],
        ),
        ("请用审核诊断题测试我对 A* 搜索的理解。", ["a_star_search"]),
        ("请用审核诊断题测试我对  uCs  的理解。", ["uniform_cost_search"]),
    ],
)
def test_strong_explicit_requests_resolve_controlled_course_concepts(
    parser, question, expected_topic_ids
):
    result = parser.parse(question)

    assert result is not None
    assert result["intent"] == "diagnostic_request"
    assert result["topic_ids"] == expected_topic_ids
    assert result["diagnostic_topic_ids"] == expected_topic_ids
    assert result["supporting_topic_ids"] == []


def test_multi_concept_requests_use_stable_registry_order(parser):
    result = parser.parse("请用审核诊断题测试我对 UCS 和 BFS 的理解。")

    assert result is not None
    assert result["topic_ids"] == ["breadth_first_search", "uniform_cost_search"]


@pytest.mark.parametrize(
    "question",
    [
        "一致代价搜索为什么选择累计代价最小的节点？",
        "请解释一致代价搜索。",
        "我不理解一致代价搜索。",
        "给我出一道题。",
        "请解释审核诊断是什么。",
        "请用审核诊断题测试我对量子搜索的理解。",
    ],
)
def test_ordinary_ambiguous_or_unsupported_requests_fail_closed(parser, question):
    assert parser.parse(question) is None


def test_parser_rejects_invalid_question_and_never_uses_model(parser):
    with pytest.raises(DiagnosticRequestParseError):
        parser.parse("   ")
    with pytest.raises(DiagnosticRequestParseError):
        parser.parse(123)  # type: ignore[arg-type]
