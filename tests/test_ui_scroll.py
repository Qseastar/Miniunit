"""Offline contracts for intentional, one-shot Streamlit scroll requests."""

from __future__ import annotations

from contextlib import nullcontext

import pytest
import streamlit.components.v1 as components

import app as streamlit_app
from introai_tutor.ui_formatting import reset_session_state

from introai_tutor.ui_scroll import (
    SCROLL_CONSUMED_EVENTS_KEY,
    SCROLL_REQUEST_KEY,
    clear_scroll_state,
    consume_scroll_request,
    request_scroll,
    scroll_anchor_markup,
    scroll_component_key,
    scroll_script_markup,
)


def test_request_and_consume_are_one_shot_and_new_events_remain_available():
    state = {}

    assert request_scroll(state, target="diagnostic_question", event_id="verification-1-a") is True
    assert request_scroll(state, target="diagnostic_question", event_id="verification-1-a") is False
    assert consume_scroll_request(state) == {
        "target": "diagnostic_question", "event_id": "verification-1-a"
    }
    assert SCROLL_REQUEST_KEY not in state
    assert consume_scroll_request(state) is None
    assert request_scroll(state, target="diagnostic_question", event_id="verification-1-a") is False
    assert request_scroll(state, target="diagnostic_question", event_id="verification-2-b") is True


def test_ordinary_reruns_hints_and_reveals_do_not_create_scroll_requests():
    state = {"introai_learner_state": {"mastery": {}}, "introai_formative_feedback_error": True}

    assert consume_scroll_request(state) is None
    assert SCROLL_REQUEST_KEY not in state
    assert state["introai_learner_state"] == {"mastery": {}}


def test_return_and_profile_cleanup_remove_transient_scroll_state_only():
    state = {
        "introai_learner_state": {"mastery": {"uniform_cost_search": 0.35}},
        SCROLL_REQUEST_KEY: {"target": "qa_input", "event_id": "return-to-qa"},
        SCROLL_CONSUMED_EVENTS_KEY: ["diagnostic-completion"],
    }

    clear_scroll_state(state)

    assert SCROLL_REQUEST_KEY not in state
    assert SCROLL_CONSUMED_EVENTS_KEY not in state
    assert state["introai_learner_state"] == {"mastery": {"uniform_cost_search": 0.35}}


def test_new_profile_reset_cannot_inherit_an_old_scroll_request():
    state = {
        "other_page_key": "preserved",
        "introai_learner_state": {"mastery": {"breadth_first_search": 0.6}},
        SCROLL_REQUEST_KEY: {"target": "diagnostic_question", "event_id": "verification-1-a"},
        SCROLL_CONSUMED_EVENTS_KEY: ["qa-explicit-diagnostic-1"],
    }

    reset_session_state(state)

    assert state == {"other_page_key": "preserved"}


@pytest.mark.parametrize("target", ["", "student answer", "diagnostic_question<script>", "unknown_target"])
def test_invalid_or_user_derived_scroll_targets_fail_closed(target):
    with pytest.raises(ValueError, match="scroll target"):
        request_scroll({}, target=target, event_id="safe-event")
    with pytest.raises(ValueError, match="scroll target"):
        scroll_anchor_markup(target)


@pytest.mark.parametrize("event_id", ["", "question text from a learner", "bad<script>", True])
def test_invalid_event_ids_fail_closed(event_id):
    with pytest.raises(ValueError, match="scroll event_id"):
        request_scroll({}, target="qa_input", event_id=event_id)


def test_anchor_and_script_use_only_fixed_target_and_respect_reduced_motion():
    anchor = scroll_anchor_markup("diagnostic_completion")
    script = scroll_script_markup("diagnostic_completion", activate_diagnostic_tab=True)

    assert anchor == '<div id="introai-scroll-diagnostic_completion" aria-hidden="true"></div>'
    assert "introai-scroll-diagnostic_completion" in script
    assert "scrollIntoView" in script
    assert "prefers-reduced-motion" in script
    assert "[role=\"tab\"]" in script
    assert "<script>" not in anchor


def test_mastery_map_target_can_activate_only_the_fixed_third_tab():
    state = {}
    assert request_scroll(
        state, target="mastery_map", event_id="verification-completion-mastery-map"
    ) is True
    assert consume_scroll_request(state) == {
        "target": "mastery_map",
        "event_id": "verification-completion-mastery-map",
    }

    script = scroll_script_markup("mastery_map", activate_tab_index=2)
    assert "querySelectorAll('[role=\"tab\"]')[2]" in script
    with pytest.raises(ValueError, match="only one tab"):
        scroll_script_markup(
            "mastery_map", activate_diagnostic_tab=True, activate_tab_index=2
        )


@pytest.mark.parametrize(
    "target",
    [
        "mastery_map_overview",
        "mastery_map_graph",
        "mastery_map_detail",
        "qa_citation_preview",
    ],
)
def test_mastery_map_overview_and_detail_targets_are_fixed_whitelist_anchors(target):
    state = {}
    assert request_scroll(state, target=target, event_id=f"mastery-map-action-{target[-1]}")
    assert consume_scroll_request(state) == {
        "target": target,
        "event_id": f"mastery-map-action-{target[-1]}",
    }
    assert scroll_anchor_markup(target) == (
        f'<div id="introai-scroll-{target}" aria-hidden="true"></div>'
    )


