"""Anonymous, local learner-profile identifiers for the Streamlit MVP."""

from __future__ import annotations

import uuid
from collections.abc import MutableMapping
from typing import Any


LEARNER_QUERY_PARAM = "learner"


def new_learner_id() -> str:
    """Return a random UUID with no user or device information."""
    return str(uuid.uuid4())


def normalize_learner_id(value: Any) -> str | None:
    """Accept only canonical UUID values used solely as database keys."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = uuid.UUID(value.strip())
    except (ValueError, AttributeError):
        return None
    canonical = str(parsed)
    return canonical if value.strip().lower() == canonical else None


def resolve_learner_id(query_params: MutableMapping[str, Any]) -> tuple[str, bool]:
    """Read or create the anonymous ID retained in query parameters.

    Returns ``(learner_id, created_or_replaced)``.  The parameter is never
    used as a path, SQL fragment, or identity credential.
    """
    value = query_params.get(LEARNER_QUERY_PARAM)
    if isinstance(value, list):
        value = value[0] if len(value) == 1 else None
    learner_id = normalize_learner_id(value)
    if learner_id is not None:
        return learner_id, False
    learner_id = new_learner_id()
    query_params[LEARNER_QUERY_PARAM] = learner_id
    return learner_id, True


def start_new_profile(query_params: MutableMapping[str, Any]) -> str:
    """Switch this browser URL to a fresh local anonymous profile."""
    learner_id = new_learner_id()
    query_params[LEARNER_QUERY_PARAM] = learner_id
    return learner_id
