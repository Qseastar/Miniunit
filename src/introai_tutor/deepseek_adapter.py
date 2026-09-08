"""Minimal OpenAI-compatible adapter for DeepSeek JSON responses."""

from __future__ import annotations

import json
import os
import re
import socket
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2

RETRYABLE_STATUS_CODES = {429, 500, 503}
NON_RETRYABLE_STATUS_CODES = {400, 401, 402, 422}

Sender = Callable[[str, bytes, dict[str, str], float], tuple[int, str]]
Sleep = Callable[[float], None]


class DeepSeekConfigurationError(ValueError):
    """Raised when DeepSeek environment configuration is invalid."""

    failure_kind = "model_configuration"


class DeepSeekRequestError(RuntimeError):
    """Raised when a DeepSeek request cannot complete successfully."""

    def __init__(
        self,
        message: str,
        *,
        failure_kind: str = "upstream_connection",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.status_code = status_code


class DeepSeekResponseError(RuntimeError):
    """Raised when DeepSeek returns an invalid or incomplete response."""

    failure_kind = "invalid_model_response"


class _RetryableResponseError(DeepSeekResponseError):
    """Internal marker for response problems that may succeed on retry."""


class DeepSeekAdapter:
    """Call DeepSeek's OpenAI-compatible chat-completions JSON endpoint.

    ``max_retries`` is the number of retries after the initial request. The
    default value of 2 therefore permits at most three attempts.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sender: Sender | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        self._api_key = _required_value(api_key, "DEEPSEEK_API_KEY")
        self.base_url = _normalise_base_url(base_url)
        self.model = _required_value(model, "DEEPSEEK_MODEL")
        self.timeout_seconds = _positive_float(timeout_seconds, "DEEPSEEK_TIMEOUT_SECONDS")
        self.max_retries = _non_negative_int(max_retries, "DEEPSEEK_MAX_RETRIES")
        self._sender = sender or _send_http_request
        self._sleep = sleep or time.sleep

    @classmethod
    def from_env(
        cls,
        *,
        sender: Sender | None = None,
        sleep: Sleep | None = None,
    ) -> "DeepSeekAdapter":
        """Create an adapter from environment variables without reading files."""
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
        model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL)
        timeout = os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        max_retries = os.environ.get("DEEPSEEK_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))

        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=_parse_positive_float(timeout, "DEEPSEEK_TIMEOUT_SECONDS"),
            max_retries=_parse_non_negative_int(max_retries, "DEEPSEEK_MAX_RETRIES"),
            sender=sender,
            sleep=sleep,
        )

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return a validated JSON-object response from DeepSeek.

        The adapter retries only transient request failures plus empty or
        syntactically invalid JSON content. It never includes credentials in
        raised exception messages.
        """
        _validate_prompt(system_prompt, "system_prompt")
        _validate_prompt(user_prompt, "user_prompt")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _ensure_json_instruction(system_prompt, user_prompt)},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
            "max_tokens": max_tokens,
        }
        request_body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        for attempt in range(self.max_retries + 1):
            try:
                status_code, response_body = self._sender(
                    url, request_body, headers, self.timeout_seconds
                )
            except (TimeoutError, socket.timeout):
                if self._can_retry(attempt):
                    self._backoff(attempt)
                    continue
                raise DeepSeekRequestError(
                    "DeepSeek request timed out after the configured retry limit.",
                    failure_kind="upstream_timeout",
                ) from None
            except (URLError, OSError):
                if self._can_retry(attempt):
                    self._backoff(attempt)
                    continue
                raise DeepSeekRequestError(
                    "DeepSeek request failed after the configured retry limit.",
                    failure_kind="upstream_connection",
                ) from None

            if status_code != 200:
                if status_code in NON_RETRYABLE_STATUS_CODES:
                    kind = "model_configuration" if status_code in {400, 401, 402, 422} else "upstream_connection"
                    raise DeepSeekRequestError(
                        f"DeepSeek request was rejected with HTTP status {status_code}.",
                        failure_kind=kind,
                        status_code=status_code,
                    )
                if status_code in RETRYABLE_STATUS_CODES and self._can_retry(attempt):
                    self._backoff(attempt)
                    continue
                raise DeepSeekRequestError(
                    f"DeepSeek request failed with HTTP status {status_code} after retries.",
                    failure_kind=(
                        "upstream_rate_limited"
                        if status_code == 429
                        else "upstream_server_error"
                        if 500 <= status_code <= 599
                        else "upstream_connection"
                    ),
                    status_code=status_code,
                )

            try:
                return _parse_completion_response(response_body)
            except _RetryableResponseError:
                if self._can_retry(attempt):
                    self._backoff(attempt)
                    continue
                raise DeepSeekResponseError(
                    "DeepSeek returned empty or invalid JSON content after retries."
                ) from None

        raise DeepSeekRequestError("DeepSeek request failed after the configured retry limit.")

    def _can_retry(self, attempt: int) -> bool:
        return attempt < self.max_retries

    def _backoff(self, attempt: int) -> None:
        self._sleep(0.25 * (2**attempt))