def test_qa_citation_preview_can_scroll_more_than_once_without_user_derived_anchors():
    state = {}

    for event_id in ("qa-citation-preview-4-1", "qa-citation-preview-4-2"):
        assert request_scroll(
            state, target="qa_citation_preview", event_id=event_id
        )
        assert consume_scroll_request(state) == {
            "target": "qa_citation_preview",
            "event_id": event_id,
        }

    assert scroll_anchor_markup("qa_citation_preview") == (
        '<div id="introai-scroll-qa_citation_preview" aria-hidden="true"></div>'
    )


def test_new_map_action_events_can_scroll_the_same_target_more_than_once():
    state = {}

    assert request_scroll(
        state, target="mastery_map_detail", event_id="mastery-map-action-1"
    )
    assert consume_scroll_request(state) is not None
    assert request_scroll(
        state, target="mastery_map_detail", event_id="mastery-map-action-2"
    )
    assert consume_scroll_request(state) == {
        "target": "mastery_map_detail",
        "event_id": "mastery-map-action-2",
    }
    assert consume_scroll_request(state) is None


def test_new_event_tokens_produce_distinct_component_payloads_for_the_same_anchor():
    first = scroll_script_markup(
        "mastery_map_detail", event_id="mastery-map-action-1", activate_tab_index=2
    )
    second = scroll_script_markup(
        "mastery_map_detail", event_id="mastery-map-action-2", activate_tab_index=2
    )

    assert first != second
    assert 'data-introai-scroll-event="mastery-map-action-1"' in first
    assert 'data-introai-scroll-event="mastery-map-action-2"' in second
    assert "introai-scroll-mastery_map_detail" in first
    assert "scrollIntoView" in second
    with pytest.raises(ValueError, match="scroll event_id"):
        scroll_script_markup("mastery_map_detail", event_id="bad<script>")


def test_new_scroll_events_use_distinct_safe_component_keys_for_the_same_anchor():
    first = scroll_component_key("mastery-map-action-1")
    second = scroll_component_key("mastery-map-action-2")

    assert first == "introai-scroll-event-mastery-map-action-1"
    assert second == "introai-scroll-event-mastery-map-action-2"
    assert first != second
    with pytest.raises(ValueError, match="scroll event_id"):
        scroll_component_key("bad<script>")


class _ScrollRenderStreamlit:
    def __init__(self, state):
        self.session_state = state
        self.container_keys: list[str] = []

    def container(self, *, key):
        self.container_keys.append(key)
        return nullcontext()


def test_pending_scroll_uses_a_new_keyed_iframe_for_each_explicit_map_action(monkeypatch):
    state = {}
    rendered: list[tuple[str, dict]] = []
    st = _ScrollRenderStreamlit(state)

    def _fake_html(body, **kwargs):
        rendered.append((body, kwargs))

    monkeypatch.setattr(components, "html", _fake_html)
    for event_id in ("mastery-map-action-1", "mastery-map-action-2"):
        assert request_scroll(state, target="mastery_map_detail", event_id=event_id)
        streamlit_app._render_pending_scroll(st)

    assert st.container_keys == [
        "introai-scroll-event-mastery-map-action-1",
        "introai-scroll-event-mastery-map-action-2",
    ]
    assert len(rendered) == 2
    assert all(kwargs == {"height": 0, "width": 0} for _, kwargs in rendered)
    assert 'data-introai-scroll-event="mastery-map-action-1"' in rendered[0][0]
    assert 'data-introai-scroll-event="mastery-map-action-2"' in rendered[1][0]
    assert SCROLL_REQUEST_KEY not in state
    assert state[SCROLL_CONSUMED_EVENTS_KEY] == [
        "mastery-map-action-1",
        "mastery-map-action-2",
    ]


class _StreamlitState:
    def __init__(self):
        self.session_state = {}


def test_explicit_qa_request_and_diagnostic_transitions_queue_only_intended_targets():
    st = _StreamlitState()
    explicit = {"response": {"status": "diagnostic_available"}}
    ordinary = {"response": {"status": "answered"}}
    verification = {
        "phase": "verification",
        "verification": {
            "question": {"step_number": 2, "template_id": "verify_dfs_frontier_choice_v1"}
        },
    }
    completed = {"phase": "completed"}

    assert streamlit_app._is_explicit_diagnostic_result(explicit) is True
    assert streamlit_app._is_explicit_diagnostic_result(ordinary) is False
    assert streamlit_app._request_scroll_for_diagnostic_result(st, verification) is True
    assert consume_scroll_request(st.session_state)["target"] == "diagnostic_question"
    assert streamlit_app._request_scroll_for_diagnostic_result(st, verification) is False
    assert streamlit_app._request_scroll_for_diagnostic_result(st, completed) is True
    assert consume_scroll_request(st.session_state)["target"] == "diagnostic_completion"
