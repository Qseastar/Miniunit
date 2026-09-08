"""Deterministic orchestration for the Search Algorithms tutor pipeline."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from introai_tutor.retrieval import retrieve_course_chunks


_SOURCE_ROLES = {"course_core", "prerequisite_support"}
QA_FAILURE_STAGES = (
    "qa_input_validation",
    "qa_topic_classification",
    "qa_retrieval",
    "qa_answer_generation",
    "qa_json_parsing",
    "qa_schema_validation",
    "qa_citation_validation",
    "qa_result_construction",
    "qa_handoff_construction",
    "qa_diagnostic_fast_path",
    "qa_unknown",
)
QA_FAILURE_KINDS = frozenset(
    {
        "upstream_timeout",
        "upstream_connection",
        "upstream_rate_limited",
        "upstream_server_error",
        "model_configuration",
        "invalid_model_response",
        "internal_application_error",
    }
)
_LOGGER = logging.getLogger(__name__)
_MAX_LOG_MESSAGE = 180
_SECRET_PATTERN = re.compile(r"(?i)(bearer\s+|api[_-]?key\s*[=:]\s*)[^\s,;]+")


class TutorServiceError(ValueError):
    """Raised when TutorService configuration or retrieval candidates are invalid."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "qa_unknown",
        correlation_id: str | None = None,
        failure_kind: str = "internal_application_error",
    ) -> None:
        super().__init__(message)
        self.failure_stage = stage
        # ``stage`` is a convenient stable alias for logs and callers.
        self.stage = stage
        self.correlation_id = correlation_id or uuid.uuid4().hex[:12]
        self.failure_kind = (
            failure_kind if failure_kind in QA_FAILURE_KINDS else "internal_application_error"
        )


