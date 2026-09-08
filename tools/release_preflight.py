#!/usr/bin/env python3
"""Run the offline reproducibility check for the Summer release.

This is intentionally a thin release-facing wrapper.  The existing pilot
preflight, verification quality gate, and application composition root remain
the authorities for their respective checks; this module only labels their
results as core or optional release readiness and checks the real startup
paths used by the research application.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from introai_tutor.app_services import (  # noqa: E402
    build_dual_track_diagnostic_workflow,
    load_app_data,
)
from introai_tutor.knowledge import load_knowledge_points  # noqa: E402
from introai_tutor.learner_state_repository import SCHEMA_VERSION  # noqa: E402
from tools.pilot_preflight import run_preflight  # noqa: E402
from tools.verification_benchmark import build_manifest  # noqa: E402
from tools.verification_quality_gate import run_quality_gate  # noqa: E402


EXPECTED_PRODUCTION_TEMPLATES = 28
EXPECTED_ACTIVE_CANDIDATES = 0
EXPECTED_BLOCKED_SLOTS = 1
EXPECTED_CONCEPTS = 26
EXPECTED_PRIMARY_FORMAL_COVERAGE = 21
EXPECTED_SOURCE_MANIFEST_FILES = 8
EXPECTED_SQLITE_SCHEMA = 3
P5B_PROMOTED_IDS = frozenset(
    {
        "verify_local_search_final_state_focus_v1",
        "verify_hill_climbing_stop_at_local_best_v1",
        "verify_simulated_annealing_worse_successor_v1",
        "verify_evolutionary_search_parent_cycle_v1",
        "verify_minimax_max_min_value_choice_v1",
        "verify_alpha_beta_prune_when_bounds_cross_v1",
        "verify_mcts_four_stage_order_v1",
        "verify_ucb_upper_bound_selection_v1",
    }
)


@dataclass(frozen=True)
class ReleaseCheck:
    check_id: str
    status: str
    message: str
    critical: bool


def run_release_preflight(
    *,
    root: str | Path = ROOT,
    env: Mapping[str, str] | None = None,
    port: int = 8501,
    host: str = "127.0.0.1",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe, offline report without writing learner data.

    ``env`` is injected by tests and otherwise uses the process environment;
    this function never loads or executes a ``.env`` file.  Missing provider
    credentials, course PDFs, Poppler, and cloudflared are optional warnings
    for the local deterministic research runtime. Registry, startup, and quality-gate
    failures are release-blocking.
    """

    root = Path(root)
    environment = os.environ if env is None else env
    checks: list[ReleaseCheck] = []

    # Reuse the existing offline checks.  They do not write the configured DB;
    # their schema probe uses its own temporary database.
    # A release check must be runnable from a clean room where the developer's
    # home directory is read-only.  The existing preflight only probes the
    # parent and creates its schema check in a temporary database; use the
    # same isolated parent here when the caller did not provide a DB path.
    effective_db_path = (
        Path(db_path)
        if db_path is not None
        else Path(tempfile.gettempdir()) / "introai_release_preflight.sqlite3"
    )
    base = run_preflight(
        root=root,
        env=environment,
        port=port,
        host=host,
        db_path=effective_db_path,
        remote=False,
    )
    for item in base["checks"]:
        checks.append(
            ReleaseCheck(
                check_id=item["check_id"],
                status=item["status"],
                message=item["message"],
                critical=bool(item["critical"]),
            )
        )

    # The verification quality gate is the single source of truth for source
    # refs, page bounds, scorer contracts, malformed answers, and candidate
    # isolation.  Do not reimplement any of those rules here.
    try:
        quality = run_quality_gate(root=root, production_only=True)
        manifest = build_manifest(root=root)
        _add_invariant(
            checks,
            "release_production_template_count",
            len(manifest["production"]) == EXPECTED_PRODUCTION_TEMPLATES,
            f"production templates={len(manifest['production'])}",
        )
        _add_invariant(
            checks,
            "release_active_candidate_count",
            len(manifest["candidates"]) == EXPECTED_ACTIVE_CANDIDATES,
            f"active candidates={len(manifest['candidates'])}",
        )
        _add_invariant(
            checks,
            "release_blocked_slot_count",
            len(manifest["blocked_slots"]) == EXPECTED_BLOCKED_SLOTS,
            f"blocked slots={len(manifest['blocked_slots'])}",
        )
        production_ids = [item["template_id"] for item in manifest["production"]]
        candidate_ids = {item["template_id"] for item in manifest["candidates"]}
        _add_invariant(
            checks,
            "release_production_id_uniqueness",
            len(production_ids) == len(set(production_ids)),
            "production template IDs are unique",
        )
        _add_invariant(
            checks,
            "release_blocked_slot_contract",
            {
                slot.get("proposed_template_id") for slot in manifest["blocked_slots"]
            }
            == {"verify_ucs_frontier_update_v1"}
            and not candidate_ids.intersection(
                {slot.get("proposed_template_id") for slot in manifest["blocked_slots"]}
            ),
            "UCS frontier-update slot remains blocked and fail-closed",
        )
        _add_invariant(
            checks,
            "release_p5b_promotion_visibility",
            P5B_PROMOTED_IDS.issubset(set(production_ids))
            and not P5B_PROMOTED_IDS.intersection(candidate_ids),
            "all eight P5b promoted IDs are production-visible and candidate-isolated",
        )
        direct_coverage = len({item["primary_concept"] for item in manifest["production"]})
        _add_invariant(
            checks,
            "release_primary_formal_coverage",
            direct_coverage == EXPECTED_PRIMARY_FORMAL_COVERAGE,
            f"direct primary formal coverage={direct_coverage}/{EXPECTED_CONCEPTS}",
        )
        material_count = quality.get("material_manifest_summary", {}).get("material_count", 0)
        _add_invariant(
            checks,
            "release_source_manifest_count",
            material_count == EXPECTED_SOURCE_MANIFEST_FILES,
            f"source manifest files={material_count}",
        )
        registry_concepts = load_knowledge_points(
            root / "data" / "knowledge_points.json"
        )["knowledge_points"]
        _add_invariant(
            checks,
            "release_concept_count",
            len(registry_concepts) == EXPECTED_CONCEPTS,
            f"concepts={len(registry_concepts)}",
        )
        _add_invariant(
            checks,
            "release_sqlite_schema",
            SCHEMA_VERSION == EXPECTED_SQLITE_SCHEMA,
            f"SQLite schema={SCHEMA_VERSION}",
        )
        _add_invariant(
            checks,
            "release_verification_quality_gate",
            quality["overall_status"] == "pass"
            and quality["source_summary"]["fail"] == 0
            and quality["candidate_isolation_summary"][
                "candidate_ids_visible_to_production"
            ]
            == [],
            "production source/scorer/page contracts pass and candidates are isolated",
        )
    except Exception as error:
        _add(
            checks,
            "release_verification_quality_gate",
            "FAIL",
            f"verification quality gate unavailable ({type(error).__name__})",
            True,
        )
        manifest = {"production": [], "candidates": [], "blocked_slots": []}
        quality = {"concept_inventory": [], "overall_status": "fail"}

    # Exercise the same immutable data loading and reviewed diagnostic
    # composition used by Streamlit, without an adapter, network, or learner
    # state integration.
    try:
        data = load_app_data(root)
        _add(checks, "release_qa_initialization", "PASS", "QA course and diagnostic inputs initialize", True)
        _add(
            checks,
            "release_concept_registry",
            "PASS" if len(data["knowledge_data"]["knowledge_points"]) == EXPECTED_CONCEPTS else "FAIL",
            f"application loaded concepts={len(data['knowledge_data']['knowledge_points'])}",
            True,
        )
    except Exception as error:
        _add(checks, "release_qa_initialization", "FAIL", f"QA initialization failed ({type(error).__name__})", True)
        _add(checks, "release_concept_registry", "FAIL", "application concept registry could not initialize", True)

    try:
        workflow = build_dual_track_diagnostic_workflow(root=root)
        started = workflow.start()
        valid = (
            isinstance(started, dict)
            and started.get("phase") == "formative"
            and started.get("purpose") == "formative"
            and started.get("evidence_eligible") is False
            and started.get("state_update") is None
        )
        _add(
            checks,
            "release_reviewed_diagnostic_initialization",
            "PASS" if valid else "FAIL",
            "reviewed diagnostic starts in the formative gate without state update"
            if valid
            else "reviewed diagnostic initialization returned an invalid boundary",
            True,
        )
    except Exception as error:
        _add(
            checks,
            "release_reviewed_diagnostic_initialization",
            "FAIL",
            f"reviewed diagnostic initialization failed ({type(error).__name__})",
            True,
        )

    # These tools are deliberately optional for the core local research
    # path. Keep their absence visible without turning a deterministic run
    # into a remote-pilot or PDF-rendering requirement.
    _add(
        checks,
        "optional_cloudflared",
        "PASS" if shutil.which("cloudflared") else "WARN",
        "cloudflared available (Remote Pilot optional)"
        if shutil.which("cloudflared")
        else "cloudflared unavailable; core local runtime remains available",
        False,
    )

    summary = {
        "pass": sum(item.status == "PASS" for item in checks),
        "warn": sum(item.status == "WARN" for item in checks),
        "fail": sum(item.status == "FAIL" for item in checks),
        "critical_fail": sum(item.status == "FAIL" and item.critical for item in checks),
    }
    return {
        "schema_version": 1,
        "mode": "offline_release",
        "network": "disabled",
        "env": "not_read_from_file",
        "checks": [asdict(item) for item in checks],
        "summary": summary,
        "release_invariants": {
            "production_templates": len(manifest["production"]),
            "active_candidates": len(manifest["candidates"]),
            "blocked_slots": len(manifest["blocked_slots"]),
            "concepts": _registry_concept_count(root),
            "direct_primary_formal_coverage": len(
                {item.get("primary_concept") for item in manifest["production"]}
            ),
            "source_manifest_files": quality.get("material_manifest_summary", {}).get(
                "material_count", 0
            ),
            "sqlite_schema": SCHEMA_VERSION,
        },
    }


