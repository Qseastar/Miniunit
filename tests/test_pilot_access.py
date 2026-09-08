from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from introai_tutor.pilot_access import (
    ACCESS_GRANTED_KEY,
    ACCESS_PENDING_CLEAR_KEY,
    PilotAccessError,
    access_code_status,
    access_input_key,
    build_access_policy,
    compare_access_code,
    grant_access,
    is_access_granted,
    logout_access,
    public_access_error,
    public_configuration_error,
    request_input_clear,
    validate_access_code,
)
from introai_tutor.ui_formatting import reset_session_state
from introai_tutor.pilot_feedback import FREE_TEXT_FIELDS, RATING_FIELDS, build_feedback_payload
from introai_tutor.pilot_tasks import load_pilot_tasks


ROOT = Path(__file__).resolve().parents[1]
VALID_CODE = "pilot-access-2026"


@pytest.mark.parametrize("value", [None, "", "short", "x" * 129, "line\nbreak"])
def test_access_code_validation_rejects_empty_short_long_or_control_values(value):
    with pytest.raises(PilotAccessError):
        validate_access_code(value)


def test_access_code_status_exposes_only_presence_and_validity():
    assert access_code_status("") == (False, False)
    assert access_code_status("short") == (True, False)
    assert access_code_status(VALID_CODE) == (True, True)


def test_access_comparison_is_exact_and_never_stores_the_code(monkeypatch):
    calls = []
    monkeypatch.setattr("introai_tutor.pilot_access.secrets.compare_digest", lambda left, right: calls.append((left, right)) or left == right)
    assert compare_access_code(VALID_CODE, VALID_CODE) is True
    assert compare_access_code("pilot-access-2027", VALID_CODE) is False
    assert calls == [(VALID_CODE, VALID_CODE), ("pilot-access-2027", VALID_CODE)]
    state = {}
    grant_access(state)
    assert state == {ACCESS_GRANTED_KEY: True}
    assert VALID_CODE not in repr(state)


def test_policy_modes_are_explicit_and_non_loopback_requires_valid_code():
    ordinary = build_access_policy(pilot_mode=False, access_code=None, host="127.0.0.1")
    assert ordinary.access_required is False
    local_fallback = build_access_policy(pilot_mode=True, access_code=None, host="localhost")
    assert local_fallback.local_no_code_fallback is True
    assert local_fallback.access_required is False
    protected_local = build_access_policy(pilot_mode=True, access_code=VALID_CODE, host="127.0.0.1")
    assert protected_local.access_required is True
    protected_lan = build_access_policy(pilot_mode=True, access_code=VALID_CODE, host="0.0.0.0")
    assert protected_lan.access_required is True
    assert protected_lan.access_code_valid is True
    unprotected_lan = build_access_policy(pilot_mode=True, access_code=None, host="0.0.0.0")
    assert unprotected_lan.access_required is True
    assert unprotected_lan.access_code_valid is False


def test_session_marker_logout_and_input_clear_are_minimal_and_reversible():
    state = {"introai_learner_state": {"mastery": {}}, "unrelated": "keep"}
    grant_access(state)
    assert is_access_granted(state) is True
    first_key = access_input_key(state)
    state[first_key] = VALID_CODE
    request_input_clear(state, first_key)
    assert state[ACCESS_PENDING_CLEAR_KEY] == first_key
    second_key = access_input_key(state)
    assert second_key != first_key
    assert state[first_key] == ""
    logout_access(state)
    assert is_access_granted(state) is False
    assert state["introai_learner_state"] == {"mastery": {}}
    assert state["unrelated"] == "keep"


def test_learner_reset_does_not_logout_pilot_access():
    state = {ACCESS_GRANTED_KEY: True, "introai_learner_state": {"mastery": {}}}
    reset_session_state(state)
    assert state[ACCESS_GRANTED_KEY] is True


def test_access_code_is_absent_from_feedback_payload_and_public_errors():
    tasks_data = load_pilot_tasks(ROOT / "data" / "pilot_search_algorithms_tasks.json")
    payload = build_feedback_payload(
        tasks_data=tasks_data,
        tester_code="G-ABC123",
        completed_task_ids=[],
        ratings={field: 3 for field in RATING_FIELDS},
        free_text_feedback={field: "" for field in FREE_TEXT_FIELDS},
        generated_at_utc="2026-08-04T00:00:00Z",
    )
    assert VALID_CODE not in repr(payload)
    assert VALID_CODE not in public_access_error()
    assert VALID_CODE not in public_configuration_error()


