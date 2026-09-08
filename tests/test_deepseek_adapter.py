import json
from urllib.error import URLError

import pytest

from introai_tutor.deepseek_adapter import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    DeepSeekAdapter,
    DeepSeekConfigurationError,
    DeepSeekRequestError,
    DeepSeekResponseError,
)


TEST_API_KEY = "test-api-key-must-not-appear-in-errors"


class SequenceSender:
    """A network-free sender returning values or raising queued exceptions."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append((url, body, headers, timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _completion(content, *, finish_reason="stop"):
    return 200, json.dumps(
        {
            "choices": [
                {
                    "message": {"content": content},
                    "finish_reason": finish_reason,
                }
            ]
        }
    )


def _adapter(monkeypatch, outcomes, **environment):
    for name in (
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_TIMEOUT_SECONDS",
        "DEEPSEEK_MAX_RETRIES",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_API_KEY)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    sender = SequenceSender(outcomes)
    adapter = DeepSeekAdapter.from_env(sender=sender, sleep=lambda _: None)
    return adapter, sender


def test_complete_json_returns_object_and_sends_required_payload(monkeypatch):
    adapter, sender = _adapter(monkeypatch, [_completion('{"answer": "BFS"}')])

    result = adapter.complete_json(
        system_prompt="Return JSON with an answer field.",
        user_prompt="Explain BFS.",
    )

    assert result == {"answer": "BFS"}
    url, body, headers, timeout = sender.calls[0]
    payload = json.loads(body)
    assert url == "https://api.deepseek.com/chat/completions"
    assert headers["Authorization"] == f"Bearer {TEST_API_KEY}"
    assert timeout == 30.0
    assert payload["model"] == DEFAULT_MODEL
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["stream"] is False
    assert payload["max_tokens"] == 1024


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"answer": "BFS"}\n```',
        'Here is the requested object:\n{"answer": "BFS"}\nEnd.',
    ],
)
def test_complete_json_accepts_presentation_wrappers_without_relaxing_object_shape(
    monkeypatch, content
):
    adapter, _ = _adapter(monkeypatch, [_completion(content)])

    assert adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.") == {
        "answer": "BFS"
    }


def test_complete_json_rejects_ambiguous_multiple_json_objects(monkeypatch):
    adapter, sender = _adapter(
        monkeypatch,
        [_completion('{"answer": "BFS"}{"answer": "UCS"}')],
        DEEPSEEK_MAX_RETRIES="0",
    )

    with pytest.raises(DeepSeekResponseError, match="empty or invalid JSON"):
        adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")

    assert len(sender.calls) == 1


def test_missing_api_key_fails_without_sender(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(DeepSeekConfigurationError, match="DEEPSEEK_API_KEY"):
        DeepSeekAdapter.from_env(sender=SequenceSender([]))


def test_default_configuration(monkeypatch):
    adapter, sender = _adapter(monkeypatch, [])

    assert adapter.base_url == DEFAULT_BASE_URL
    assert adapter.model == DEFAULT_MODEL
    assert adapter.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert adapter.max_retries == DEFAULT_MAX_RETRIES
    assert sender.calls == []


def test_environment_overrides_are_stripped(monkeypatch):
    adapter, sender = _adapter(
        monkeypatch,
        [_completion('{"ok": true}')],
        DEEPSEEK_API_KEY="  " + TEST_API_KEY + "\r\n",
        DEEPSEEK_BASE_URL=" https://example.invalid/api/ \r\n",
        DEEPSEEK_MODEL=" custom-model \r\n",
        DEEPSEEK_TIMEOUT_SECONDS=" 12.5 \r\n",
        DEEPSEEK_MAX_RETRIES=" 1 \r\n",
    )

    adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")

    url, _, headers, timeout = sender.calls[0]
    assert adapter.base_url == "https://example.invalid/api"
    assert adapter.model == "custom-model"
    assert adapter.max_retries == 1
    assert url == "https://example.invalid/api/chat/completions"
    assert headers["Authorization"] == f"Bearer {TEST_API_KEY}"
    assert timeout == 12.5


def test_adapter_adds_json_instruction_when_callers_omit_it(monkeypatch):
    adapter, sender = _adapter(monkeypatch, [_completion('{"ok": true}')])

    adapter.complete_json(system_prompt="Be concise.", user_prompt="Explain BFS.")

    payload = json.loads(sender.calls[0][1])
    assert payload["messages"][0]["content"].startswith("Return a JSON object.")


def test_empty_content_retries_then_succeeds(monkeypatch):
    adapter, sender = _adapter(
        monkeypatch,
        [_completion(""), _completion('{"ok": true}')],
    )

    assert adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.") == {"ok": True}
    assert len(sender.calls) == 2


def test_persistent_empty_content_fails_after_retries(monkeypatch):
    adapter, sender = _adapter(
        monkeypatch,
        [_completion(""), _completion("")],
        DEEPSEEK_MAX_RETRIES="1",
    )

    with pytest.raises(DeepSeekResponseError, match="empty or invalid JSON"):
        adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")

    assert len(sender.calls) == 2


def test_invalid_json_content_retries_then_fails(monkeypatch):
    adapter, sender = _adapter(
        monkeypatch,
        [_completion("not-json"), _completion("still-not-json")],
        DEEPSEEK_MAX_RETRIES="1",
    )

    with pytest.raises(DeepSeekResponseError, match="empty or invalid JSON"):
        adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")

    assert len(sender.calls) == 2


def test_json_content_must_be_an_object(monkeypatch):
    adapter, _ = _adapter(monkeypatch, [_completion("[]")])

    with pytest.raises(DeepSeekResponseError, match="must be an object"):
        adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")


@pytest.mark.parametrize(
    "response_body",
    [
        json.dumps({}),
        json.dumps({"choices": []}),
    ],
)
def test_choices_must_be_present_and_non_empty(monkeypatch, response_body):
    adapter, _ = _adapter(monkeypatch, [(200, response_body)])

    with pytest.raises(DeepSeekResponseError, match="non-empty choices"):
        adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")


def test_finish_reason_length_is_a_clear_truncation_error(monkeypatch):
    adapter, sender = _adapter(
        monkeypatch,
        [_completion('{"partial": true}', finish_reason="length")],
    )

    with pytest.raises(DeepSeekResponseError, match="truncated"):
        adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")

    assert len(sender.calls) == 1


def test_401_is_not_retried_and_does_not_expose_api_key(monkeypatch):
    adapter, sender = _adapter(monkeypatch, [(401, "unauthorized")])

    with pytest.raises(DeepSeekRequestError) as error:
        adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")

    assert len(sender.calls) == 1
    assert TEST_API_KEY not in str(error.value)
    assert "Authorization" not in str(error.value)
    assert error.value.failure_kind == "model_configuration"


def test_429_retries_then_succeeds(monkeypatch):
    adapter, sender = _adapter(
        monkeypatch,
        [(429, "rate limited"), _completion('{"ok": true}')],
    )

    assert adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.") == {"ok": True}
    assert len(sender.calls) == 2


def test_final_timeout_and_http_failures_have_stable_failure_kinds(monkeypatch):
    timeout_adapter, _ = _adapter(
        monkeypatch,
        [TimeoutError()],
        DEEPSEEK_MAX_RETRIES="0",
    )
    with pytest.raises(DeepSeekRequestError) as timeout:
        timeout_adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")
    assert timeout.value.failure_kind == "upstream_timeout"

    rate_adapter, _ = _adapter(
        monkeypatch,
        [(429, "rate limited")],
        DEEPSEEK_MAX_RETRIES="0",
    )
    with pytest.raises(DeepSeekRequestError) as rate:
        rate_adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")
    assert rate.value.failure_kind == "upstream_rate_limited"

    server_adapter, _ = _adapter(
        monkeypatch,
        [(503, "unavailable")],
        DEEPSEEK_MAX_RETRIES="0",
    )
    with pytest.raises(DeepSeekRequestError) as server:
        server_adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")
    assert server.value.failure_kind == "upstream_server_error"


@pytest.mark.parametrize("status_code", [500, 503])
def test_retryable_server_status_fails_after_max_retries(monkeypatch, status_code):
    adapter, sender = _adapter(
        monkeypatch,
        [(status_code, "server error"), (status_code, "server error")],
        DEEPSEEK_MAX_RETRIES="1",
    )

    with pytest.raises(DeepSeekRequestError, match=f"HTTP status {status_code}"):
        adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.")

    assert len(sender.calls) == 2


@pytest.mark.parametrize("network_error", [TimeoutError(), URLError("temporary failure")])
def test_timeout_and_network_errors_retry(monkeypatch, network_error):
    adapter, sender = _adapter(
        monkeypatch,
        [network_error, _completion('{"ok": true}')],
    )

    assert adapter.complete_json(system_prompt="Return JSON.", user_prompt="Test.") == {"ok": True}
    assert len(sender.calls) == 2
