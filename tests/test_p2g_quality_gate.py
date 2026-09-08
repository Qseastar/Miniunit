"""High-value offline regression tests for the P2g verification quality gate."""

from __future__ import annotations

from copy import deepcopy
from itertools import chain, combinations, permutations
import json
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import DiagnosticTemplateError, validate_diagnostic_templates
from introai_tutor.template_selection import TemplateSelectionService, load_diagnostic_templates
from introai_tutor.diagnostic_handoff import DiagnosticHandoffError, DiagnosticHandoffService
from introai_tutor.verification_diagnostics import (
    VerificationDiagnosticError, VerificationDiagnosticService, score_verification_answer,
)
from tools.generate_template_review_packet import build_review_packet, main as generate_review_packet, markdown_packet
from tools.generate_verification_reports import build_reports
from tools.test_inventory import build_inventory
from tools.verification_benchmark import BenchmarkInputError, build_manifest, load_candidate_document
from tools.verification_quality_gate import markdown_report, run_quality_gate
from template_acceptance_cases import PRODUCTION_TEMPLATE_ACCEPTANCE_CASES


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "data" / "diagnostic_templates.json"
CANDIDATES = ROOT / "data" / "candidate_templates" / "search_algorithms_p2f_candidates.json"
P2F_IDS = {
    "verify_path_cost_accumulation_v1", "verify_search_node_state_distinction_v1",
    "verify_dfs_infinite_branch_risk_v1", "verify_search_algorithm_properties_v1",
    "verify_greedy_suboptimality_v1", "verify_astar_f_value_v1",
    "verify_consistency_edge_check_v1",
}
EXPECTED_PRODUCTION_TEMPLATE_COUNT = 28


def test_ci_workflow_installs_pytest_and_never_requires_or_downloads_local_materials():
    workflow = (ROOT / ".github" / "workflows" / "verification-quality.yml").read_text(encoding="utf-8")
    acceptance_test = (ROOT / "tests" / "test_template_acceptance.py").read_text(encoding="utf-8")
    assert "python -m pip install -r requirements.txt pytest" in workflow
    assert "local_materials" not in workflow
    assert "curl" not in workflow
    assert "wget" not in workflow
    assert "continue-on-error" not in workflow
    assert "local_materials" not in acceptance_test
    assert ".is_file()" not in acceptance_test


def _active_candidate_fixture():
    production = json.loads(PRODUCTION.read_text(encoding="utf-8"))["templates"]
    templates = []
    for item in production:
        if item["id"] in P2F_IDS:
            candidate = deepcopy(item)
            candidate["review_status"] = "candidate_draft"
            templates.append(candidate)
    return {
        "schema_version": 1,
        "candidate_batch_id": "search_algorithms_p2f_a",
        "candidate_status": "pending_human_review",
        "templates": templates,
        "acceptance_cases": {key: deepcopy(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[key]) for key in P2F_IDS},
    }


def _templates() -> dict[str, dict]:
    result = {}
    for path in (PRODUCTION, CANDIDATES):
        for item in json.loads(path.read_text(encoding="utf-8"))["templates"]:
            result[item["id"]] = item
    return result


def _entries():
    manifest = build_manifest(root=ROOT)
    return [*manifest["production"], *manifest["candidates"]]


def test_manifest_is_derived_complete_and_candidate_isolated():
    manifest = build_manifest(root=ROOT)
    assert len(manifest["production"]) == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert len(manifest["candidates"]) == 0
    assert len(manifest["blocked_slots"]) == 1
    assert {item["review_status"] for item in manifest["production"]} == {"human_verified"}
    assert not manifest["candidates"]
    assert not ({item["template_id"] for item in manifest["production"]} & {item["template_id"] for item in manifest["candidates"]})


@pytest.mark.parametrize("entry", [item for item in _entries() if item["scorer"] == "single_choice_v1"], ids=lambda item: item["template_id"])
def test_every_single_choice_legal_answer_is_exhaustive_and_stable(entry):
    template = _templates()[entry["template_id"]]
    before_template = deepcopy(template)
    expected = template["expected_answer"]["choice_id"]
    for choice in template["choices"]:
        result = score_verification_answer(template=template, answer=choice["id"])
        assert result["passed"] is (choice["id"] == expected)
        assert result["score"] == (1.0 if choice["id"] == expected else 0.0)
    for _ in range(3):
        assert score_verification_answer(template=template, answer=expected) == score_verification_answer(template=template, answer=expected)
    for malformed in (None, "", " ", [], (), {}, True, 1, 1.0, "not_a_choice_id"):
        with pytest.raises(VerificationDiagnosticError):
            score_verification_answer(template=template, answer=malformed)
    assert template == before_template


