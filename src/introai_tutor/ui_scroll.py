"""Small, one-shot scroll state helpers for the Streamlit UI.

The state is deliberately session-local: learner persistence must never
restore a previous browser scroll request.
"""

from __future__ import annotations

import re
from typing import Any


SCROLL_REQUEST_KEY = "introai_scroll_request"
SCROLL_CONSUMED_EVENTS_KEY = "introai_scroll_consumed_events"
SCROLL_TARGETS = frozenset(
    {
        "qa_input",
        "qa_citation_preview",
        "diagnostic_handoff",
        "diagnostic_question",
        "diagnostic_completion",
        "mastery_map",
        "mastery_map_overview",
        "mastery_map_graph",
        "mastery_map_detail",
    }
)
_EVENT_ID = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,119}$")


def request_scroll(session_state: Any, *, target: str, event_id: str) -> bool:
    """Record one approved scroll event, returning whether it was newly queued."""
    if not hasattr(session_state, "get") or not hasattr(session_state, "__setitem__"):
        raise ValueError("session_state must be a mutable mapping.")
    _validate_target(target)
    _validate_event_id(event_id)
    consumed = _consumed_events(session_state)
    pending = session_state.get(SCROLL_REQUEST_KEY)
    if event_id in consumed or (
        isinstance(pending, dict) and pending.get("event_id") == event_id
    ):
        return False
    session_state[SCROLL_REQUEST_KEY] = {"target": target, "event_id": event_id}
    return True


def consume_scroll_request(session_state: Any) -> dict[str, str] | None:
    """Consume a valid request exactly once; malformed transient state is ignored."""
    if not hasattr(session_state, "pop"):
        raise ValueError("session_state must be a mutable mapping.")
    request = session_state.pop(SCROLL_REQUEST_KEY, None)
    if not isinstance(request, dict) or set(request) != {"target", "event_id"}:
        return None
    target, event_id = request["target"], request["event_id"]
    try:
        _validate_target(target)
        _validate_event_id(event_id)
    except ValueError:
        return None
    consumed = _consumed_events(session_state)
    if event_id in consumed:
        return None
    consumed.append(event_id)
    session_state[SCROLL_CONSUMED_EVENTS_KEY] = consumed
    return {"target": target, "event_id": event_id}


def clear_scroll_state(session_state: Any) -> None:
    """Remove transient scroll state without touching learner or QA data."""
    if not hasattr(session_state, "pop"):
        raise ValueError("session_state must be a mutable mapping.")
    session_state.pop(SCROLL_REQUEST_KEY, None)
    session_state.pop(SCROLL_CONSUMED_EVENTS_KEY, None)


def scroll_anchor_markup(target: str) -> str:
    """Return a fixed, safe anchor for a whitelisted scroll target."""
    _validate_target(target)
    return f'<div id="introai-scroll-{target}" aria-hidden="true"></div>'


def scroll_component_key(event_id: str) -> str:
    """Return a stable-per-event component identity for a scroll iframe.

    ``components.v1.html`` does not accept a key. Rendering it inside this
    keyed transient container makes each approved event a fresh frontend
    element, so a later request for the same anchor runs its script again.
    """
    _validate_event_id(event_id)
    return f"introai-scroll-event-{event_id}"


def scroll_script_markup(
    target: str,
    *,
    event_id: str | None = None,
    activate_diagnostic_tab: bool = False,
    activate_tab_index: int | None = None,
) -> str:
    """Return a safe one-shot script with an optional unique component payload.

    When an event ID is supplied, it is embedded only after the strict local
    validator accepts it.  This makes two approved requests for the same
    anchor produce different Streamlit component payloads, so the iframe is
    remounted and its scroll script runs again after a later explicit click.
    """
    _validate_target(target)
    if event_id is not None:
        _validate_event_id(event_id)
    if activate_tab_index is not None and (
        isinstance(activate_tab_index, bool)
        or not isinstance(activate_tab_index, int)
        or activate_tab_index < 0
    ):
        raise ValueError("activate_tab_index must be a non-negative integer or None.")
    if activate_diagnostic_tab and activate_tab_index is not None:
        raise ValueError("Specify only one tab activation option.")
    activate = ""
    if activate_diagnostic_tab:
        activate = """
        const diagnosticTab = Array.from(parentDocument.querySelectorAll('[role="tab"]'))
          .find((tab) => tab.textContent.trim() === "诊断学习");
        if (diagnosticTab && diagnosticTab.getAttribute("aria-selected") !== "true") {
          diagnosticTab.click();
        }
        """
    elif activate_tab_index is not None:
        activate = f"""
        const targetTab = parentDocument.querySelectorAll('[role="tab"]')[{activate_tab_index}];
        if (targetTab && targetTab.getAttribute("aria-selected") !== "true") {{
          targetTab.click();
        }}
        """
    event_marker = "" if event_id is None else f' data-introai-scroll-event="{event_id}"'
    return f"""<!doctype html><html><body{event_marker}><script>
    (() => {{
      try {{
        const parentDocument = window.parent && window.parent.document;
        if (!parentDocument) return;
        {activate}
        const anchor = parentDocument.getElementById("introai-scroll-{target}");
        if (!anchor) return;
        const reduceMotion = window.parent.matchMedia
          && window.parent.matchMedia("(prefers-reduced-motion: reduce)").matches;
        anchor.scrollIntoView({{behavior: reduceMotion ? "auto" : "smooth", block: "start"}});
      }} catch (_error) {{
        // Scroll is progressive enhancement; the learning flow remains usable.
      }}
    }})();
    </script></body></html>"""


def _consumed_events(session_state: Any) -> list[str]:
    value = session_state.get(SCROLL_CONSUMED_EVENTS_KEY, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        value = []
    return list(value)


def _validate_target(target: Any) -> None:
    if not isinstance(target, str) or target not in SCROLL_TARGETS:
        raise ValueError("scroll target is invalid.")


def _validate_event_id(event_id: Any) -> None:
    if not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id):
        raise ValueError("scroll event_id is invalid.")