class TutorService:
    """Compose understanding, retrieval, evidence selection, and answering.

    The service owns only deterministic routing and selection. It creates no
    adapters or component services, and it does not alter learner state.
    """

    def __init__(
        self,
        *,
        understanding_service: Any,
        answer_service: Any,
        course_data: dict,
        valid_topic_ids: set[str] | list[str] | tuple[str, ...],
        retriever=retrieve_course_chunks,
        candidate_top_k: int = 12,
        max_evidence_chunks: int = 6,
        max_prerequisite_chunks: int = 3,
        include_prerequisite_support: bool = True,
        diagnostic_plan_service: Any | None = None,
        deterministic_diagnostic_request_parser: Any | None = None,
    ) -> None:
        if not callable(getattr(understanding_service, "understand", None)):
            raise TutorServiceError("understanding_service must provide callable understand().")
        if not callable(getattr(answer_service, "answer", None)):
            raise TutorServiceError("answer_service must provide callable answer().")
        if not isinstance(course_data, dict):
            raise TutorServiceError("course_data must be an object.")
        if not callable(retriever):
            raise TutorServiceError("retriever must be callable.")

        self._valid_topic_ids = _validate_valid_topic_ids(valid_topic_ids)
        self._candidate_top_k = _validate_positive_int(candidate_top_k, "candidate_top_k")
        self._max_evidence_chunks = _validate_positive_int(
            max_evidence_chunks, "max_evidence_chunks"
        )
        self._max_prerequisite_chunks = _validate_non_negative_int(
            max_prerequisite_chunks, "max_prerequisite_chunks"
        )
        if self._candidate_top_k < self._max_evidence_chunks:
            raise TutorServiceError(
                "candidate_top_k must be greater than or equal to max_evidence_chunks."
            )
        if self._max_prerequisite_chunks > self._max_evidence_chunks:
            raise TutorServiceError(
                "max_prerequisite_chunks must not exceed max_evidence_chunks."
            )
        if not isinstance(include_prerequisite_support, bool):
            raise TutorServiceError("include_prerequisite_support must be a boolean.")
        if diagnostic_plan_service is not None and not callable(
            getattr(diagnostic_plan_service, "plan_from_qa_result", None)
        ):
            raise TutorServiceError(
                "diagnostic_plan_service must provide callable plan_from_qa_result()."
            )
        if deterministic_diagnostic_request_parser is not None and not callable(
            getattr(deterministic_diagnostic_request_parser, "parse", None)
        ):
            raise TutorServiceError(
                "deterministic_diagnostic_request_parser must provide callable parse()."
            )

        self._understanding_service = understanding_service
        self._answer_service = answer_service
        self._course_data = course_data
        self._retriever = retriever
        self._include_prerequisite_support = include_prerequisite_support
        self._diagnostic_plan_service = diagnostic_plan_service
        self._deterministic_diagnostic_request_parser = deterministic_diagnostic_request_parser

    def ask(self, question: str) -> dict:
        """Return one Python-computed trace and the selected answer response."""
        correlation_id = uuid.uuid4().hex[:12]
        try:
            if not isinstance(question, str):
                raise TutorServiceError("question must be a string.")
            normalized_question = question.strip()
            if not normalized_question:
                raise TutorServiceError("question must not be empty.")
        except Exception as error:
            raise _qa_failure(error, "qa_input_validation", correlation_id) from error

        fast_path_result = self._try_deterministic_diagnostic_handoff(
            question=normalized_question,
            correlation_id=correlation_id,
        )
        if fast_path_result is not None:
            return fast_path_result

        understanding = _run_qa_stage(
            "qa_topic_classification",
            correlation_id,
            lambda: self._understanding_service.understand(normalized_question),
        )
        routing = _run_qa_stage(
            "qa_topic_classification",
            correlation_id,
            lambda: _validate_routing_fields(understanding),
        )
        preflight_plan = None
        if (
            routing["intent"] == "diagnostic_request"
            and self._diagnostic_plan_service is not None
        ):
            preflight_plan = _run_qa_stage(
                "qa_handoff_construction",
                correlation_id,
                lambda: self._diagnostic_plan_service.plan_from_qa_result(
                    qa_result={
                        "question": normalized_question,
                        "understanding": understanding,
                    }
                ),
            )
            if preflight_plan.get("available") is True:
                return _run_qa_stage(
                    "qa_result_construction",
                    correlation_id,
                    lambda: {
                        "question": normalized_question,
                        "understanding": understanding,
                        "retrieval": _empty_retrieval_trace(),
                        "response": _diagnostic_transition_response(),
                        "diagnostic_plan": preflight_plan,
                    },
                )

        if not routing["in_scope"] or routing["needs_clarification"]:
            selected_results: list[dict] = []
            retrieval_trace = _empty_retrieval_trace()
        else:
            candidates = _run_qa_stage(
                "qa_retrieval",
                correlation_id,
                lambda: self._retriever(
                    self._course_data,
                    query=normalized_question,
                    valid_topic_ids=self._valid_topic_ids,
                    topic_ids=routing["topic_ids"],
                    search_terms=routing["search_terms"],
                    top_k=self._candidate_limit(routing["topic_ids"]),
                    include_prerequisite_support=self._include_prerequisite_support,
                ),
            )
            selected_results, topic_coverage = _run_qa_stage(
                "qa_retrieval",
                correlation_id,
                lambda: self._select_evidence(candidates, routing["topic_ids"]),
            )
            retrieval_trace = {
                "candidate_count": len(candidates),
                "selected_count": len(selected_results),
                "selected_chunk_ids": [result["chunk"]["id"] for result in selected_results],
                "topic_coverage": topic_coverage,
                "results": selected_results,
            }

        response = _run_qa_stage(
            "qa_answer_generation",
            correlation_id,
            lambda: self._answer_service.answer(
                question=normalized_question,
                understanding=understanding,
                retrieval_results=selected_results,
            ),
        )
        result = _run_qa_stage(
            "qa_result_construction",
            correlation_id,
            lambda: {
                "question": normalized_question,
                "understanding": understanding,
                "retrieval": retrieval_trace,
                "response": response,
            },
        )
        if preflight_plan is not None:
            result["diagnostic_plan"] = preflight_plan
        return result

    def _try_deterministic_diagnostic_handoff(
        self, *, question: str, correlation_id: str
    ) -> dict | None:
        """Plan a strongly explicit reviewed diagnostic without a model call.

        The parser supplies only a controlled understanding object.  The
        existing handoff service remains responsible for production-template
        eligibility and returns ``available=False`` when no reviewed template
        can safely serve the requested concept.
        """
        if (
            self._deterministic_diagnostic_request_parser is None
            or self._diagnostic_plan_service is None
        ):
            return None
        understanding = _run_qa_stage(
            "qa_diagnostic_fast_path",
            correlation_id,
            lambda: self._deterministic_diagnostic_request_parser.parse(question),
        )
        if understanding is None:
            return None
        routing = _run_qa_stage(
            "qa_diagnostic_fast_path",
            correlation_id,
            lambda: _validate_routing_fields(understanding),
        )
        if routing["intent"] != "diagnostic_request":
            raise _qa_failure(
                TutorServiceError("deterministic diagnostic parser returned an invalid intent."),
                "qa_diagnostic_fast_path",
                correlation_id,
            )
        plan = _run_qa_stage(
            "qa_handoff_construction",
            correlation_id,
            lambda: self._diagnostic_plan_service.plan_from_qa_result(
                qa_result={"question": question, "understanding": understanding}
            ),
        )
        if plan.get("available") is not True:
            return None
        return _run_qa_stage(
            "qa_result_construction",
            correlation_id,
            lambda: {
                "question": question,
                "understanding": understanding,
                "retrieval": _empty_retrieval_trace(),
                "response": _diagnostic_transition_response(),
                "diagnostic_plan": plan,
            },
        )

    def _candidate_limit(self, topic_ids: list[str]) -> int:
        """Use the ordinary window for one topic and full local coverage otherwise.

        Multi-topic coverage needs access to topic-specific evidence that can
        rank below broad summary chunks. This only expands a deterministic
        local retrieval call; it creates no additional model work.
        """
        if len(topic_ids) <= 1:
            return self._candidate_top_k
        chunks = self._course_data.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise TutorServiceError(
                "course_data must contain a non-empty chunks list for multi-topic retrieval."
            )
        return len(chunks)

    def _select_evidence(
        self, candidates: Any, topic_ids: list[str]
    ) -> tuple[list[dict], dict[str, list[str]]]:
        validated_candidates = _validate_candidates(candidates)
        candidate_rank = {
            candidate["chunk"]["id"]: index
            for index, candidate in enumerate(validated_candidates)
        }
        selected_ids: set[str] = set()
        topic_coverage: dict[str, list[str]] = {topic_id: [] for topic_id in topic_ids}
        support_count = 0

        def select(candidate: dict) -> bool:
            nonlocal support_count
            chunk = candidate["chunk"]
            chunk_id = chunk["id"]
            if chunk_id in selected_ids:
                return True
            if len(selected_ids) >= self._max_evidence_chunks:
                return False
            if (
                chunk["source_role"] == "prerequisite_support"
                and support_count >= self._max_prerequisite_chunks
            ):
                return False
            selected_ids.add(chunk_id)
            if chunk["source_role"] == "prerequisite_support":
                support_count += 1
            return True

        def by_specificity(candidates_for_topic: list[dict]) -> list[dict]:
            return sorted(
                candidates_for_topic,
                key=lambda candidate: (
                    len(candidate["chunk"]["topic_ids"]),
                    candidate_rank[candidate["chunk"]["id"]],
                ),
            )

        # Phase 1: cover each requested topic in input order. Prefer core,
        # then topic-specific chunks, then the original retrieval rank.
        for topic_id in topic_ids:
            unselected_candidates = [
                candidate
                for candidate in validated_candidates
                if _candidate_covers_topic(candidate, topic_id)
                and candidate["chunk"]["id"] not in selected_ids
            ]
            core_candidates = [
                candidate
                for candidate in unselected_candidates
                if candidate["chunk"]["source_role"] == "course_core"
            ]
            choices = by_specificity(core_candidates or unselected_candidates)
            for candidate in choices:
                if select(candidate):
                    chunk_id = candidate["chunk"]["id"]
                    if chunk_id not in topic_coverage[topic_id]:
                        topic_coverage[topic_id].append(chunk_id)
                    break
            else:
                # All candidates for this topic may already have been selected
                # while covering an earlier topic. Reuse that coverage without
                # selecting the same chunk twice.
                selected_candidates = [
                    candidate
                    for candidate in validated_candidates
                    if candidate["chunk"]["id"] in selected_ids
                    and _candidate_covers_topic(candidate, topic_id)
                ]
                for candidate in by_specificity(selected_candidates):
                    chunk_id = candidate["chunk"]["id"]
                    if chunk_id not in topic_coverage[topic_id]:
                        topic_coverage[topic_id].append(chunk_id)
                        break

        # Phase 2: when possible, ensure the selected set includes core evidence.
        if not any(
            candidate["chunk"]["source_role"] == "course_core"
            and candidate["chunk"]["id"] in selected_ids
            for candidate in validated_candidates
        ):
            for candidate in validated_candidates:
                if candidate["chunk"]["source_role"] == "course_core":
                    select(candidate)
                    break

        # Phase 3: retain original retrieval order while filling remaining slots.
        for candidate in validated_candidates:
            if len(selected_ids) >= self._max_evidence_chunks:
                break
            select(candidate)

        selected_results = [
            candidate
            for candidate in validated_candidates
            if candidate["chunk"]["id"] in selected_ids
        ]
        return selected_results, topic_coverage