def _registry_concept_count(root: Path) -> int:
    try:
        return len(load_knowledge_points(root / "data" / "knowledge_points.json")["knowledge_points"])
    except (OSError, KeyError, TypeError, ValueError):
        return 0


def _add_invariant(checks: list[ReleaseCheck], check_id: str, passed: bool, message: str) -> None:
    _add(checks, check_id, "PASS" if passed else "FAIL", message, True)


def _add(checks: list[ReleaseCheck], check_id: str, status: str, message: str, critical: bool) -> None:
    checks.append(ReleaseCheck(check_id, status, message, critical))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--json-report", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = run_release_preflight(
        root=args.root,
        port=args.port,
        host=args.host,
        db_path=args.db_path,
    )
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
    if args.json_report is not None:
        args.json_report.write_text(rendered + "\n", encoding="utf-8")
    if args.format == "json":
        print(rendered)
    else:
        print("IntroAI Tutor Summer Release reproducibility preflight (offline; network disabled)")
        for item in report["checks"]:
            print(f"[{item['status']}] {item['check_id']}: {item['message']}")
        summary = report["summary"]
        print(f"Summary: PASS={summary['pass']} WARN={summary['warn']} FAIL={summary['fail']}")
    return 1 if args.strict and report["summary"]["critical_fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
