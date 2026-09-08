#!/usr/bin/env python3
"""Run an offline, fail-closed readiness check for the internal pilot."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import errno
import importlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Any, Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from introai_tutor.course_materials import load_course_chunks  # noqa: E402
from introai_tutor.deepseek_adapter import DEFAULT_BASE_URL, DEFAULT_MODEL  # noqa: E402
from introai_tutor.knowledge import load_knowledge_points  # noqa: E402
from introai_tutor.learner_state_repository import (  # noqa: E402
    SCHEMA_VERSION,
    SQLiteLearnerStateRepository,
)
from introai_tutor.pilot_feedback import (  # noqa: E402
    FREE_TEXT_FIELDS,
    FEEDBACK_SCHEMA_VERSION,
    RATING_FIELDS,
    build_feedback_payload,
    payload_json,
)
from introai_tutor.pilot_access import (  # noqa: E402
    build_access_policy,
    access_code_status,
    is_loopback_host,
    normalize_host,
)
from introai_tutor.pilot_focus_roles import load_focus_roles  # noqa: E402
from introai_tutor.pilot_mode import is_pilot_mode_enabled  # noqa: E402
from introai_tutor.pilot_tasks import load_pilot_tasks, ordered_tasks  # noqa: E402
from tools.course_material_manifest import (  # noqa: E402
    load_course_material_manifest,
    material_index,
    validate_chunk_material_coverage,
)
from tools.verification_benchmark import build_manifest  # noqa: E402
from tools.verify_local_course_materials import (  # noqa: E402
    LocalMaterialIntegrityError,
    verify_local_course_materials,
)


@dataclass(frozen=True)
class PreflightCheck:
    check_id: str
    status: str
    message: str
    critical: bool


def run_preflight(
    *,
    root: str | Path = ROOT,
    env: Mapping[str, str] | None = None,
    port: int = 8503,
    host: str = "127.0.0.1",
    db_path: str | Path | None = None,
    remote: bool = False,
    tunnel_provider: str | None = None,
    tunnel_binary: str | Path | None = None,
) -> dict[str, Any]:
    """Return stable PASS/WARN/FAIL checks without network or learner writes."""
    root = Path(root)
    environment = os.environ if env is None else env
    checks: list[PreflightCheck] = []
    _check_python(checks)
    _check_required_files(checks, root)
    _check_runtime_requirements(checks, root)
    _check_streamlit(checks)
    _check_pilot_config(checks, environment)
    _check_deepseek_config(checks, environment)
    _check_access_boundary(checks, environment, host)
    if remote:
        _check_remote_boundary(
            checks,
            environment,
            host=host,
            tunnel_provider=tunnel_provider,
            tunnel_binary=tunnel_binary,
        )
    _check_sqlite(checks, db_path)

    knowledge_data: dict[str, Any] | None = None
    tasks_data: dict[str, Any] | None = None
    try:
        knowledge_data = load_knowledge_points(root / "data" / "knowledge_points.json")
        _add(checks, "concept_count", "PASS" if len(knowledge_data["knowledge_points"]) == 26 else "FAIL", "concept registry count checked", True)
    except Exception as error:  # loaders expose safe ValueError/OSError messages
        _add(checks, "concept_count", "FAIL", f"concept registry unavailable ({type(error).__name__})", True)

    try:
        manifest = build_manifest(root=root)
        production_ok = len(manifest["production"]) == 28
        candidate_ok = len(manifest["candidates"]) == 0
        blocked_ok = len(manifest["blocked_slots"]) == 1
        _add(checks, "production_template_count", "PASS" if production_ok else "FAIL", f"production templates={len(manifest['production'])}", True)
        _add(checks, "active_candidate_count", "PASS" if candidate_ok else "FAIL", f"active candidates={len(manifest['candidates'])}", True)
        _add(checks, "blocked_slot_count", "PASS" if blocked_ok else "FAIL", f"blocked slots={len(manifest['blocked_slots'])}", True)
    except Exception as error:
        for check_id in ("production_template_count", "active_candidate_count", "blocked_slot_count"):
            _add(checks, check_id, "FAIL", f"template manifest unavailable ({type(error).__name__})", True)

    try:
        tasks_data = load_pilot_tasks(root / "data" / "pilot_search_algorithms_tasks.json")
        _add(checks, "pilot_task_count", "PASS" if len(ordered_tasks(tasks_data)) == 6 else "FAIL", "six pilot tasks loaded", True)
    except Exception as error:
        _add(checks, "pilot_task_count", "FAIL", f"pilot tasks unavailable ({type(error).__name__})", True)

    if tasks_data is not None:
        try:
            load_focus_roles(root / "data" / "internal_pilot_focus_roles.json", tasks_data=tasks_data)
            _add(checks, "focus_role_count", "PASS", "six focus roles loaded", True)
        except Exception as error:
            _add(checks, "focus_role_count", "FAIL", f"focus roles unavailable ({type(error).__name__})", True)
        try:
            payload = build_feedback_payload(
                tasks_data=tasks_data,
                tester_code="G-ABCDEF",
                completed_task_ids=[],
                ratings={field: 3 for field in RATING_FIELDS},
                free_text_feedback={field: "" for field in FREE_TEXT_FIELDS},
                generated_at_utc="2026-08-10T00:00:00Z",
            )
            payload_json(payload, valid_task_ids={task["task_id"] for task in ordered_tasks(tasks_data)})
            _add(checks, "feedback_schema", "PASS", f"feedback schema v{FEEDBACK_SCHEMA_VERSION} constructs", True)
        except Exception as error:
            _add(checks, "feedback_schema", "FAIL", f"feedback schema unavailable ({type(error).__name__})", True)
    else:
        _add(checks, "focus_role_count", "FAIL", "pilot tasks are unavailable", True)
        _add(checks, "feedback_schema", "FAIL", "pilot tasks are unavailable", True)

    try:
        importlib.import_module("introai_tutor.pilot_feedback_aggregation")
        _add(checks, "aggregation_import", "PASS", "offline aggregation module imports", True)
    except Exception as error:
        _add(checks, "aggregation_import", "FAIL", f"aggregation unavailable ({type(error).__name__})", True)

    _check_course_materials(checks, root, knowledge_data)
    _check_citation_preview(checks, root, environment)
    _check_app_compile(checks, root)
    _check_port(checks, port, host=host)
    _check_tracked_artifacts(checks, root)
    return {
        "schema_version": 1,
        "mode": "offline",
        "network": "disabled",
        "checks": [asdict(item) for item in checks],
        "summary": {
            "pass": sum(item.status == "PASS" for item in checks),
            "warn": sum(item.status == "WARN" for item in checks),
            "fail": sum(item.status == "FAIL" for item in checks),
            "critical_fail": sum(item.status == "FAIL" and item.critical for item in checks),
        },
    }


def _check_python(checks: list[PreflightCheck]) -> None:
    version = sys.version_info
    ok = (version.major, version.minor) >= (3, 11)
    _add(checks, "python_version", "PASS" if ok else "FAIL", "Python version requirement checked", True)


def _check_required_files(checks: list[PreflightCheck], root: Path) -> None:
    required = (
        "app.py",
        "requirements.txt",
        "data/knowledge_points.json",
        "data/diagnostic_templates.json",
        "data/course_chunks.json",
        "data/course_material_manifest.json",
        "data/pilot_search_algorithms_tasks.json",
        "data/internal_pilot_focus_roles.json",
        "tools/summarize_pilot_feedback.py",
        "scripts/quality_gate.sh",
    )
    missing = [item for item in required if not (root / item).is_file()]
    _add(checks, "required_files", "PASS" if not missing else "FAIL", "required project files are present" if not missing else "required files are missing", True)


def _check_streamlit(checks: list[PreflightCheck]) -> None:
    try:
        importlib.import_module("streamlit")
    except Exception as error:
        _add(checks, "runtime_streamlit", "FAIL", f"Streamlit import failed ({type(error).__name__})", True)
    else:
        _add(checks, "runtime_streamlit", "PASS", "Streamlit is importable", True)


def _check_runtime_requirements(checks: list[PreflightCheck], root: Path) -> None:
    """Check the small runtime requirements file without installing anything."""
    path = root / "requirements.txt"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        _add(checks, "runtime_requirements", "FAIL", f"requirements file unavailable ({type(error).__name__})", True)
        return
    packages = [line.split("#", 1)[0].strip() for line in lines if line.split("#", 1)[0].strip()]
    if not packages:
        _add(checks, "runtime_requirements", "FAIL", "requirements file has no runtime packages", True)
        return
    # The current runtime file intentionally contains only Streamlit.  Keep
    # the check generic enough to flag a missing named package if that file is
    # extended, while avoiding a second package-management implementation.
    import_names = {"streamlit": "streamlit"}
    missing = []
    for package in packages:
        normalized = package.split("[", 1)[0]
        name = import_names.get(normalized.casefold())
        if name is None:
            continue
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(normalized)
    _add(checks, "runtime_requirements", "PASS" if not missing else "FAIL", "runtime requirements are importable" if not missing else "runtime requirements are not importable", True)


def _check_pilot_config(checks: list[PreflightCheck], env: Mapping[str, str]) -> None:
    raw = env.get("INTROAI_PILOT_MODE", "")
    allowed = {"", "0", "1", "true", "false", "on", "off", "yes", "no"}
    valid = raw.strip().casefold() in allowed
    enabled = is_pilot_mode_enabled(raw)
    message = "pilot mode enabled" if enabled else "pilot mode disabled"
    _add(checks, "pilot_mode_config", "PASS" if valid else "FAIL", message if valid else "pilot mode configuration is invalid", True)


def _check_deepseek_config(checks: list[PreflightCheck], env: Mapping[str, str]) -> None:
    key_present = bool(env.get("DEEPSEEK_API_KEY", "").strip())
    _add(checks, "deepseek_api_key_present", "PASS" if key_present else "WARN", "DEEPSEEK_API_KEY present=true (value hidden)" if key_present else "DEEPSEEK_API_KEY present=false; deterministic paths remain available", False)
    base = env.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip()
    parsed = urlsplit(base)
    _add(checks, "deepseek_base_url", "PASS" if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else "FAIL", "base URL is syntactically usable; no request made" if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else "base URL is invalid", True)
    model = env.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip()
    _add(checks, "deepseek_model", "PASS" if bool(model) else "FAIL", "model is configured or defaulted; value hidden" if model else "model is empty", True)


def _check_access_boundary(checks: list[PreflightCheck], env: Mapping[str, str], host: str) -> None:
    raw_mode = env.get("INTROAI_PILOT_MODE", "")
    raw_code = env.get("INTROAI_PILOT_ACCESS_CODE", "")
    present, valid = access_code_status(raw_code)
    try:
        normalized_host = normalize_host(host)
        policy = build_access_policy(
            pilot_mode=raw_mode,
            access_code=raw_code,
            host=normalized_host,
        )
    except (TypeError, ValueError):
        _add(checks, "pilot_bind_host", "FAIL", "pilot bind host is invalid", True)
        _add(checks, "pilot_access_code_config", "FAIL", f"present={str(present).lower()} valid={str(valid).lower()}", True)
        _add(checks, "pilot_access_boundary", "FAIL", "pilot access boundary is invalid", True)
        return
    _add(checks, "pilot_bind_host", "PASS", f"bind host={normalized_host}", True)
    if not policy.pilot_enabled:
        _add(
            checks,
            "pilot_access_code_config",
            "PASS",
            f"present={str(present).lower()} valid={str(valid).lower()} (access code not used in ordinary mode)",
            False,
        )
        if policy.host_is_loopback:
            _add(checks, "pilot_access_boundary", "PASS", "ordinary loopback mode does not require pilot access", True)
        else:
            _add(checks, "pilot_access_boundary", "FAIL", "non-loopback bind requires Pilot mode", True)
        return
    config_status = "PASS" if valid else ("WARN" if policy.host_is_loopback and not present else "FAIL")
    _add(
        checks,
        "pilot_access_code_config",
        config_status,
        f"present={str(present).lower()} valid={str(valid).lower()}",
        config_status == "FAIL",
    )
    if policy.local_no_code_fallback:
        _add(checks, "pilot_access_boundary", "WARN", "loopback Pilot mode is using owner-only no-code fallback", False)
    elif policy.access_code_valid:
        _add(checks, "pilot_access_boundary", "PASS", "pilot access code protects the requested bind", True)
    else:
        _add(checks, "pilot_access_boundary", "FAIL", "non-loopback or invalid Pilot access configuration", True)


def _check_remote_boundary(
    checks: list[PreflightCheck],
    env: Mapping[str, str],
    *,
    host: str,
    tunnel_provider: str | None,
    tunnel_binary: str | Path | None,
) -> None:
    """Apply P4d's stricter remote-pilot requirements without networking."""
    provider = "cloudflared" if tunnel_provider is None else tunnel_provider
    if provider != "cloudflared":
        _add(checks, "remote_tunnel_provider", "FAIL", "remote tunnel provider is unsupported", True)
        _add(checks, "remote_tunnel_binary", "FAIL", "remote tunnel provider is unsupported", True)
    else:
        _add(checks, "remote_tunnel_provider", "PASS", "cloudflared Quick Tunnel selected", True)
        _check_cloudflared_binary(checks, tunnel_binary)

    if host != "127.0.0.1" or not is_loopback_host(host):
        _add(
            checks,
            "remote_streamlit_host",
            "FAIL",
            "remote Pilot requires Streamlit to bind exactly 127.0.0.1",
            True,
        )
    else:
        _add(
            checks,
            "remote_streamlit_host",
            "PASS",
            "remote Pilot keeps Streamlit on 127.0.0.1",
            True,
        )

    enabled = is_pilot_mode_enabled(env.get("INTROAI_PILOT_MODE", ""))
    _add(
        checks,
        "remote_pilot_mode",
        "PASS" if enabled else "FAIL",
        "remote Pilot mode is enabled" if enabled else "remote Pilot mode must be enabled",
        True,
    )
    present, valid = access_code_status(env.get("INTROAI_PILOT_ACCESS_CODE", ""))
    _add(
        checks,
        "remote_access_code",
        "PASS" if valid else "FAIL",
        f"present={str(present).lower()} valid={str(valid).lower()}",
        True,
    )