def _run_qa_stage(stage: str, correlation_id: str, operation):
    try:
        return operation()
    except Exception as error:
        raise _qa_failure(error, stage, correlation_id) from error


def _qa_failure(error: BaseException, stage: str, correlation_id: str) -> TutorServiceError:
    """Convert a pipeline failure to a safe public error and structured log."""
    stage = _refine_failure_stage(stage, error)
    if stage not in QA_FAILURE_STAGES:
        stage = "qa_unknown"
    if isinstance(error, TutorServiceError):
        public_message = str(error)
    else:
        public_message = f"QA request failed during {stage}."
    safe_message = _sanitize_log_message(public_message)
    failure_kind = _failure_kind(error)
    _LOGGER.warning(
        "freeform QA failure stage=%s kind=%s correlation_id=%s exception=%s message=%s",
        stage,
        failure_kind,
        correlation_id,
        type(error).__name__,
        safe_message,
    )
    return TutorServiceError(
        public_message,
        stage=stage,
        correlation_id=correlation_id,
        failure_kind=failure_kind,
    )


def _failure_kind(error: BaseException) -> str:
    value = getattr(error, "failure_kind", None)
    return value if value in QA_FAILURE_KINDS else "internal_application_error"


def _refine_failure_stage(stage: str, error: BaseException) -> str:
    """Use component error wording to expose a useful bounded sub-stage."""
    message = str(error).casefold()
    if stage == "qa_topic_classification" and "output is invalid" in message:
        return "qa_schema_validation"
    if stage == "qa_answer_generation":
        if "cites a chunk" in message or "citation" in message:
            return "qa_citation_validation"
        if "model output" in message or "missing fields" in message:
            return "qa_schema_validation"
        if "json" in message:
            return "qa_json_parsing"
    return stage


