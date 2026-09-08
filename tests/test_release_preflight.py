import json
from pathlib import Path

from tools import release_preflight


ROOT = Path(__file__).resolve().parents[1]


def _env(**overrides):
    values = {"INTROAI_PILOT_MODE": "", "DEEPSEEK_API_KEY": ""}
    values.update(overrides)
    return values


def test_release_preflight_is_core_ready_without_provider_or_material(tmp_path):
    report = release_preflight.run_release_preflight(
        root=ROOT,
        env=_env(),
        port=18501,
        db_path=tmp_path / "learner.sqlite3",
    )
    assert report["network"] == "disabled"
    assert report["release_invariants"] == {
        "production_templates": 28,
        "active_candidates": 0,
        "blocked_slots": 1,
        "concepts": 26,
        "direct_primary_formal_coverage": 21,
        "source_manifest_files": 8,
        "sqlite_schema": 3,
    }
    assert report["summary"]["critical_fail"] == 0
    statuses = {item["check_id"]: item["status"] for item in report["checks"]}
    assert statuses["release_verification_quality_gate"] == "PASS"
    assert statuses["release_production_id_uniqueness"] == "PASS"
    assert statuses["release_blocked_slot_contract"] == "PASS"
    assert statuses["release_p5b_promotion_visibility"] == "PASS"
    assert statuses["release_primary_formal_coverage"] == "PASS"
    assert statuses["release_source_manifest_count"] == "PASS"
    assert statuses["release_qa_initialization"] == "PASS"
    assert statuses["release_reviewed_diagnostic_initialization"] == "PASS"
    assert statuses["deepseek_api_key_present"] == "WARN"
    assert statuses["citation_preview_readiness"] == "WARN"
    assert not (tmp_path / "learner.sqlite3").exists()


def test_release_preflight_never_emits_provider_secret(tmp_path):
    secret = "release-preflight-test-secret"
    report = release_preflight.run_release_preflight(
        root=ROOT,
        env=_env(DEEPSEEK_API_KEY=secret),
        port=18502,
        db_path=tmp_path / "state.sqlite3",
    )
    assert secret not in json.dumps(report, ensure_ascii=False)


def test_release_preflight_marks_missing_cloudflared_optional(monkeypatch, tmp_path):
    monkeypatch.setattr(release_preflight.shutil, "which", lambda _: None)
    report = release_preflight.run_release_preflight(
        root=ROOT,
        env=_env(),
        port=18503,
        db_path=tmp_path / "state.sqlite3",
    )
    check = next(item for item in report["checks"] if item["check_id"] == "optional_cloudflared")
    assert check["status"] == "WARN"
    assert check["critical"] is False


def test_release_preflight_fails_closed_on_invariant_drift(monkeypatch, tmp_path):
    real = release_preflight.load_knowledge_points

    def drifted(path):
        report = real(path)
        report["knowledge_points"] = report["knowledge_points"][:-1]
        return report

    monkeypatch.setattr(release_preflight, "load_knowledge_points", drifted)
    report = release_preflight.run_release_preflight(
        root=ROOT,
        env=_env(),
        port=18504,
        db_path=tmp_path / "state.sqlite3",
    )
    check = next(item for item in report["checks"] if item["check_id"] == "release_concept_count")
    assert check["status"] == "FAIL"
    assert report["summary"]["critical_fail"] >= 1
