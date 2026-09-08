from pathlib import Path
import json

from tools.document_consistency import check_documents


ROOT = Path(__file__).resolve().parents[1]


def test_p2g_document_counts_do_not_conflict_with_manifest():
    result = check_documents(root=ROOT)
    assert result["errors"] == []


def test_p2g_document_checker_is_read_only_and_returns_reviewable_warnings(tmp_path):
    (tmp_path / "docs").mkdir()
    # The tool's paths are intentionally fixed to maintained docs; this case
    # documents that no rewrite facility exists.
    assert set(check_documents(root=ROOT)) == {"errors", "warnings"}


def test_final_owner_decisions_and_promotion_are_documented():
    candidate = json.loads((ROOT / "data/candidate_templates/search_algorithms_p2f_candidates.json").read_text(encoding="utf-8"))
    review = (ROOT / "docs/search_algorithms_p2f_candidate_review.md").read_text(encoding="utf-8")
    packet = json.loads((ROOT / "docs/generated/search_algorithms_template_review_packet.json").read_text(encoding="utf-8"))

    assert candidate["candidate_status"] == "promoted_to_production"
    assert candidate["templates"] == []
    assert candidate["acceptance_cases"] == {}
    assert "promotion" in review.lower()
    assert review.count("verify_") >= 8
    assert all(entry["owner_decision"] == "" for entry in [*packet["production"], *packet["candidates"]])
    assert "Authoritative owner decisions" in (ROOT / "docs/generated/search_algorithms_template_review_packet.md").read_text(encoding="utf-8")
