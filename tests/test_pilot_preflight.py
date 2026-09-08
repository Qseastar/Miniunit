from pathlib import Path
import socket
from types import SimpleNamespace
import json
import errno

import pytest

from tools import pilot_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]


def _free_port():
    # Socket creation is restricted in the managed test sandbox.  The
    # production check itself handles that as a visible WARN.
    return 18503


def _env(**overrides):
    values = {"INTROAI_PILOT_MODE": "", "DEEPSEEK_API_KEY": "unit-test-secret"}
    values.update(overrides)
    return values


def test_preflight_passes_offline_with_explicit_isolated_database(tmp_path):
    report = preflight.run_preflight(
        root=ROOT,
        env=_env(),
        port=_free_port(),
        db_path=tmp_path / "learner.sqlite3",
    )
    assert report["network"] == "disabled"
    assert report["summary"]["fail"] == 0
    assert {item["check_id"] for item in report["checks"]} >= {
        "production_template_count", "active_candidate_count", "blocked_slot_count",
        "concept_count", "focus_role_count", "sqlite_schema_initialization",
    }
    assert all("unit-test-secret" not in item["message"] for item in report["checks"])
    assert not (tmp_path / "learner.sqlite3").exists()


def test_optional_citation_preview_readiness_does_not_block_when_unconfigured(tmp_path):
    checks = []
    preflight._check_citation_preview(checks, ROOT, _env())
    assert checks[0].check_id == "citation_preview_readiness"
    assert checks[0].status == "WARN"
    assert checks[0].critical is False


def test_optional_citation_preview_readiness_can_pass_without_exposing_root(monkeypatch, tmp_path):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: "/usr/bin/pdftoppm")
    monkeypatch.setattr(
        preflight,
        "verify_local_course_materials",
        lambda **_: {"status": "pass", "verified_materials": [], "missing_materials": []},
    )
    checks = []
    preflight._check_citation_preview(
        checks,
        ROOT,
        _env(INTROAI_COURSE_MATERIALS_DIR=str(tmp_path)),
    )
    assert checks[0].status == "PASS"
    assert str(tmp_path) not in checks[0].message


def test_missing_api_key_is_explicit_warn_without_secret_output(tmp_path):
    report = preflight.run_preflight(
        root=ROOT,
        env=_env(DEEPSEEK_API_KEY=""),
        port=_free_port(),
        db_path=tmp_path / "learner.sqlite3",
    )
    check = next(item for item in report["checks"] if item["check_id"] == "deepseek_api_key_present")
    assert check["status"] == "WARN"
    assert "key" in check["message"].casefold()


@pytest.mark.parametrize(
    ("env", "host", "expected_status"),
    [
        (_env(), "127.0.0.1", "PASS"),
        (_env(), "0.0.0.0", "FAIL"),
        (_env(INTROAI_PILOT_MODE="1"), "127.0.0.1", "WARN"),
        (_env(INTROAI_PILOT_MODE="1"), "0.0.0.0", "FAIL"),
        (_env(INTROAI_PILOT_MODE="1", INTROAI_PILOT_ACCESS_CODE="pilot-access-2026"), "0.0.0.0", "PASS"),
    ],
)
def test_access_boundary_is_explicit_for_local_and_non_loopback_hosts(tmp_path, env, host, expected_status):
    report = preflight.run_preflight(
        root=ROOT,
        env=env,
        host=host,
        port=_free_port(),
        db_path=tmp_path / "state.sqlite3",
    )
    check = next(item for item in report["checks"] if item["check_id"] == "pilot_access_boundary")
    assert check["status"] == expected_status
    assert "pilot-access-2026" not in json.dumps(report, ensure_ascii=False)


def test_invalid_pilot_access_code_fails_closed_even_on_loopback(tmp_path):
    report = preflight.run_preflight(
        root=ROOT,
        env=_env(INTROAI_PILOT_MODE="1", INTROAI_PILOT_ACCESS_CODE="short"),
        host="127.0.0.1",
        port=_free_port(),
        db_path=tmp_path / "state.sqlite3",
    )
    statuses = {
        item["check_id"]: item["status"]
        for item in report["checks"]
        if item["check_id"] in {"pilot_access_code_config", "pilot_access_boundary"}
    }
    assert statuses == {"pilot_access_code_config": "FAIL", "pilot_access_boundary": "FAIL"}


def _fake_cloudflared(tmp_path, *, executable=True):
    binary = tmp_path / "cloudflared"
    binary.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755 if executable else 0o644)
    return binary


def test_remote_preflight_requires_loopback_pilot_code_and_cloudflared(tmp_path):
    code = "remote-test-code-2026"
    report = preflight.run_preflight(
        root=ROOT,
        env=_env(INTROAI_PILOT_MODE="1", INTROAI_PILOT_ACCESS_CODE=code),
        host="127.0.0.1",
        port=_free_port(),
        db_path=tmp_path / "state.sqlite3",
        remote=True,
        tunnel_provider="cloudflared",
        tunnel_binary=_fake_cloudflared(tmp_path),
    )
    statuses = {item["check_id"]: item["status"] for item in report["checks"]}
    assert statuses["pilot_mode_config"] == "PASS"
    assert statuses["remote_tunnel_provider"] == "PASS"
    assert statuses["remote_tunnel_binary"] == "PASS"
    assert statuses["remote_streamlit_host"] == "PASS"
    assert statuses["remote_pilot_mode"] == "PASS"
    assert statuses["remote_access_code"] == "PASS"
    assert code not in json.dumps(report, ensure_ascii=False)


