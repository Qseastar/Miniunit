from introai_tutor.pilot_feedback import FREE_TEXT_FIELDS, RATING_FIELDS
from introai_tutor.pilot_feedback_ui import (
    ANONYMOUS_CODE_KEY,
    DOWNLOAD_FILENAME_KEY,
    FORM_REVISION_KEY,
    PREPARED_PAYLOAD_KEY,
    RESET_FLASH_KEY,
    SERIALIZED_PAYLOAD_KEY,
    consume_reset_flash,
    current_form_revision,
    ensure_anonymous_tester_code,
    generate_anonymous_tester_code,
    pilot_widget_inventory,
    reset_pilot_feedback_form,
    validate_anonymous_tester_code,
)


TASK_IDS = (
    "course_question_answering",
    "reviewed_diagnostic",
    "mastery_map",
    "map_to_learning_action",
    "persistent_learning_state",
    "repeat_practice",
)


def _chooser(characters):
    values = iter(characters)
    return lambda _: next(values)


def test_anonymous_code_has_safe_format_and_does_not_derive_from_learner_state():
    state = {"introai_learner_id": "01234567-89ab-cdef-0123-456789abcdef"}

    code = ensure_anonymous_tester_code(
        state, chooser=_chooser("ABCDEF")
    )

    assert code == "G-ABCDEF"
    assert validate_anonymous_tester_code(code) == code
    assert not set("O0IL1").intersection(code)
    assert "01234567" not in code
    assert state[ANONYMOUS_CODE_KEY] == code


def test_code_is_stable_for_one_session_and_new_sessions_can_have_new_codes():
    first = {}
    second = {}

    assert ensure_anonymous_tester_code(first, chooser=_chooser("ABCDEF")) == "G-ABCDEF"
    assert ensure_anonymous_tester_code(first, chooser=_chooser("ZZZZZZ")) == "G-ABCDEF"
    assert ensure_anonymous_tester_code(second, chooser=_chooser("BCDEFG")) == "G-BCDEFG"


def test_widget_inventory_contains_exactly_six_tasks_eight_ratings_and_five_feedback_fields():
    inventory = pilot_widget_inventory(task_ids=TASK_IDS, revision=4)

    assert set(inventory["tasks"]) == set(TASK_IDS)
    assert set(inventory["ratings"]) == set(RATING_FIELDS)
    assert set(inventory["free_text"]) == set(FREE_TEXT_FIELDS)
    assert len(set(inventory["tasks"].values())) == 6
    assert all(key.startswith("introai_pilot_form_4_") for key in inventory["tasks"].values())


def test_reset_clears_only_pilot_form_state_and_creates_a_new_code_and_revision():
    old_inventory = pilot_widget_inventory(task_ids=TASK_IDS, revision=0)
    state = {
        ANONYMOUS_CODE_KEY: "G-ABCDEF",
        PREPARED_PAYLOAD_KEY: {"schema_version": 1},
        SERIALIZED_PAYLOAD_KEY: b"{}\n",
        DOWNLOAD_FILENAME_KEY: "old.json",
        "introai_learner_state": {"mastery": {"breadth_first_search": 0.4}},
        "introai_last_recommendation": {"concept_id": "uniform_cost_search"},
        "introai_dual_track_session": {"phase": "verification"},
        "introai_pilot_task_course_question_answering": True,
        "introai_pilot_rating_qa_clarity": 5,
        **{key: "old" for key in old_inventory["tasks"].values()},
        **{key: 5 for key in old_inventory["ratings"].values()},
        **{key: "old" for key in old_inventory["free_text"].values()},
    }

    new_code = reset_pilot_feedback_form(state, chooser=_chooser("BCDEFG"))

    assert new_code == "G-BCDEFG"
    assert state[FORM_REVISION_KEY] == 1
    assert current_form_revision(state) == 1
    assert state[ANONYMOUS_CODE_KEY] == new_code
    assert all(key not in state for key in old_inventory["tasks"].values())
    assert all(key not in state for key in old_inventory["ratings"].values())
    assert all(key not in state for key in old_inventory["free_text"].values())
    assert PREPARED_PAYLOAD_KEY not in state
    assert SERIALIZED_PAYLOAD_KEY not in state
    assert DOWNLOAD_FILENAME_KEY not in state
    assert "introai_pilot_task_course_question_answering" not in state
    assert "introai_pilot_rating_qa_clarity" not in state
    assert state["introai_learner_state"]["mastery"]["breadth_first_search"] == 0.4
    assert state["introai_last_recommendation"]["concept_id"] == "uniform_cost_search"
    assert state["introai_dual_track_session"]["phase"] == "verification"
    assert consume_reset_flash(state) == "反馈表已重置，已生成新的匿名测试编号。"
    assert RESET_FLASH_KEY not in state
    assert consume_reset_flash(state) is None


def test_generate_rejects_an_invalid_injected_chooser_value():
    try:
        generate_anonymous_tester_code(chooser=lambda _: "O")
    except ValueError:
        pass
    else:
        raise AssertionError("ambiguous anonymous-code character was accepted")