def _check_cloudflared_binary(
    checks: list[PreflightCheck], binary: str | Path | None
) -> None:
    candidate = Path(binary) if binary is not None else _which_cloudflared()
    if candidate is None or not candidate.is_file() or not os.access(candidate, os.X_OK):
        _add(
            checks,
            "remote_tunnel_binary",
            "FAIL",
            "cloudflared executable is unavailable; install it manually before remote Pilot use",
            True,
        )
        return
    _add(
        checks,
        "remote_tunnel_binary",
        "PASS",
        "cloudflared executable is available; no provider request was made",
        True,
    )


def _which_cloudflared() -> Path | None:
    resolved = shutil.which("cloudflared")
    return Path(resolved) if resolved else None


def _check_sqlite(checks: list[PreflightCheck], db_path: str | Path | None) -> None:
    configured = Path(db_path).expanduser() if db_path is not None else None
    parent = configured.parent if configured is not None else Path.home() / ".introai_tutor"
    existing = parent
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    writable = existing.is_dir() and os.access(existing, os.W_OK)
    _add(checks, "sqlite_directory", "PASS" if writable else "FAIL", "SQLite parent directory is writable" if writable else "SQLite parent directory is not writable", True)
    try:
        with tempfile.TemporaryDirectory(prefix="introai_pilot_preflight_") as directory:
            repository = SQLiteLearnerStateRepository(Path(directory) / "schema.sqlite3")
            repository.health_check()
        schema_ok = SCHEMA_VERSION == 3
        _add(
            checks,
            "sqlite_schema_initialization",
            "PASS" if schema_ok else "FAIL",
            f"SQLite schema={SCHEMA_VERSION} initialized in a temporary check database"
            if schema_ok
            else f"SQLite schema version is {SCHEMA_VERSION}; expected 3",
            True,
        )
    except Exception as error:
        _add(checks, "sqlite_schema_initialization", "FAIL", f"SQLite schema check failed ({type(error).__name__})", True)


