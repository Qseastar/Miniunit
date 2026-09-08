"""Default-off configuration for the internal pilot interface."""

from __future__ import annotations

import os


PILOT_MODE_ENV = "INTROAI_PILOT_MODE"
_TRUE_VALUES = frozenset({"1", "true", "on", "yes"})


def is_pilot_mode_enabled(value: str | None = None) -> bool:
    """Return whether the explicitly opt-in pilot UI should be shown.

    Unknown values fail closed.  Passing ``value`` keeps tests independent of
    process environment while production callers use only the named variable.
    """
    if value is None:
        value = os.environ.get(PILOT_MODE_ENV)
    return isinstance(value, str) and value.strip().casefold() in _TRUE_VALUES