@pytest.mark.parametrize("entry", [item for item in _entries() if item["scorer"] == "multiple_choice_v1"], ids=lambda item: item["template_id"])
def test_every_multiple_choice_subset_has_exactly_one_passing_set(entry):
    template = _templates()[entry["template_id"]]
    before_template = deepcopy(template)
    ids = [choice["id"] for choice in template["choices"]]
    expected = set(template["expected_answer"]["choice_ids"])
    passed_subsets = []
    for size in range(len(ids) + 1):
        for subset in combinations(ids, size):
            if not subset:
                with pytest.raises(VerificationDiagnosticError):
                    score_verification_answer(template=template, answer=[])
                continue
            result = score_verification_answer(template=template, answer=list(subset))
            if result["passed"]:
                passed_subsets.append(set(subset))
    assert passed_subsets == [expected]
    for ordered in permutations(template["expected_answer"]["choice_ids"]):
        assert score_verification_answer(template=template, answer=list(ordered))["passed"] is True
    for malformed in (None, "", (), {}, True, ["unknown"], [ids[0], ids[0]]):
        with pytest.raises(VerificationDiagnosticError):
            score_verification_answer(template=template, answer=malformed)
    assert template == before_template


def _synthetic_template(scorer: str, expected_answer: dict, choices: list[dict] | None = None) -> dict:
    return {
        "id": "synthetic", "deterministic_scorer": scorer, "choices": choices or [],
        "expected_answer": expected_answer, "teaching_support": {"hint": "h", "explanation": "e"}, "misconception_rules": [],
    }


@pytest.mark.parametrize("answer,passed", [(3, True), (" 3.0 ", True), (3.1, True), (3.1001, False), (-3, False), (True, None), ("3+0", None), ("1e3", None), (float("inf"), None), (float("nan"), None)])
def test_numeric_scorer_contract_matrix(answer, passed):
    template = _synthetic_template("numeric_answer_v1", {"value": 3, "absolute_tolerance": 0.1})
    if passed is None:
        with pytest.raises(VerificationDiagnosticError):
            score_verification_answer(template=template, answer=answer)
    else:
        assert score_verification_answer(template=template, answer=answer)["passed"] is passed


@pytest.mark.parametrize("expected", [{"value": True}, {"value": float("nan")}, {"value": 3, "absolute_tolerance": -1}, {"value": 3, "absolute_tolerance": float("inf")}])
def test_numeric_invalid_configuration_fails_closed(expected):
    with pytest.raises(VerificationDiagnosticError):
        score_verification_answer(template=_synthetic_template("numeric_answer_v1", expected), answer=3)


def test_ordering_scorer_contract_matrix():
    choices = [{"id": item, "text": item} for item in ("a", "b", "c")]
    template = _synthetic_template("ordering_v1", {"ordered_choice_ids": ["a", "b", "c"]}, choices)
    assert score_verification_answer(template=template, answer=["a", "b", "c"])["passed"] is True
    for answer in (["b", "a", "c"], ["c", "b", "a"], ["b", "c", "a"], ["a", "b"], ["a", "b", "c", "x"]):
        if "x" in answer:
            with pytest.raises(VerificationDiagnosticError):
                score_verification_answer(template=template, answer=answer)
        else:
            assert score_verification_answer(template=template, answer=answer)["passed"] is False
    for malformed in (None, "abc", (), {}, True, ["a", "a", "c"]):
        with pytest.raises(VerificationDiagnosticError):
            score_verification_answer(template=template, answer=malformed)


def test_quality_gate_and_review_packet_are_stable_and_non_sensitive(tmp_path):
    first = run_quality_gate(root=ROOT)
    second = run_quality_gate(root=ROOT)
    assert first == second
    assert first["overall_status"] == "pass"
    assert "API" not in json.dumps(first, ensure_ascii=False)
    assert "Authorization" not in markdown_report(first)
    packet = build_review_packet(root=ROOT)
    assert len(packet["production"]) == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert len(packet["candidates"]) == 0
    assert len(packet["blocked_slots"]) == 1
    assert markdown_packet(packet) == markdown_packet(build_review_packet(root=ROOT))