def _check_course_materials(checks: list[PreflightCheck], root: Path, knowledge_data: dict[str, Any] | None) -> None:
    if knowledge_data is None:
        _add(checks, "course_material_manifest", "FAIL", "knowledge data is unavailable", True)
        return
    try:
        manifest = load_course_material_manifest(root / "data" / "course_material_manifest.json")
        chunks = load_course_chunks(root / "data" / "course_chunks.json", knowledge_data)
        issues = validate_chunk_material_coverage(
            {item["id"]: item for item in chunks["chunks"]}, material_index(manifest)
        )
        _add(checks, "course_material_manifest", "PASS" if not issues else "FAIL", "course material manifest and chunk coverage are valid" if not issues else "course material coverage has issues", True)
    except Exception as error:
        _add(checks, "course_material_manifest", "FAIL", f"course material manifest unavailable ({type(error).__name__})", True)
    material_root = root / "local_materials"
    if not material_root.exists():
        _add(checks, "local_material_integrity", "WARN", "local PDF subset is unavailable; metadata-only check completed", False)
        return
    try:
        result = verify_local_course_materials(
            manifest_path=root / "data" / "course_material_manifest.json",
            materials_root=material_root,
            require=False,
        )
        _add(checks, "local_material_integrity", "PASS" if result["status"] == "pass" else "WARN", "local course materials match manifest" if result["status"] == "pass" else "some local PDFs are unavailable", False)
    except LocalMaterialIntegrityError as error:
        _add(checks, "local_material_integrity", "FAIL", f"local course material check failed ({type(error).__name__})", True)