def _sanitize_log_message(message: str) -> str:
    text = _SECRET_PATTERN.sub(r"\1[REDACTED]", str(message))
    text = " ".join(text.split())
    return text[:_MAX_LOG_MESSAGE]


def _validate_routing_fields(understanding: Any) -> dict:
    if not isinstance(understanding, dict):
        raise TutorServiceError("understanding_service must return an object.")
    in_scope = understanding.get("in_scope")
    needs_clarification = understanding.get("needs_clarification")
    intent = understanding.get("intent")
    if not isinstance(in_scope, bool):
        raise TutorServiceError("understanding.in_scope must be a boolean.")
    if not isinstance(needs_clarification, bool):
        raise TutorServiceError("understanding.needs_clarification must be a boolean.")
    if not isinstance(intent, str) or not intent.strip():
        raise TutorServiceError("understanding.intent must be a non-empty string.")
    topic_ids = _validate_string_list(understanding.get("topic_ids"), "understanding.topic_ids")
    search_terms = _validate_string_list(
        understanding.get("search_terms"), "understanding.search_terms"
    )
    return {
        "in_scope": in_scope,
        "intent": intent,
        "needs_clarification": needs_clarification,
        "topic_ids": topic_ids,
        "search_terms": search_terms,
    }


def _diagnostic_transition_response() -> dict:
    """Return a deterministic handoff without exposing an answer or quiz key."""
    message = "系统已找到与本题相关的审核诊断题，可进入诊断。"
    return {
        "status": "diagnostic_available",
        "answer": message,
        "answer_blocks": [],
        "used_chunk_ids": [],
        "limitations": [],
        "confidence": 0.0,
    }


