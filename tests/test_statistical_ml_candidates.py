"""Offline validation for the Statistical ML phase-1 candidate Mini Unit.

These tests only validate the new data (knowledge points and candidate
diagnostic templates) without touching the production registry or any shared
core logic. They intentionally do not depend on lec8 course chunks, which are
not yet ingested into ``course_chunks.json``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import validate_diagnostic_templates
from introai_tutor.verification_diagnostics import (
    VerificationDiagnosticError,
    VerificationDiagnosticService,
    score_verification_answer,
)

ROOT = Path(__file__).resolve().parents[1]
KP_PATH = ROOT / "data" / "statistical_ml_knowledge.json"
CANDIDATE_PATH = (
    ROOT / "data" / "candidate_templates" / "statistical_ml_p1_candidates.json"
)
PRODUCTION_PATH = ROOT / "data" / "diagnostic_templates.json"

STAT_ML_IDS = {
    "statistical_ml__supervised_learning",
    "statistical_ml__unsupervised_learning",
    "statistical_ml__knn_lazy_learning",
    "statistical_ml__knn_k_value_selection",
    "statistical_ml__knn_distance_metric",
    "statistical_ml__linear_regression_univariate",
    "statistical_ml__linear_regression_multivariate",
    "statistical_ml__linear_regression_regularization",
    "statistical_ml__linear_regression_srm",
    "statistical_ml__logistic_regression_glm",
    "statistical_ml__logistic_regression_sigmoid",
    "statistical_ml__logistic_regression_mle",
    "statistical_ml__logistic_regression_gradient_descent",
    "statistical_ml__clustering_evaluation",
    "statistical_ml__kmeans_algorithm",
    "statistical_ml__kmeans_limitations",
    "statistical_ml__clustering_applications",
}


def _kps():
    return load_knowledge_points(KP_PATH)


def _candidate_doc():
    return json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))


def test_stat_ml_knowledge_points_are_registered():
    data = _kps()
    ids = {point["id"] for point in data["knowledge_points"]}
    assert STAT_ML_IDS <= ids
    stat_ml = [
        point for point in data["knowledge_points"] if point["id"] in STAT_ML_IDS
    ]
    assert len(stat_ml) == 17
    assert all(point["module"] == "statistical_ml" for point in stat_ml)
    assert all(point["title_zh"].strip() for point in stat_ml)
    assert all(point["title_en"].strip() for point in stat_ml)


def test_stat_ml_knowledge_point_prerequisites_resolve():
    data = _kps()
    ids = {point["id"] for point in data["knowledge_points"]}
    for point in data["knowledge_points"]:
        if point["id"] in STAT_ML_IDS:
            for prereq in point["prerequisites"]:
                assert prereq in ids


def test_stat_ml_candidate_templates_have_valid_schema():
    doc = _candidate_doc()
    validate_diagnostic_templates(
        {"schema_version": doc["schema_version"], "templates": doc["templates"]},
        valid_concept_ids=STAT_ML_IDS,
        allowed_review_statuses={"candidate_draft"},
    )


def test_stat_ml_candidate_templates_do_not_collide_with_production():
    doc = _candidate_doc()
    production = json.loads(PRODUCTION_PATH.read_text(encoding="utf-8"))
    production_ids = {t["id"] for t in production["templates"]}
    candidate_ids = {t["id"] for t in doc["templates"]}
    assert candidate_ids.isdisjoint(production_ids)


def test_stat_ml_candidate_templates_cover_each_concept():
    doc = _candidate_doc()
    covered = {concept for t in doc["templates"] for concept in t["concept_ids"]}
    assert covered <= STAT_ML_IDS


def test_stat_ml_candidate_templates_are_candidate_draft():
    doc = _candidate_doc()
    assert doc["candidate_status"] == "pending_human_review"
    assert doc["schema_version"] == 1
    for template in doc["templates"]:
        assert template["review_status"] == "candidate_draft"
        assert template["purpose"] == "mastery_verification"
        assert len(template["concept_ids"]) == 1


def _candidate_cases():
    doc = _candidate_doc()
    templates = {t["id"]: t for t in doc["templates"]}
    return [
        (templates[template_id], doc["acceptance_cases"][template_id])
        for template_id in templates
    ]


@pytest.mark.parametrize(
    ("template", "case"),
    _candidate_cases(),
    ids=[t["id"] for t in _candidate_doc()["templates"]],
)
def test_stat_ml_candidate_scorers_pass_correct_reject_wrong_and_malformed(
    template, case
):
    positive = score_verification_answer(
        template=template, answer=copy.deepcopy(case["correct_answer"])
    )
    assert (positive["score"], positive["passed"]) == (1.0, True)

    negative = score_verification_answer(
        template=template, answer=copy.deepcopy(case["wrong_answer"])
    )
    assert (negative["score"], negative["passed"]) == (0.0, False)

    with pytest.raises(VerificationDiagnosticError):
        score_verification_answer(
            template=template, answer=copy.deepcopy(case["malformed_answer"])
        )


@pytest.mark.parametrize(
    "template",
    [t for t in _candidate_doc()["templates"]],
    ids=[t["id"] for t in _candidate_doc()["templates"]],
)
def test_stat_ml_candidate_templates_stay_out_of_production_verification(
    template,
):
    # candidate_draft templates are not yet human_verified, so the production
    # verification service must refuse them until owner promotion.
    with pytest.raises(VerificationDiagnosticError):
        VerificationDiagnosticService(templates=[template])
