"""Offline P3e regressions for model outages and reviewed handoff safety."""

import logging
from pathlib import Path

import pytest

from app import _log_qa_failure
from introai_tutor.app_services import build_question_answer_service
from introai_tutor.deepseek_adapter import DeepSeekRequestError, DeepSeekResponseError
from introai_tutor.tutor_service import TutorServiceError


ROOT = Path(__file__).resolve().parents[1]


class _FailingAdapter:
    def __init__(self, error: BaseException):
        self.error = error
        self.calls = []

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        raise self.error


def _service(error: BaseException):
    adapter = _FailingAdapter(error)
    return build_question_answer_service(root=ROOT, adapter=adapter), adapter


@pytest.mark.parametrize(
    "error",
    [
        DeepSeekRequestError("offline timeout", failure_kind="upstream_timeout"),
        DeepSeekRequestError("offline connection", failure_kind="upstream_connection"),
        DeepSeekRequestError("offline 429", failure_kind="upstream_rate_limited"),
        DeepSeekRequestError("offline 503", failure_kind="upstream_server_error"),
    ],
)
def test_explicit_reviewed_ucs_request_uses_local_handoff_before_unavailable_adapter(error):
    service, adapter = _service(error)

    result = service.ask("请用审核诊断题测试我对一致代价搜索如何选择下一个节点的理解。")

    assert adapter.calls == []
    assert result["response"]["status"] == "diagnostic_available"
    assert result["response"]["answer_blocks"] == []
    assert result["response"]["used_chunk_ids"] == []
    assert result["retrieval"]["selected_count"] == 0
    assert result["diagnostic_plan"]["template_ids"] == ["verify_ucs_min_g_choice_v1"]


@pytest.mark.parametrize(
    ("error", "expected_kind"),
    [
        (
            DeepSeekRequestError("offline timeout", failure_kind="upstream_timeout"),
            "upstream_timeout",
        ),
        (
            DeepSeekRequestError("offline connection", failure_kind="upstream_connection"),
            "upstream_connection",
        ),
        (
            DeepSeekRequestError("offline 429", failure_kind="upstream_rate_limited"),
            "upstream_rate_limited",
        ),
        (
            DeepSeekRequestError("offline 503", failure_kind="upstream_server_error"),
            "upstream_server_error",
        ),
        (DeepSeekResponseError("empty content"), "invalid_model_response"),
        (TypeError("local composition fault"), "internal_application_error"),
    ],
)
def test_ordinary_qa_preserves_typed_failure_kind(error, expected_kind):
    service, adapter = _service(error)

    with pytest.raises(TutorServiceError) as raised:
        service.ask("为什么一致代价搜索选择累计路径代价最小的节点？")

    assert len(adapter.calls) == 1
    assert raised.value.failure_kind == expected_kind
    assert raised.value.failure_stage == "qa_topic_classification"
    assert raised.value.correlation_id


def test_unsupported_explicit_request_does_not_forge_a_handoff_plan():
    service, adapter = _service(
        DeepSeekRequestError("offline timeout", failure_kind="upstream_timeout")
    )

    with pytest.raises(TutorServiceError) as raised:
        service.ask("请用审核诊断题测试我对量子搜索的理解。")

    assert len(adapter.calls) == 1
    assert raised.value.failure_kind == "upstream_timeout"


def test_schema_invalid_understanding_output_is_not_misclassified_as_provider_outage():
    class _InvalidSchemaAdapter:
        def __init__(self):
            self.calls = []

        def complete_json(self, **kwargs):
            self.calls.append(kwargs)
            return {"unexpected": "shape"}

    adapter = _InvalidSchemaAdapter()
    service = build_question_answer_service(root=ROOT, adapter=adapter)

    with pytest.raises(TutorServiceError) as raised:
        service.ask("为什么一致代价搜索选择累计路径代价最小的节点？")

    assert len(adapter.calls) == 2
    assert raised.value.failure_kind == "invalid_model_response"
    assert raised.value.failure_stage == "qa_schema_validation"


def test_unknown_local_failure_log_does_not_include_question_or_fake_secret(caplog):
    with caplog.at_level(logging.WARNING, logger="app"):
        _log_qa_failure(
            RuntimeError("private student question; api_key=fake-secret"),
            "qa_unknown",
        )

    record_text = " ".join(record.getMessage() for record in caplog.records)
    assert "private student question" not in record_text
    assert "fake-secret" not in record_text
    assert "internal_application_error" in record_text
