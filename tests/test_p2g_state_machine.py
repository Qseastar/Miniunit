"""Regression contract for P2g's real bounded state-machine explorer."""

from pathlib import Path
import json

import pytest

from introai_tutor.verification_diagnostics import VerificationDiagnosticError, VerificationDiagnosticService
from tests.verification_benchmark_manifest import build_manifest
from tools.p2g_state_exploration import explore_template


ROOT = Path(__file__).resolve().parents[1]


def _templates():
    return {item["id"]: item for item in json.loads((ROOT / "data" / "diagnostic_templates.json").read_text(encoding="utf-8"))["templates"]}


_BY_ID = {item["template_id"]: item for item in build_manifest(root=ROOT)["production"]}


@pytest.mark.parametrize("template_id", [
    "verify_bfs_frontier_choice_v1", "verify_bfs_equal_cost_condition_v1",
    "verify_dfs_frontier_choice_v1", "verify_admissibility_no_overestimate_v1",
    "verify_search_problem_components_v1",
])
def test_bounded_real_state_machine_exploration(template_id):
    entry = _BY_ID[template_id]
    stats = explore_template(
        template=_templates()[template_id], correct_answer=entry["known_correct"],
        wrong_answer=entry["known_wrong"][0], max_depth=4,
    )
    assert stats["max_depth"] == 4
    assert stats["explored_paths"] >= 3
    assert stats["unique_states"] == stats["explored_paths"]
    assert stats["rejected_transitions"] >= 1


def test_promoted_candidate_staging_is_inactive_after_promotion():
    candidate = json.loads((ROOT / "data" / "candidate_templates" / "search_algorithms_p2f_candidates.json").read_text(encoding="utf-8"))
    assert candidate["candidate_status"] == "promoted_to_production"
    assert candidate["templates"] == []
    assert candidate["acceptance_cases"] == {}