def test_review_packet_generator_has_no_trailing_whitespace_and_preserves_review_state(tmp_path):
    """Exercise the CLI writer so generated packet formatting cannot regress."""
    markdown = tmp_path / "review_packet.md"
    packet_json = tmp_path / "review_packet.json"
    source_before = {
        path: path.read_bytes()
        for path in (PRODUCTION, CANDIDATES)
    }
    arguments = [
        "--production", str(PRODUCTION),
        "--candidates", str(CANDIDATES),
        "--chunks", str(ROOT / "data" / "course_chunks.json"),
        "--markdown-output", str(markdown),
        "--json-output", str(packet_json),
    ]
    assert generate_review_packet(arguments) == 0
    first_markdown = markdown.read_text(encoding="utf-8")
    first_json = packet_json.read_text(encoding="utf-8")
    assert all(not line.endswith((" ", "\t")) for line in first_markdown.splitlines())
    owner_lines = [line for line in first_markdown.splitlines() if line.startswith("**Owner decision:**")]
    assert owner_lines == ["**Owner decision:**"] * EXPECTED_PRODUCTION_TEMPLATE_COUNT
    packet = json.loads(first_json)
    assert (len(packet["production"]), len(packet["candidates"]), len(packet["blocked_slots"])) == (EXPECTED_PRODUCTION_TEMPLATE_COUNT, 0, 1)
    assert {entry["owner_decision"] for entry in [*packet["production"], *packet["candidates"]]} == {""}
    assert source_before == {path: path.read_bytes() for path in source_before}
    assert generate_review_packet(arguments) == 0
    assert markdown.read_text(encoding="utf-8") == first_markdown
    assert packet_json.read_text(encoding="utf-8") == first_json


def test_generated_review_packet_snapshot_has_no_trailing_whitespace():
    snapshot = ROOT / "docs" / "generated" / "search_algorithms_template_review_packet.md"
    assert all(not line.endswith((" ", "\t")) for line in snapshot.read_text(encoding="utf-8").splitlines())


def test_candidate_loader_rejects_invalid_input_and_production_collision(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(BenchmarkInputError):
        load_candidate_document(invalid, root=ROOT)
    data = _active_candidate_fixture()
    data["templates"][0]["id"] = "verify_bfs_frontier_choice_v1"
    data["acceptance_cases"] = {data["templates"][0]["id"]: data["acceptance_cases"]["verify_path_cost_accumulation_v1"], **{key: value for key, value in data["acceptance_cases"].items() if key != "verify_path_cost_accumulation_v1"}}
    collision = tmp_path / "collision.json"
    collision.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BenchmarkInputError):
        build_manifest(root=ROOT, candidate_path=collision)


@pytest.mark.parametrize("mutation", [
    ("id", ""), ("concept_ids", []), ("deterministic_scorer", "unknown"),
    ("question_type", "unknown"), ("choices", []), ("expected_answer", {}),
    ("review_status", "candidate_draft"), ("eligible_intents", []),
])
def test_production_validator_rejects_high_value_template_mutations(mutation):
    key, value = mutation
    document = json.loads(PRODUCTION.read_text(encoding="utf-8"))
    document["templates"][0][key] = deepcopy(value)
    concepts = {item["id"] for item in load_knowledge_points(ROOT / "data" / "knowledge_points.json")["knowledge_points"]}
    with pytest.raises(DiagnosticTemplateError):
        validate_diagnostic_templates(document, valid_concept_ids=concepts)


def _production_service_inputs():
    concepts = {item["id"] for item in load_knowledge_points(ROOT / "data" / "knowledge_points.json")["knowledge_points"]}
    document = load_diagnostic_templates(PRODUCTION, valid_concept_ids=concepts)
    return concepts, document


@pytest.mark.parametrize("entry", build_manifest(root=ROOT)["production"], ids=lambda item: item["template_id"])
def test_selector_intent_matrix_is_primary_topic_only_and_deterministic(entry):
    concepts, document = _production_service_inputs()
    selector = TemplateSelectionService(templates_data=document, valid_concept_ids=concepts)
    for intent in entry["eligible_intents"]:
        selected = selector.select(concept_ids=[entry["primary_concept"]], intent=intent)
        assert entry["template_id"] in {item["id"] for item in selected}
        assert selected == selector.select(concept_ids=[entry["primary_concept"]], intent=intent)
    for intent in entry["explicit_negative_intents"]:
        selected = selector.select(concept_ids=[entry["primary_concept"]], intent=intent)
        assert entry["template_id"] not in {item["id"] for item in selected}
    for supporting in entry["supporting_topics"]:
        selected = selector.select(concept_ids=[supporting], intent=entry["eligible_intents"][0])
        assert entry["template_id"] not in {item["id"] for item in selected}
    with pytest.raises(DiagnosticTemplateError):
        selector.select(concept_ids=["unknown_concept"], intent=entry["eligible_intents"][0])


