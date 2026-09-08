"""Representative tamper matrix through real session restore and integration."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from introai_tutor.diagnostic_state_integration import (
    DiagnosticStateIntegrationError, DiagnosticStateIntegrationService,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.verification_diagnostics import VerificationDiagnosticError, VerificationDiagnosticService


ROOT = Path(__file__).resolve().parents[1]


def _template():
    return next(item for item in json.loads((ROOT / "data" / "diagnostic_templates.json").read_text(encoding="utf-8"))["templates"] if item["id"] == "verify_bfs_frontier_choice_v1")


def _retry_session():
    template = _template()
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template["id"]])
    retry = service.submit(session=started["session"], answer="C", submitted_template_id=template["id"])
    return service, retry["session"]


@pytest.mark.parametrize("field,mutate", [
    ("submitted_answer", lambda s: s["history"][0].__setitem__("selected_choice_id", "A")),
    ("score", lambda s: s["history"][0].__setitem__("score", 1.0)),
    ("passed", lambda s: s["history"][0].__setitem__("passed", True)),
    ("misconception_ids", lambda s: s["history"][0].__setitem__("misconception_ids", [])),
    ("template_id", lambda s: s["history"][0].__setitem__("template_id", "verify_ucs_min_g_choice_v1")),
    ("primary_concept", lambda s: s["history"][0].__setitem__("concept_ids", ["uniform_cost_search"])),
    ("attempt_order", lambda s: s["history"][0].__setitem__("attempt_number", 2)),
    ("hint_provenance", lambda s: s["history"][0].__setitem__("assisted", True)),
    ("assistance_level", lambda s: s["history"][0].__setitem__("assistance_level", "hint")),
    ("assistance_source", lambda s: s["history"][0].__setitem__("assistance_source", "model_answer")),
    ("active_template_id", lambda s: s.__setitem__("current_template_id", "verify_ucs_min_g_choice_v1")),
    ("attempt_count", lambda s: s.__setitem__("attempt_in_step", 0)),
], ids=["submitted_answer", "score", "passed", "misconception_ids", "template_id", "primary_concept", "attempt_order", "hint_provenance", "assistance_level", "assistance_source", "active_template_id", "attempt_count"])
def test_tampered_session_fields_are_rejected_by_real_restore_validation(field, mutate):
    service, session = _retry_session()
    original = deepcopy(session)
    mutate(session)
    with pytest.raises(VerificationDiagnosticError):
        service.current_question(session=session)
    assert original["history"][0]["score"] == 0.0


@pytest.mark.parametrize("field,mutate", [
    ("purpose", lambda s: s.__setitem__("purpose", "formative")),
    ("evidence_eligible", lambda s: s.__setitem__("evidence_eligible", False)),
    ("summary_concept", lambda s: s["concept_observations"].__setitem__("unknown_concept", [1.0])),
    ("extra_concept", lambda s: s["unobserved_concept_ids"].append("unknown_concept")),
    ("step_count", lambda s: s.__setitem__("passed_steps", 99)),
], ids=["purpose", "evidence_eligible", "summary_concept", "extra_concept", "step_count"])
def test_tampered_completed_summary_is_rejected_before_learner_state_changes(field, mutate):
    template = _template()
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template["id"]])
    completed = service.submit(session=started["session"], answer="A", submitted_template_id=template["id"])
    summary = deepcopy(completed["summary"])
    state = {"student_id": "p2g", "course_id": "intro_ai", "mastery": {}, "misconceptions": [], "learning_evidence": [], "preferred_style": "visual_example"}
    before = deepcopy(state)
    mutate(summary)
    integration = DiagnosticStateIntegrationService(knowledge_data=load_knowledge_points(ROOT / "data" / "knowledge_points.json"), recommendation_fn=lambda *_: None)
    with pytest.raises(DiagnosticStateIntegrationError):
        integration.apply(learner_state=state, diagnostic_summary=summary)
    assert state == before