def _check_citation_preview(
    checks: list[PreflightCheck], root: Path, environment: Mapping[str, str]
) -> None:
    """Report optional cited-page preview readiness without blocking the Pilot."""

    configured = environment.get("INTROAI_COURSE_MATERIALS_DIR", "")
    if not isinstance(configured, str) or not configured.strip():
        _add(
            checks,
            "citation_preview_readiness",
            "WARN",
            "citation preview unavailable; materials root is not configured",
            False,
        )
        return
    material_root = Path(configured.strip()).expanduser()
    if not material_root.is_dir():
        _add(
            checks,
            "citation_preview_readiness",
            "WARN",
            "citation preview unavailable; configured materials root is not usable",
            False,
        )
        return
    if shutil.which("pdftoppm") is None:
        _add(
            checks,
            "citation_preview_readiness",
            "WARN",
            "citation preview unavailable; pdftoppm is not installed",
            False,
        )
        return
    try:
        result = verify_local_course_materials(
            manifest_path=root / "data" / "course_material_manifest.json",
            materials_root=material_root,
            require=False,
        )
    except (OSError, LocalMaterialIntegrityError, ValueError):
        _add(
            checks,
            "citation_preview_readiness",
            "WARN",
            "citation preview is unavailable; local material verification needs attention",
            False,
        )
        return
    if result["status"] == "pass":
        _add(
            checks,
            "citation_preview_readiness",
            "PASS",
            "optional cited-page preview is ready",
            False,
        )
    else:
        _add(
            checks,
            "citation_preview_readiness",
            "WARN",
            "optional cited-page preview is unavailable; some local PDFs are missing",
            False,
        )