def test_remote_preflight_rejects_invalid_access_code_without_exposing_it(tmp_path):
    invalid = "short"
    report = preflight.run_preflight(
        root=ROOT,
        env=_env(INTROAI_PILOT_MODE="1", INTROAI_PILOT_ACCESS_CODE=invalid),
        host="127.0.0.1",
        port=_free_port(),
        db_path=tmp_path / "state.sqlite3",
        remote=True,
        tunnel_provider="cloudflared",
        tunnel_binary=_fake_cloudflared(tmp_path),
    )
    check = next(item for item in report["checks"] if item["check_id"] == "remote_access_code")
    assert check["status"] == "FAIL"
    assert invalid not in json.dumps(report, ensure_ascii=False)


@pytest.mark.parametrize(
    ("host", "env_overrides", "binary_kind", "failed_check"),
    [
        ("127.0.0.1", {}, "missing", "remote_access_code"),
        ("localhost", {"INTROAI_PILOT_ACCESS_CODE": "remote-test-code-2026"}, "executable", "remote_streamlit_host"),
        ("127.0.0.1", {"INTROAI_PILOT_ACCESS_CODE": "remote-test-code-2026"}, "missing", "remote_tunnel_binary"),
        ("127.0.0.1", {"INTROAI_PILOT_ACCESS_CODE": "remote-test-code-2026"}, "non_executable", "remote_tunnel_binary"),
    ],
)
def test_remote_preflight_fails_closed_for_each_remote_boundary(
    tmp_path, host, env_overrides, binary_kind, failed_check
):
    binary = (
        tmp_path / "missing-cloudflared"
        if binary_kind == "missing"
        else _fake_cloudflared(tmp_path, executable=binary_kind == "executable")
    )
    report = preflight.run_preflight(
        root=ROOT,
        env=_env(INTROAI_PILOT_MODE="1", **env_overrides),
        host=host,
        port=_free_port(),
        db_path=tmp_path / "state.sqlite3",
        remote=True,
        tunnel_provider="cloudflared",
        tunnel_binary=binary,
    )
    check = next(item for item in report["checks"] if item["check_id"] == failed_check)
    assert check["status"] == "FAIL"
    assert report["summary"]["fail"] >= 1


def test_tunnel_provider_requires_remote_mode_at_cli_boundary():
    with pytest.raises(SystemExit) as error:
        preflight.main(["--tunnel-provider", "cloudflared"])
    assert error.value.code == 2


def test_invalid_pilot_mode_is_critical_failure(tmp_path):
    report = preflight.run_preflight(
        root=ROOT,
        env=_env(INTROAI_PILOT_MODE="maybe"),
        port=_free_port(),
        db_path=tmp_path / "learner.sqlite3",
    )
    check = next(item for item in report["checks"] if item["check_id"] == "pilot_mode_config")
    assert check["status"] == "FAIL"
    assert report["summary"]["critical_fail"] >= 1


def test_preflight_detects_occupied_port(tmp_path):
    class OccupiedSocket:
        def __enter__(self):
            raise OSError(errno.EADDRINUSE, "occupied")
        def __exit__(self, *_):
            return False

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(preflight.socket, "socket", lambda *args, **kwargs: OccupiedSocket())
    try:
        checks = []
        preflight._check_port(checks, 18503)
    finally:
        monkeypatch.undo()
    assert checks[0].status == "FAIL"


def test_preflight_detects_non_writable_sqlite_parent(tmp_path):
    not_directory = tmp_path / "not-a-directory"
    not_directory.write_text("x", encoding="utf-8")
    checks = []
    preflight._check_sqlite(checks, not_directory / "state.sqlite3")
    assert next(item for item in checks if item.check_id == "sqlite_directory").status == "FAIL"


def test_required_file_failure_is_explicit(tmp_path):
    checks = []
    preflight._check_required_files(checks, tmp_path)
    assert checks[0].check_id == "required_files"
    assert checks[0].status == "FAIL"


def test_sqlite_schema_version_drift_is_critical(monkeypatch, tmp_path):
    checks = []
    monkeypatch.setattr(preflight, "SCHEMA_VERSION", 2)
    preflight._check_sqlite(checks, tmp_path / "state.sqlite3")
    schema = next(item for item in checks if item.check_id == "sqlite_schema_initialization")
    assert schema.status == "FAIL"
    assert schema.critical is True


def test_preflight_checks_python_version_without_running_app(monkeypatch):
    checks = []
    monkeypatch.setattr(preflight.sys, "version_info", SimpleNamespace(major=3, minor=10))
    preflight._check_python(checks)
    assert checks[0].status == "FAIL"


def test_preflight_reports_template_count_drift(monkeypatch, tmp_path):
    monkeypatch.setattr(
        preflight,
        "build_manifest",
        lambda **_: {"production": [], "candidates": [], "blocked_slots": []},
    )
    report = preflight.run_preflight(
        root=ROOT, env=_env(), port=_free_port(), db_path=tmp_path / "state.sqlite3"
    )
    assert {item["check_id"] for item in report["checks"] if item["status"] == "FAIL"} >= {
        "production_template_count", "blocked_slot_count"
    }


def test_strict_cli_exit_code_and_json_output_are_stable(tmp_path, capsys):
    exit_code = preflight.main(
        [
            "--strict",
            "--format",
            "json",
            "--root",
            str(ROOT),
            "--db-path",
            str(tmp_path / "state.sqlite3"),
            "--port",
            "0",
        ]
    )
    assert exit_code == 1
    report = json.loads(capsys.readouterr().out)
    assert set(report) == {"checks", "mode", "network", "schema_version", "summary"}
    assert report["network"] == "disabled"
