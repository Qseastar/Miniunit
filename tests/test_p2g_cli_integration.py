"""CLI boundary tests; production scoring remains real except exit-code seam."""

import json
from copy import deepcopy
from pathlib import Path

from tools import verification_quality_gate as gate


ROOT = Path(__file__).resolve().parents[1]
P2F_IDS = {
    "verify_path_cost_accumulation_v1", "verify_search_node_state_distinction_v1",
    "verify_dfs_infinite_branch_risk_v1", "verify_search_algorithm_properties_v1",
    "verify_greedy_suboptimality_v1", "verify_astar_f_value_v1",
    "verify_consistency_edge_check_v1",
}


def _active_candidate():
    production = json.loads((ROOT / "data" / "diagnostic_templates.json").read_text(encoding="utf-8"))["templates"]
    from template_acceptance_cases import PRODUCTION_TEMPLATE_ACCEPTANCE_CASES
    templates = []
    acceptance = {}
    for item in production:
        if item["id"] in P2F_IDS:
            copy = deepcopy(item)
            original_id = copy["id"]
            copy["id"] = "synthetic_" + original_id
            copy["review_status"] = "candidate_draft"
            templates.append(copy)
            acceptance[copy["id"]] = deepcopy(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[original_id])
    return {
        "schema_version": 1,
        "candidate_batch_id": "search_algorithms_p2f_a",
        "candidate_status": "pending_human_review",
        "templates": templates,
        "acceptance_cases": acceptance,
    }


def _candidate_with_only_context(tmp_path):
    document = _active_candidate()
    case = document["acceptance_cases"]["synthetic_verify_search_algorithm_properties_v1"]
    case["source_refs"] = [case["source_refs"][0]]
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _write_iddfs_source_mutation(tmp_path, mutate):
    document = _active_candidate()
    refs = document["acceptance_cases"]["synthetic_verify_search_algorithm_properties_v1"]["source_refs"]
    mutate(refs)
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_cli_real_production_only_and_candidate_lint_reports_are_parseable(tmp_path):
    report = tmp_path / "report.json"
    markdown = tmp_path / "report.md"
    assert gate.main(["--production-only", "--json-report", str(report), "--markdown-report", str(markdown), "--strict"]) == gate.EXIT_OK
    assert '"active_candidate_count": 0' in report.read_text(encoding="utf-8")
    assert "Production templates: 28" in markdown.read_text(encoding="utf-8")
    assert gate.main(["--lint-candidate", "--strict"]) == gate.EXIT_OK


def test_cli_missing_input_and_report_write_failure_have_nonzero_stable_exit(tmp_path):
    assert gate.main(["--production", str(tmp_path / "missing.json")]) == gate.EXIT_INPUT_ERROR
    impossible = tmp_path / "missing-parent" / "report.json"
    assert gate.main(["--json-report", str(impossible)]) == gate.EXIT_INTERNAL_ERROR


def test_cli_strict_warning_escalates_without_mocking_production_scoring(monkeypatch):
    real = gate.run_quality_gate

    def warning_report(**kwargs):
        report = real(**kwargs)
        report["warnings"] = ["test warning"]
        return report

    monkeypatch.setattr(gate, "run_quality_gate", warning_report)
    assert gate.main(["--strict"]) == gate.EXIT_STRICT_WARNING


def test_cli_context_only_without_primary_evidence_fails_with_stable_report_code(tmp_path):
    report = tmp_path / "report.json"
    candidate = _candidate_with_only_context(tmp_path)
    assert gate.main(["--candidates", str(candidate), "--json-report", str(report), "--strict"]) == gate.EXIT_QUALITY_FAILURE
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "fail"
    assert any("SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE" in item for item in payload["failures"])


def test_cli_source_role_variants_fail_closed_with_parseable_reports(tmp_path):
    mutations = [
        (
            "unrelated_context_only",
            lambda refs: refs.__setitem__(slice(None), [{
                "chunk_id": "lec2_bfs_properties", "source_file": "ai_lec2_uninformed_search.pdf",
                "page_start": 35, "page_end": 35, "context_only": True,
            }]),
            "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE",
        ),
        (
            "context_plus_unrelated_evidence",
            lambda refs: refs[1].update({"chunk_id": "lec2_bfs_layer_order", "page_start": 31, "page_end": 34}),
            "SOURCE_PRIMARY_EVIDENCE_ANCHOR_MISSING",
        ),
        (
            "malformed_context_type",
            lambda refs: refs[0].__setitem__("context_only", "true"),
            "SOURCE_CONTEXT_ONLY_TYPE_INVALID",
        ),
        ("missing_refs", lambda refs: refs.clear(), "SOURCE_REFS_MISSING"),
    ]
    for name, mutate, expected in mutations:
        report = tmp_path / f"{name}.json"
        candidate = _write_iddfs_source_mutation(tmp_path, mutate)
        assert gate.main(["--candidates", str(candidate), "--json-report", str(report), "--lint-candidate", "--strict"]) == gate.EXIT_QUALITY_FAILURE
        payload = json.loads(report.read_text(encoding="utf-8"))
        assert payload["overall_status"] == "fail"
        assert any(expected in item for item in payload["failures"])


def test_cli_promotion_readiness_never_auto_approves_or_promotes(tmp_path):
    report = tmp_path / "readiness.json"
    assert gate.main(["--promotion-readiness", "--json-report", str(report), "--strict"]) == gate.EXIT_OK
    readiness = json.loads(report.read_text(encoding="utf-8"))["promotion_readiness"]
    assert readiness == {
        "source_gate_ready": True,
        "owner_approval_pending": True,
        "promotion_pending": True,
        "automatic_promotion": False,
    }
