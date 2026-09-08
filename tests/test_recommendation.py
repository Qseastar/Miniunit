import copy
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.learner import load_learner_state
from introai_tutor.recommend import (
    MASTERY_WEAKNESS_THRESHOLD,
    ReviewedEvidenceCatalog,
    recommend_next_concept,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
LEARNER_STATE_FILE = PROJECT_ROOT / "data" / "demo_student_state.json"

def test_recommend_target_when_prereqs_mastered():
    """测试场景：前置知识都已掌握，正常推荐当前薄弱点"""
    knowledge_data = {
        "search_problem": {"id": "search_problem", "prerequisites": []},
        "bfs": {"id": "bfs", "prerequisites": ["search_problem"]}
    }
    learner_state = {
        "mastery": {
            "search_problem": 0.8, # 前置已掌握
            "bfs": 0.3             # 目标未掌握
        }
    }
    result = recommend_next_concept(knowledge_data, learner_state)
    assert result["concept_id"] == "bfs"
    assert "掌握度偏低" in result["reason"]

def test_recommend_prereq_when_prereqs_weak():
    """测试场景：未掌握 A*，且前置 BFS 也没掌握，应优先推荐 BFS"""
    knowledge_data = {
        "search_problem": {"id": "search_problem", "prerequisites": []},
        "bfs": {"id": "bfs", "prerequisites": ["search_problem"]},
        "a_star": {"id": "a_star", "prerequisites": ["bfs"]}
    }
    learner_state = {
        "mastery": {
            "search_problem": 0.9,
            "bfs": 0.4,    # 前置未掌握
            "a_star": 0.1  # 目标未掌握
        }
    }
    # 预期算法会从 a_star 顺藤摸瓜找到 bfs
    result = recommend_next_concept(knowledge_data, learner_state)
    assert result["concept_id"] == "bfs"

def test_recommend_no_weak_concepts():
    """测试场景：全部知识点掌握度都大于等于 0.6"""
    knowledge_data = {
        "bfs": {"id": "bfs", "prerequisites": []}
    }
    learner_state = {
        "mastery": {
            "bfs": 0.9
        }
    }
    result = recommend_next_concept(knowledge_data, learner_state)
    assert result["concept_id"] is None
    assert "太棒了" in result["reason"]


def test_recommend_accepts_knowledge_point_list():
    knowledge_data = [
        {"id": "search_problem", "prerequisites": []},
        {"id": "bfs", "prerequisites": ["search_problem"]},
    ]
    learner_state = {
        "mastery": {
            "search_problem": 0.8,
            "bfs": 0.3,
        }
    }

    result = recommend_next_concept(knowledge_data, learner_state)

    assert result["concept_id"] == "bfs"


def test_recommend_accepts_loaded_knowledge_document():
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    learner_state = load_learner_state(LEARNER_STATE_FILE, knowledge_data)

    result = recommend_next_concept(knowledge_data, learner_state)

    valid_concept_ids = {point["id"] for point in knowledge_data["knowledge_points"]}
    assert result["concept_id"] in valid_concept_ids


def test_recommend_rejects_mapping_with_non_point_value():
    with pytest.raises(ValueError, match="Knowledge point at bfs must be an object"):
        recommend_next_concept({"bfs": "not a knowledge point"}, {"mastery": {}})


def _evidence_catalog():
    return ReviewedEvidenceCatalog(
        templates=[
            {
                "id": "verify_foundation_one",
                "concept_ids": ["foundation"],
                "misconception_rules": [{"misconception_id": "foundation_error"}],
            },
            {
                "id": "verify_foundation_two",
                "concept_ids": ["foundation"],
                "misconception_rules": [],
            },
            {
                "id": "verify_next",
                "concept_ids": ["next"],
                "misconception_rules": [],
            },
        ]
    )


def _actionable_knowledge():
    return {
        "foundation": {"id": "foundation", "prerequisites": []},
        "next": {"id": "next", "prerequisites": ["foundation"]},
        "uncovered": {"id": "uncovered", "prerequisites": []},
    }


def _state(*, mastery=None, outcomes=None, misconceptions=None, practice_only=False):
    evidence = []
    if outcomes is not None:
        evidence.append(
            {
                "evidence_eligible": not practice_only,
                "template_ids": [item["template_id"] for item in outcomes],
                "template_outcomes": outcomes,
            }
        )
    return {
        "mastery": mastery or {},
        "learning_evidence": evidence,
        "misconceptions": misconceptions or [],
    }


def _outcome(template_id, status="passed", level="none"):
    return {
        "template_id": template_id,
        "status": status,
        "final_attempt_assistance_level": level,
    }


def test_new_learner_with_available_formal_evidence_is_not_skipped():
    result = recommend_next_concept(
        _actionable_knowledge(), _state(), reviewed_evidence_catalog=_evidence_catalog()
    )

    assert result["concept_id"] == "foundation"
    assert result["evidence_status"] == "formal_evidence_available"
    assert result["remaining_formal_evidence_opportunities"] == 2


def test_partially_used_formal_evidence_remains_the_next_action():
    result = recommend_next_concept(
        _actionable_knowledge(),
        _state(
            mastery={"foundation": 0.35}, outcomes=[_outcome("verify_foundation_one")]
        ),
        reviewed_evidence_catalog=_evidence_catalog(),
    )

    assert result["concept_id"] == "foundation"
    assert result["remaining_formal_evidence_opportunities"] == 1


def test_all_independent_correct_evidence_below_threshold_no_longer_blocks_progression():
    # Preserve P0's real numerical ceiling: two correct observations do not
    # magically cross the 0.6 mastery threshold.
    mastery = 0.65 * (0.65 * 0.0 + 0.35) + 0.35
    assert mastery == pytest.approx(0.5775)
    assert mastery < MASTERY_WEAKNESS_THRESHOLD

    result = recommend_next_concept(
        _actionable_knowledge(),
        _state(
            mastery={"foundation": mastery},
            outcomes=[
                _outcome("verify_foundation_one"),
                _outcome("verify_foundation_two"),
            ],
        ),
        reviewed_evidence_catalog=_evidence_catalog(),
    )

    assert result["concept_id"] == "next"
    assert result["evidence_status"] == "formal_evidence_available"
    assert result["remaining_formal_evidence_opportunities"] == 1


@pytest.mark.parametrize(
    "outcomes,misconceptions,expected_status",
    [
        (
            [_outcome("verify_foundation_one", "unresolved"), _outcome("verify_foundation_two", "unresolved")],
            [],
            "evidence_exhausted_review",
        ),
        (
            [_outcome("verify_foundation_one"), _outcome("verify_foundation_two")],
            ["foundation_error"],
            "unresolved_misconception",
        ),
        (
            [_outcome("verify_foundation_one", level="hint"), _outcome("verify_foundation_two")],
            [],
            "evidence_exhausted_review",
        ),
    ],
)
def test_exhausted_incorrect_misconception_or_assisted_evidence_remains_honest_review_action(
    outcomes, misconceptions, expected_status
):
    result = recommend_next_concept(
        _actionable_knowledge(),
        _state(mastery={"foundation": 0.5775}, outcomes=outcomes, misconceptions=misconceptions),
        reviewed_evidence_catalog=_evidence_catalog(),
    )

    assert result["concept_id"] == "foundation"
    assert result["actionability"] == "review_practice"
    assert result["evidence_status"] == expected_status
    assert result["remaining_formal_evidence_opportunities"] == 0


def test_practice_only_entry_does_not_create_formal_evidence_or_skip_available_action():
    result = recommend_next_concept(
        _actionable_knowledge(),
        _state(
            mastery={"foundation": 0.35},
            outcomes=[_outcome("verify_foundation_one")],
            practice_only=True,
        ),
        reviewed_evidence_catalog=_evidence_catalog(),
    )

    assert result["concept_id"] == "foundation"
    assert result["remaining_formal_evidence_opportunities"] == 2


def test_legacy_formal_template_id_without_outcome_fails_closed_to_review():
    state = _state(mastery={"foundation": 0.5775})
    state["learning_evidence"] = [
        {
            "evidence_eligible": True,
            "template_ids": ["verify_foundation_one", "verify_foundation_two"],
        }
    ]

    result = recommend_next_concept(
        _actionable_knowledge(), state, reviewed_evidence_catalog=_evidence_catalog()
    )

    assert result["concept_id"] == "foundation"
    assert result["evidence_status"] == "evidence_exhausted_review"
    assert result["actionability"] == "review_practice"


def test_zero_template_concept_is_neither_mastered_nor_skipped():
    knowledge = {"uncovered": _actionable_knowledge()["uncovered"]}
    result = recommend_next_concept(
        knowledge, _state(), reviewed_evidence_catalog=_evidence_catalog()
    )

    assert result["concept_id"] == "uncovered"
    assert result["actionability"] == "review_without_formal_evidence"
    assert result["evidence_status"] == "no_formal_template"


def test_evidence_aware_recommendation_is_deterministic_and_does_not_mutate_input():
    state = _state(
        mastery={"foundation": 0.5775},
        outcomes=[_outcome("verify_foundation_one"), _outcome("verify_foundation_two")],
    )
    original = copy.deepcopy(state)
    catalog = _evidence_catalog()

    first = recommend_next_concept(
        _actionable_knowledge(), state, reviewed_evidence_catalog=catalog
    )
    second = recommend_next_concept(
        _actionable_knowledge(), state, reviewed_evidence_catalog=catalog
    )

    assert first == second
    assert state == original