def _send_http_request(
    url: str,
    request_body: bytes,
    headers: dict[str, str],
    timeout_seconds: float,
) -> tuple[int, str]:
    """Perform the actual HTTP request. Tests inject a sender instead."""
    request = Request(url, data=request_body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def _parse_completion_response(response_body: str) -> dict[str, Any]:
    try:
        response_data = json.loads(response_body)
    except (TypeError, json.JSONDecodeError):
        raise _RetryableResponseError("DeepSeek returned an invalid response body.") from None

    if not isinstance(response_data, dict):
        raise DeepSeekResponseError("DeepSeek response body must be a JSON object.")

    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise DeepSeekResponseError("DeepSeek response must contain a non-empty choices list.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise DeepSeekResponseError("DeepSeek response choice must be an object.")

    if first_choice.get("finish_reason") == "length":
        raise DeepSeekResponseError(
            "DeepSeek response was truncated because it reached the token limit."
        )

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise DeepSeekResponseError("DeepSeek response choice must contain a message object.")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise _RetryableResponseError("DeepSeek response content is empty.")

    content_data = _extract_json_object(content)

    if not isinstance(content_data, dict):
        raise DeepSeekResponseError("DeepSeek response JSON content must be an object.")

    return content_data


_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*(?P<body>.*?)\s*```\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _extract_json_object(content: str) -> dict[str, Any]:
    """Extract one JSON object from a model response without weakening schema checks.

    DeepSeek's JSON mode normally returns bare JSON, but models can still add a
    Markdown fence or a short pre/postamble.  We accept those presentation
    wrappers only; the returned value is still required to be a JSON object and
    is validated by the calling service.  Ambiguous multiple JSON values remain
    invalid and are retried as response errors.
    """
    candidates = [content.strip()]
    fenced = _JSON_FENCE_RE.match(content)
    if fenced:
        candidates.insert(0, fenced.group("body").strip())

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        if parsed is not None:
            raise DeepSeekResponseError(
                "DeepSeek response JSON content must be an object."
            )

        # Allow a small textual preamble/trailer around exactly one object.
        starts = [index for index, char in enumerate(candidate) if char == "{"]
        ambiguous = False
        for start in starts:
            try:
                parsed, end = decoder.raw_decode(candidate, start)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                raise DeepSeekResponseError(
                    "DeepSeek response JSON content must be an object."
                )
            trailing = candidate[end:].strip()
            if trailing and any(marker in trailing for marker in "[{"):
                ambiguous = True
                break
            return parsed
        if ambiguous:
            continue

    raise _RetryableResponseError("DeepSeek response content is not valid JSON.")


def _ensure_json_instruction(system_prompt: str, user_prompt: str) -> str:
    if "json" in system_prompt.lower() or "json" in user_prompt.lower():
        return system_prompt
    return "Return a JSON object. " + system_prompt


def _validate_prompt(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")


def _required_value(value: str, name: str) -> str:
    if not isinstance(value, str) or not (stripped := value.strip()):
        raise DeepSeekConfigurationError(f"{name} must be configured.")
    return stripped


def _normalise_base_url(value: str) -> str:
    return _required_value(value, "DEEPSEEK_BASE_URL").rstrip("/")


def _parse_positive_float(value: str, name: str) -> float:
    try:
        return _positive_float(float(value.strip()), name)
    except (AttributeError, ValueError):
        raise DeepSeekConfigurationError(f"{name} must be a positive number.") from None


def _positive_float(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise DeepSeekConfigurationError(f"{name} must be a positive number.")
    return float(value)


def _parse_non_negative_int(value: str, name: str) -> int:
    try:
        return _non_negative_int(int(value.strip()), name)
    except (AttributeError, ValueError):
        raise DeepSeekConfigurationError(f"{name} must be a non-negative integer.") from None


def _non_negative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DeepSeekConfigurationError(f"{name} must be a non-negative integer.")
    return value
