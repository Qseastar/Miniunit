"""Promotion audit for the owner-approved P2f batch."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import TemplateSelectionService, load_diagnostic_templates
from introai_tutor.verification_diagnostics import VerificationDiagnosticError, VerificationDiagnosticService, score_verification_answer
from template_acceptance_cases import PRODUCTION_TEMPLATE_ACCEPTANCE_CASES


ROOT = Path(__file__).resolve().parents[1]
P2F_PATH = ROOT / "data/candidate_templates/search_algorithms_p2f_candidates.json"
PRODUCTION_PATH = ROOT / "data/diagnostic_templates.json"
P2F_TEMPLATE_IDS = {
    "verify_path_cost_accumulation_v1",
    "verify_search_node_state_distinction_v1",
    "verify_dfs_infinite_branch_risk_v1",
    "verify_search_algorithm_properties_v1",
    "verify_greedy_suboptimality_v1",
    "verify_astar_f_value_v1",
    "verify_consistency_edge_check_v1",
}
P2F_SEMANTIC_HASHES = {
    "verify_path_cost_accumulation_v1": "8260c5e99ffce3ef2de78ea9b4056b2723f7bb52ec00d8cbfe5e11545887b6cd",
    "verify_search_node_state_distinction_v1": "d16fa5f06483af6fc28089a25dc320c095385656d86bcbb537579e9778f3c0bd",
    "verify_dfs_infinite_branch_risk_v1": "4f367fecbca06d11440b7319c6fe2e1bc150225a042f3337410fa1896cae99c2",
    "verify_search_algorithm_properties_v1": "4da54ca35d69e0a2fffba5df45f6cf06d0ab437adc3bb634ba0339f50d068d34",
    "verify_greedy_suboptimality_v1": "92dccc357e9c660d87fad2f514e88cb5228bde5afa5d2f9d40c9bbcf883d012a",
    "verify_astar_f_value_v1": "e0f2edbd314394a452bd1ba9bda191b5b4caa321a6ed9113559405aed8c11d62",
    "verify_consistency_edge_check_v1": "cda1b9727e8e5b67d0195b01c49c1b12acddedfd66e1f2bbccf5f8faf09e2d4d",
}


def _concept_ids():
    return {x["id"] for x in load_knowledge_points(ROOT / "data/knowledge_points.json")["knowledge_points"]}


def _production():
    return {
        x["id"]: x
        for x in load_diagnostic_templates(PRODUCTION_PATH, valid_concept_ids=_concept_ids())["templates"]
    }


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_p2f_candidate_staging_is_promoted_and_empty():
    assert json.loads(P2F_PATH.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "candidate_batch_id": "search_algorithms_p2f_a",
        "candidate_status": "promoted_to_production",
        "templates": [],
        "acceptance_cases": {},
    }


def test_all_seven_promoted_templates_preserve_semantic_payload_hashes():
    production = _production()
    assert len(production) == 28
    assert P2F_TEMPLATE_IDS <= set(production)
    assert len(set(production)) == 28
    for template_id in P2F_TEMPLATE_IDS:
        semantic = deepcopy(production[template_id])
        assert semantic.pop("review_status") == "human_verified"
        assert _hash(semantic) == P2F_SEMANTIC_HASHES[template_id]


@pytest.mark.parametrize("template_id", sorted(P2F_TEMPLATE_IDS))
def test_promoted_template_acceptance_and_scorer_contracts(template_id):
    template = _production()[template_id]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]
    assert template["concept_ids"] == [case["primary_concept_id"]]
    assert template["question_type"] == "single_choice"
    assert template["deterministic_scorer"] == "single_choice_v1"
    assert template["review_status"] == "human_verified"
    positive = score_verification_answer(template=template, answer=case["correct_answer"])
    negative = score_verification_answer(template=template, answer=case["wrong_answer"])
    assert (positive["score"], positive["passed"]) == (1.0, True)
    assert (negative["score"], negative["passed"]) == (0.0, False)
    with pytest.raises(VerificationDiagnosticError):
        score_verification_answer(template=template, answer=case["malformed_answer"])


def test_p2f_iddfs_source_roles_remain_context_plus_primary_evidence():
    refs = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES["verify_search_algorithm_properties_v1"]["source_refs"]
    assert any(ref.get("context_only") is True and ref["page_start"] == 53 for ref in refs)
    assert any(ref.get("primary_evidence") is True and ref["page_start"] == 58 for ref in refs)


def test_p2f_templates_are_selector_and_service_visible_after_promotion():
    production = _production()
    selector = TemplateSelectionService(
        templates_data={"schema_version": 1, "templates": list(production.values())},
        valid_concept_ids=_concept_ids(),
    )
    selected = {
        item["id"]
        for template_id in P2F_TEMPLATE_IDS
        for intent in production[template_id]["eligible_intents"]
        for item in selector.select(concept_ids=production[template_id]["concept_ids"], intent=intent)
    }
    assert P2F_TEMPLATE_IDS <= selected
    service = VerificationDiagnosticService(templates=[production[x] for x in sorted(P2F_TEMPLATE_IDS)])
    for template_id in P2F_TEMPLATE_IDS:
        started = service.start(template_ids=[template_id])
        assert started["question"]["template_id"] == template_id