def _validate_candidates(candidates: Any) -> list[dict]:
    if not isinstance(candidates, list):
        raise TutorServiceError("retriever must return a list of candidate results.")
    seen_chunk_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise TutorServiceError(f"retriever candidate at index {index} must be an object.")
        if not isinstance(candidate.get("chunk"), dict):
            raise TutorServiceError(f"retriever candidate at index {index} must contain a chunk object.")
        chunk = candidate["chunk"]
        chunk_id = chunk.get("id")
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise TutorServiceError(f"retriever candidate at index {index} has invalid chunk id.")
        if chunk_id in seen_chunk_ids:
            raise TutorServiceError(f"Duplicate candidate chunk id: {chunk_id}")
        seen_chunk_ids.add(chunk_id)
        source_role = chunk.get("source_role")
        if not isinstance(source_role, str) or source_role not in _SOURCE_ROLES:
            raise TutorServiceError(f"Candidate chunk '{chunk_id}' has invalid source_role.")
        _validate_string_list(chunk.get("topic_ids"), f"Candidate chunk '{chunk_id}' topic_ids")
        _validate_string_list(
            candidate.get("matched_topic_ids"),
            f"Candidate chunk '{chunk_id}' matched_topic_ids",
        )
    return candidates


def _candidate_covers_topic(candidate: dict, topic_id: str) -> bool:
    return (
        topic_id in candidate["matched_topic_ids"]
        or topic_id in candidate["chunk"]["topic_ids"]
    )


def _empty_retrieval_trace() -> dict:
    return {
        "candidate_count": 0,
        "selected_count": 0,
        "selected_chunk_ids": [],
        "topic_coverage": {},
        "results": [],
    }


def _validate_valid_topic_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, set | list | tuple) or not value:
        raise TutorServiceError("valid_topic_ids must be a non-empty set, list, or tuple.")
    result: list[str] = []
    for index, topic_id in enumerate(value):
        if not isinstance(topic_id, str) or not (normalized := topic_id.strip()):
            raise TutorServiceError(f"valid_topic_ids[{index}] must be a non-empty string.")
        if normalized not in result:
            result.append(normalized)
    if not result:
        raise TutorServiceError("valid_topic_ids must contain a non-empty string.")
    return tuple(result)


def _validate_string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list):
        raise TutorServiceError(f"{name} must be a list of strings.")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not (normalized := item.strip()):
            raise TutorServiceError(f"{name}[{index}] must be a non-empty string.")
        result.append(normalized)
    return result


def _validate_positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TutorServiceError(f"{name} must be a positive integer.")
    return value


def _validate_non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TutorServiceError(f"{name} must be a non-negative integer.")
    return value
