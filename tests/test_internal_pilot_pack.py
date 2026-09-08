import csv
import json
from pathlib import Path

import pytest

from tools.generate_internal_pilot_pack import OUTPUT_FILES, PilotPackError, generate_pack


ROOT = Path(__file__).resolve().parents[1]


def test_pack_generator_creates_stable_privacy_minimal_inventory(tmp_path):
    output = tmp_path / "pack"
    paths = generate_pack(
        root=ROOT,
        output_dir=output,
        generated_at_utc="2026-08-10T00:00:00Z",
    )
    assert [path.name for path in paths] == list(OUTPUT_FILES)
    manifest = json.loads((output / "pilot_release_manifest.json").read_text(encoding="utf-8"))
    assert manifest == {
        "schema_version": 1,
        "pilot_release": "p4d",
        "generated_at_utc": "2026-08-10T00:00:00Z",
        "git_commit_short_sha": manifest["git_commit_short_sha"],
        "production_template_count": 28,
        "concept_count": 26,
        "pilot_task_count": 6,
        "focus_role_count": 6,
        "expected_feedback_schema_version": 1,
    }
    with (output / "tester_focus_assignments.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert [row["role_id"] for row in rows] == [f"role_{letter}" for letter in "abcdef"]
    assert all(len(row["required_core_task_ids"].split("；")) == 6 for row in rows)
    assert "G-XXXXXX" in (output / "tester_instructions.md").read_text(encoding="utf-8")
    assert (output / "issue_triage_template.csv").read_text(encoding="utf-8").splitlines()[0].startswith("issue_id,")
    for path in output.iterdir():
        assert ROOT.as_posix() not in path.read_text(encoding="utf-8")
    assert "learner_uuid" not in (output / "pilot_release_manifest.json").read_text(encoding="utf-8")
    assert "api_key" not in (output / "pilot_release_manifest.json").read_text(encoding="utf-8").casefold()
    remote_tester = (output / "remote_tester_message_template.md").read_text(encoding="utf-8")
    remote_facilitator = (output / "remote_facilitator_launch_checklist.md").read_text(encoding="utf-8")
    for placeholder in (
        "<PILOT_HTTPS_URL>",
        "<PILOT_ACCESS_CODE>",
        "<FOCUS_ROLE>",
        "<FEEDBACK_RETURN_CHANNEL>",
        "<DEADLINE>",
    ):
        assert placeholder in remote_tester
    assert "Ctrl+C" in remote_facilitator
    packed_text = "\n".join(path.read_text(encoding="utf-8") for path in output.iterdir())
    assert "https://trycloudflare.com" not in packed_text
    assert "INTROAI_PILOT_ACCESS_CODE=" not in packed_text


def test_pack_generator_fails_closed_for_nonempty_directory_and_overwrites_explicitly(tmp_path):
    output = tmp_path / "pack"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(PilotPackError):
        generate_pack(root=ROOT, output_dir=output, generated_at_utc="2026-08-10T00:00:00Z")
    generate_pack(
        root=ROOT,
        output_dir=output,
        generated_at_utc="2026-08-10T00:00:00Z",
        overwrite=True,
    )
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_pack_generator_rejects_invalid_timestamp(tmp_path):
    with pytest.raises(PilotPackError):
        generate_pack(root=ROOT, output_dir=tmp_path / "pack", generated_at_utc="not-a-timestamp")