def _check_app_compile(checks: list[PreflightCheck], root: Path) -> None:
    try:
        compile((root / "app.py").read_text(encoding="utf-8"), "app.py", "exec")
    except Exception as error:
        _add(checks, "app_safe_compile", "FAIL", f"app compile failed ({type(error).__name__})", True)
    else:
        _add(checks, "app_safe_compile", "PASS", "app.py compiles without executing the app", True)


def _check_port(checks: list[PreflightCheck], port: int, *, host: str = "127.0.0.1") -> None:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        _add(checks, "streamlit_port", "FAIL", "port must be between 1 and 65535", True)
        return
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        bind_host = "::1" if host == "localhost" and family == socket.AF_INET6 else host
        with socket.socket(family, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((bind_host, port))
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            _add(checks, "streamlit_port", "FAIL", "requested port is occupied", True)
        else:
            # Some CI sandboxes prohibit socket creation altogether.  That is
            # not evidence that the requested port is occupied, so preserve a
            # visible WARN and let the person starting Streamlit decide.
            _add(checks, "streamlit_port", "WARN", "port availability could not be checked in this environment", False)
    else:
        _add(checks, "streamlit_port", "PASS", "requested port is available", True)


def _check_tracked_artifacts(checks: list[PreflightCheck], root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
        paths = [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as error:
        _add(checks, "tracked_sensitive_artifacts", "FAIL", f"tracked-file audit failed ({type(error).__name__})", True)
        return
    forbidden: list[str] = []
    for path in paths:
        lower = path.casefold()
        if Path(path).name.casefold() == ".env" or lower.endswith((".sqlite", ".sqlite3", ".log", ".pdf")):
            forbidden.append(path)
        if ("pilot_feedback_inbox/" in lower or "pilot_feedback_summary/" in lower) and lower.endswith(".json"):
            forbidden.append(path)
    _add(checks, "tracked_sensitive_artifacts", "PASS" if not forbidden else "FAIL", "no forbidden tracked artifacts found" if not forbidden else "forbidden tracked artifacts found", True)


def _add(checks: list[PreflightCheck], check_id: str, status: str, message: str, critical: bool) -> None:
    checks.append(PreflightCheck(check_id, status, message, critical))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="return non-zero for any FAIL check")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--port", type=int, default=8503)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--remote", action="store_true", help="apply Cloudflare Quick Tunnel Pilot checks")
    parser.add_argument("--tunnel-provider", choices=("cloudflared",), default=None)
    args = parser.parse_args(argv)
    if args.tunnel_provider is not None and not args.remote:
        parser.error("--tunnel-provider requires --remote")
    report = run_preflight(
        root=args.root,
        port=args.port,
        host=args.host,
        db_path=args.db_path,
        remote=args.remote,
        tunnel_provider=args.tunnel_provider,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print("IntroAI Tutor internal pilot preflight (offline; network disabled)")
        for item in report["checks"]:
            print(f"[{item['status']}] {item['check_id']}: {item['message']}")
        summary = report["summary"]
        print(f"Summary: PASS={summary['pass']} WARN={summary['warn']} FAIL={summary['fail']}")
    return 1 if args.strict and report["summary"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
