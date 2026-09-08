"""Regression coverage for the reproducible source-role inventory."""

from __future__ import annotations

import json
from pathlib import Path

from tools.source_role_inventory import build_source_role_inventory, main


ROOT = Path(__file__).resolve().parents[1]


def test_real_inventory_is_complete_candidate_isolated_and_has_one_iddfs_context_ref():
    report = build_source_role_inventory(root=ROOT)

    assert (report["production_template_count"], report["candidate_template_count"], report["blocked_slot_count"]) == (28, 0, 1)
    assert report["statistics"]["context_only_refs"] == 1
    assert report["statistics"]["templates_with_zero_evidence_refs"] == 0
    assert report["statistics"]["templates_with_all_refs_context_only"] == 0
    assert report["statistics"]["topic_mismatches"] == 0
    assert report["statistics"]["invalid_pages"] == 0
    assert report["statistics"]["filename_mismatches"] == 0
    assert report["statistics"]["unknown_chunks"] == 0
    iddfs = [row for row in report["rows"] if row["template_id"] == "verify_search_algorithm_properties_v1"]
    assert any(row["page_start"] == 53 and row["context_only"] is True for row in iddfs)
    assert any(row["page_start"] == 58 and row["primary_evidence"] is True and row["context_only"] is False for row in iddfs)
    assert sum(row["context_only"] is True for row in report["rows"] if row["bank"] == "production") == 1


def test_inventory_cli_writes_parseable_stable_reports(tmp_path):
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    assert main(["--json-report", str(json_path), "--markdown-report", str(markdown_path)]) == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["run_metadata"] == {"mode": "offline", "network": "disabled", "env": "not_read"}
    assert "Verification source-role inventory" in markdown_path.read_text(encoding="utf-8")