def _access_app(monkeypatch, db_path=None):
    monkeypatch.setenv("INTROAI_PILOT_MODE", "1")
    monkeypatch.setenv("INTROAI_PILOT_ACCESS_CODE", VALID_CODE)
    monkeypatch.setenv("INTROAI_PILOT_HOST", "127.0.0.1")
    if db_path is not None:
        monkeypatch.setenv("INTROAI_STATE_DB", str(db_path))
    app = AppTest.from_file(ROOT / "app.py", default_timeout=10)
    app.run()
    assert not app.exception
    return app


def test_unauthenticated_app_stops_before_uuid_profile_or_service_initialization(monkeypatch):
    app = _access_app(monkeypatch)
    assert "introai_pilot_access_granted" not in app.session_state
    assert "introai_learner_id" not in app.session_state
    assert "introai_learner_state" not in app.session_state
    assert "introai_qa_service" not in app.session_state
    assert "introai_dual_track_session" not in app.session_state
    assert any("内测访问" in item.value for item in app.title)
    assert [tab.label for tab in app.tabs] == []


def test_wrong_code_is_generic_and_success_clears_input_then_initializes_one_profile(monkeypatch, tmp_path):
    database_path = tmp_path / "state.sqlite3"
    app = _access_app(monkeypatch, database_path)
    key = app.text_input[0].key
    app.text_input(key=key).input("wrong-access-code")
    app.button(key="FormSubmitter:introai_pilot_access_form-进入内测").click()
    app.run()
    assert not app.exception
    assert "introai_learner_state" not in app.session_state
    assert any("访问码无效" in item.value for item in app.error)
    next_key = app.text_input[0].key
    assert next_key != key
    app.text_input(key=next_key).input(VALID_CODE)
    app.button(key="FormSubmitter:introai_pilot_access_form-进入内测").click()
    app.run()
    assert not app.exception
    assert app.session_state[ACCESS_GRANTED_KEY] is True
    assert "introai_learner_id" in app.session_state
    assert isinstance(app.session_state["introai_learner_id"], str)
    assert "introai_learner_state" in app.session_state
    assert isinstance(app.session_state["introai_learner_state"], dict)
    qa_areas = [area for area in app.text_area if area.label == "输入课程问题"]
    assert len(qa_areas) == 1
    assert qa_areas[0].value == ""
    assert qa_areas[0].key.startswith("introai_qa_question_")
    assert VALID_CODE not in repr(app.session_state)
    if database_path.exists():
        assert VALID_CODE.encode("utf-8") not in database_path.read_bytes()


def test_logout_relocks_without_deleting_profile(monkeypatch):
    """The logout transition clears app state but preserves the profile URL."""
    from app import _consume_pilot_logout_request

    class FakeStreamlit:
        def __init__(self):
            self.session_state = {
                "introai_pilot_access_logout_requested": True,
                ACCESS_GRANTED_KEY: True,
                "introai_learner_id": "learner-a",
                "introai_learner_state": {"mastery": {}},
                "introai_pilot_access_code_0": VALID_CODE,
                "unrelated": "keep",
            }

    fake = FakeStreamlit()
    _consume_pilot_logout_request(fake)
    assert ACCESS_GRANTED_KEY not in fake.session_state
    assert "introai_learner_state" not in fake.session_state
    assert fake.session_state["introai_pilot_access_code_0"] == ""
    assert fake.session_state["unrelated"] == "keep"


def test_new_streamlit_session_does_not_inherit_access_marker(monkeypatch, tmp_path):
    first = _access_app(monkeypatch, tmp_path / "state.sqlite3")
    assert ACCESS_GRANTED_KEY not in first.session_state
    second = _access_app(monkeypatch, tmp_path / "state.sqlite3")
    assert ACCESS_GRANTED_KEY not in second.session_state


def test_two_authenticated_streamlit_sessions_get_distinct_profiles(monkeypatch, tmp_path):
    first = _access_app(monkeypatch, tmp_path / "state.sqlite3")
    first_key = first.text_input[0].key
    first.text_input(key=first_key).input(VALID_CODE)
    first.button(key="FormSubmitter:introai_pilot_access_form-进入内测").click()
    first.run()
    first_id = first.session_state["introai_learner_id"]

    second = _access_app(monkeypatch, tmp_path / "state.sqlite3")
    second_key = second.text_input[0].key
    second.text_input(key=second_key).input(VALID_CODE)
    second.button(key="FormSubmitter:introai_pilot_access_form-进入内测").click()
    second.run()
    second_id = second.session_state["introai_learner_id"]

    assert first_id != second_id