@pytest.mark.parametrize("entry", build_manifest(root=ROOT)["production"], ids=lambda item: item["template_id"])
def test_handoff_matrix_uses_one_reviewed_default_per_primary_topic(entry):
    concepts, document = _production_service_inputs()
    selector = TemplateSelectionService(templates_data=document, valid_concept_ids=concepts)
    handoff = DiagnosticHandoffService(template_selection_service=selector)
    plan = handoff.plan(topic_ids=[entry["primary_concept"]], intent=entry["eligible_intents"][0])
    # A handoff deliberately chooses one stable, reviewed default per direct
    # primary concept.  Individual production templates remain selectable by
    # the lower-level selector, but need not all appear in the default plan.
    assert len(plan["template_ids"]) == 1
    selected_by_id = {item["id"]: item for item in document["templates"]}
    selected = selected_by_id[plan["template_ids"][0]]
    assert selected["concept_ids"][0] == entry["primary_concept"]
    assert entry["template_id"] in {
        item["id"]
        for item in selector.select(
            concept_ids=[entry["primary_concept"]],
            intent=entry["eligible_intents"][0],
        )
    }
    assert plan["planning_source"] == "explicit_topic_ids"
    unavailable = handoff.plan(topic_ids=[entry["primary_concept"]], intent=entry["explicit_negative_intents"][0])
    assert all(
        selected_by_id[template_id]["review_status"] == "human_verified"
        for template_id in unavailable["template_ids"]
    )


@pytest.mark.parametrize("entry", build_manifest(root=ROOT)["production"], ids=lambda item: item["template_id"])
def test_production_service_replay_hint_reveal_and_tamper_fail_closed(entry):
    template = _templates()[entry["template_id"]]
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template["id"]])
    before = deepcopy(started["session"])
    completed = service.submit(session=started["session"], answer=entry["known_correct"], submitted_template_id=template["id"])
    assert completed["status"] == "completed"
    assert completed["summary"]["evidence_eligible"] is True
    assert completed["summary"]["concept_observations"][entry["primary_concept"]] == [1.0]
    assert started["session"] == before

    retry = service.submit(session=started["session"], answer=entry["known_wrong"][0], submitted_template_id=template["id"])
    assert retry["session"]["interaction_state"] == "retry_ready"
    hinted = service.choose_hint_retry(session=retry["session"], template_id=template["id"])
    assisted_done = service.submit(session=hinted["session"], answer=entry["known_correct"], submitted_template_id=template["id"])
    assert assisted_done["summary"]["observation_records"][-1]["assisted"] is True

    reveal = service.request_reveal(session=started["session"], template_id=template["id"])
    assert reveal["session"]["interaction_state"] == "revealing"
    acknowledged = service.acknowledge_reveal(session=reveal["session"], template_id=template["id"])
    assert acknowledged["summary"].get("no_observation_reason") == "all_revealed"

    tampered = deepcopy(completed["session"])
    tampered["history"][0]["score"] = 0.0
    # Completed sessions are not accepted for a second submit; replay through
    # an in-progress sibling catches the same deterministic history mutation.
    in_progress = deepcopy(retry["session"])
    in_progress["history"][0]["score"] = 1.0
    with pytest.raises(VerificationDiagnosticError):
        service.current_question(session=in_progress)


def test_candidate_templates_cannot_start_production_verification_service():
    candidates = _active_candidate_fixture()["templates"]
    with pytest.raises(VerificationDiagnosticError):
        VerificationDiagnosticService(templates=[candidates[0]])


def test_workflow_and_ci_configuration_are_offline_and_no_secret_declaration():
    workflow = (ROOT / ".github" / "workflows" / "verification-quality.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "quality_gate.sh").read_text(encoding="utf-8")
    assert "push:" in workflow and "pull_request:" in workflow and "workflow_dispatch:" in workflow
    assert "timeout-minutes" in workflow and ".env" not in workflow and "secrets." not in workflow
    assert "set -euo pipefail" in script and ".env" not in script and "curl" not in script


def test_source_and_capability_reports_cover_exact_bank_inventory():
    trace, coverage = build_reports(root=ROOT)
    assert trace["production_template_count"] == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert trace["candidate_template_count"] == 0
    assert trace["blocked_slot_count"] == 1
    assert len(trace["entries"]) == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert len(coverage["concepts"]) == 26
    assert len({item["concept_id"] for item in coverage["concepts"]}) == 26
    assert {item["template_id"] for item in trace["entries"]} == {item["template_id"] for item in _entries()}


def test_test_inventory_collects_real_suite_without_running_test_bodies():
    inventory = build_inventory(root=ROOT)
    assert inventory["baseline_before_p2g"] == 971
    assert inventory["collected_test_count"] >= 971
    assert inventory["test_file_count"] >= 1
