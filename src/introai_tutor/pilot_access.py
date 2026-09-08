"""Small, session-only access gate for the hosted internal pilot.

This is an access code for a short, owner-supervised pilot, not an account or
identity system.  The code is read from process configuration and is never
returned, persisted, logged, or placed in a URL.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
import secrets
from typing import Any, MutableMapping

from introai_tutor.pilot_mode import is_pilot_mode_enabled


PILOT_ACCESS_CODE_ENV = "INTROAI_PILOT_ACCESS_CODE"
PILOT_HOST_ENV = "INTROAI_PILOT_HOST"
ACCESS_GRANTED_KEY = "introai_pilot_access_granted"
ACCESS_INPUT_REVISION_KEY = "introai_pilot_access_input_revision"
ACCESS_PENDING_CLEAR_KEY = "introai_pilot_access_pending_clear"
ACCESS_ERROR_KEY = "introai_pilot_access_error"
MIN_ACCESS_CODE_LENGTH = 12
MAX_ACCESS_CODE_LENGTH = 128
DEFAULT_PILOT_HOST = "127.0.0.1"


class PilotAccessError(ValueError):
    """Raised when access configuration or session state is malformed."""


@dataclass(frozen=True)
class PilotAccessPolicy:
    """Validated policy summary that intentionally contains no secret value."""

    pilot_enabled: bool
    host: str
    host_is_loopback: bool
    access_code_present: bool
    access_code_valid: bool
    access_required: bool
    local_no_code_fallback: bool


def validate_access_code(value: Any) -> str:
    """Validate and normalize a configured or submitted code locally."""
    if not isinstance(value, str):
        raise PilotAccessError("pilot access code configuration is invalid.")
    normalized = value.strip()
    if not MIN_ACCESS_CODE_LENGTH <= len(normalized) <= MAX_ACCESS_CODE_LENGTH:
        raise PilotAccessError("pilot access code configuration is invalid.")
    if any(not character.isprintable() or character in "\r\n\t" for character in normalized):
        raise PilotAccessError("pilot access code configuration is invalid.")
    return normalized


def access_code_status(value: Any) -> tuple[bool, bool]:
    """Return only presence and validity; never return the code itself."""
    present = isinstance(value, str) and bool(value.strip())
    if not present:
        return False, False
    try:
        validate_access_code(value)
    except PilotAccessError:
        return True, False
    return True, True


def normalize_host(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PilotAccessError("pilot bind host is invalid.")
    host = value.strip()
    if any(character.isspace() for character in host):
        raise PilotAccessError("pilot bind host is invalid.")
    return host


def is_loopback_host(value: Any) -> bool:
    """Return whether a bind host is explicitly local-only."""
    try:
        host = normalize_host(value)
    except PilotAccessError:
        return False
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_access_policy(
    *,
    pilot_mode: Any,
    access_code: Any,
    host: Any = DEFAULT_PILOT_HOST,
) -> PilotAccessPolicy:
    """Derive the access boundary without exposing configuration values."""
    if isinstance(pilot_mode, str):
        enabled = is_pilot_mode_enabled(pilot_mode)
    elif isinstance(pilot_mode, bool):
        enabled = pilot_mode
    else:
        enabled = False
    normalized_host = normalize_host(host)
    loopback = is_loopback_host(normalized_host)
    present, valid = access_code_status(access_code)
    if not enabled:
        required = False
        local_fallback = False
    elif valid:
        required = True
        local_fallback = False
    elif present:
        # A malformed configured value is never silently treated as open,
        # including on localhost.
        required = True
        local_fallback = False
    elif loopback:
        # Explicitly supported owner-only localhost development mode.
        required = False
        local_fallback = True
    else:
        required = True
        local_fallback = False
    return PilotAccessPolicy(
        pilot_enabled=enabled,
        host=normalized_host,
        host_is_loopback=loopback,
        access_code_present=present,
        access_code_valid=valid,
        access_required=required,
        local_no_code_fallback=local_fallback,
    )


def policy_from_environment(
    *,
    pilot_mode: str | None = None,
    access_code: str | None = None,
    host: str | None = None,
) -> PilotAccessPolicy:
    """Build policy from named environment values without logging them."""
    if pilot_mode is None:
        pilot_mode = os.environ.get("INTROAI_PILOT_MODE")
    if access_code is None:
        access_code = os.environ.get(PILOT_ACCESS_CODE_ENV)
    if host is None:
        host = os.environ.get(PILOT_HOST_ENV, DEFAULT_PILOT_HOST)
    return build_access_policy(pilot_mode=pilot_mode, access_code=access_code, host=host)


def configured_access_code() -> str | None:
    """Read the configured code for one in-memory comparison only."""
    return os.environ.get(PILOT_ACCESS_CODE_ENV)


def compare_access_code(submitted: Any, configured: Any) -> bool:
    """Compare only validated strings with constant-time comparison."""
    if not isinstance(submitted, str) or not isinstance(configured, str):
        return False
    try:
        submitted_value = validate_access_code(submitted)
        configured_value = validate_access_code(configured)
    except PilotAccessError:
        return False
    return secrets.compare_digest(submitted_value, configured_value)


def is_access_granted(session_state: MutableMapping[str, Any]) -> bool:
    value = session_state.get(ACCESS_GRANTED_KEY)
    if not isinstance(value, bool):
        if value is not None:
            session_state.pop(ACCESS_GRANTED_KEY, None)
        return False
    return value


def grant_access(session_state: MutableMapping[str, Any]) -> None:
    session_state[ACCESS_GRANTED_KEY] = True


def logout_access(session_state: MutableMapping[str, Any]) -> None:
    """Clear only authentication/session markers, never the learner database."""
    session_state.pop(ACCESS_GRANTED_KEY, None)
    session_state.pop(ACCESS_ERROR_KEY, None)
    session_state.pop(ACCESS_PENDING_CLEAR_KEY, None)
    session_state.pop(ACCESS_INPUT_REVISION_KEY, None)


def access_input_key(session_state: MutableMapping[str, Any]) -> str:
    """Return a deterministic input key whose revision can clear submitted text."""
    revision = session_state.get(ACCESS_INPUT_REVISION_KEY, 0)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        revision = 0
        session_state[ACCESS_INPUT_REVISION_KEY] = revision
    pending = session_state.pop(ACCESS_PENDING_CLEAR_KEY, None)
    if pending is not None:
        # Keep an old Streamlit widget key addressable for the current rerun,
        # but erase its value.  Removing a live widget key before Streamlit
        # collects widget state can make a rerun fail; empty stale keys never
        # retain the submitted access code.
        old_key = str(pending)
        if old_key in session_state:
            session_state[old_key] = ""
        revision += 1
        session_state[ACCESS_INPUT_REVISION_KEY] = revision
    return f"introai_pilot_access_code_{revision}"


def request_input_clear(session_state: MutableMapping[str, Any], input_key: str) -> None:
    if not isinstance(input_key, str) or not input_key.startswith("introai_pilot_access_code_"):
        raise PilotAccessError("access input key is invalid.")
    session_state[ACCESS_PENDING_CLEAR_KEY] = input_key


def public_access_error() -> str:
    return "访问码无效，请联系负责人获取本次内测访问码。"


def public_configuration_error() -> str:
    return "内测访问暂不可用，请联系负责人检查访问配置。"


def configuration_is_safe_for_host(policy: PilotAccessPolicy) -> bool:
    """Whether the requested bind can safely proceed under P4c rules."""
    if not policy.pilot_enabled:
        return policy.host_is_loopback
    return policy.host_is_loopback or policy.access_code_valid
