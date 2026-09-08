"""Small SQLite persistence boundary for anonymous learner-state recovery.

The repository stores only the state needed to resume learning: mastery,
misconception identifiers, and a compact reviewed-verification audit record.
It deliberately never accepts free-form questions, answers, course text, or
model requests/responses.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator


SCHEMA_VERSION = 3
DEFAULT_DB_DIRECTORY = ".introai_tutor"
DEFAULT_DB_FILENAME = "learner_state.sqlite3"
_FORBIDDEN_EVIDENCE_KEYS = {
    "question",
    "question_text",
    "answer",
    "answer_text",
    "prompt",
    "api_key",
    "authorization",
    "course_chunk_text",
    "content",
}
_SCHEMA_LOCKS: dict[str, threading.Lock] = {}
_SCHEMA_LOCKS_GUARD = threading.Lock()


class LearnerStatePersistenceError(RuntimeError):
    """Raised for a recoverable local persistence failure."""


@dataclass(frozen=True)
class LoadedLearnerProfile:
    """Validated recovery result with non-fatal row-level warnings."""

    learner_state: dict[str, Any]
    completed_summaries: list[dict[str, Any]]
    warnings: list[str]


def default_state_db_path() -> Path:
    """Return the stable local database path, optionally overridden for tests."""
    configured = os.environ.get("INTROAI_STATE_DB")
    if configured is not None and configured.strip():
        return Path(configured.strip()).expanduser()
    return Path.home() / DEFAULT_DB_DIRECTORY / DEFAULT_DB_FILENAME


class SQLiteLearnerStateRepository:
    """Persist existing learner-domain snapshots without domain calculations."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._path = Path(db_path) if db_path is not None else default_state_db_path()
        if not self._path.name:
            raise LearnerStatePersistenceError("SQLite database path is invalid.")

    @property
    def path(self) -> Path:
        return self._path

    def initialize_schema(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with _schema_lock(self._path):
                with self._connection() as connection:
                    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                    if version > SCHEMA_VERSION:
                        raise LearnerStatePersistenceError(
                            "Local learner-state database uses a newer unsupported schema."
                        )
                    if version == 0:
                        with _transaction(connection):
                            _create_schema_v3(connection)
                            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    elif version == 1:
                        with _transaction(connection):
                            _migrate_v1_to_v2(connection)
                            _migrate_v2_to_v3(connection)
                            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    elif version == 2:
                        with _transaction(connection):
                            _migrate_v2_to_v3(connection)
                            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except LearnerStatePersistenceError:
            raise
        except (OSError, sqlite3.DatabaseError) as error:
            raise LearnerStatePersistenceError(
                f"Local learner-state database is unavailable: {type(error).__name__}."
            ) from None

    def health_check(self) -> bool:
        self.initialize_schema()
        try:
            with self._connection() as connection:
                connection.execute("SELECT 1").fetchone()
            return True
        except (sqlite3.DatabaseError, OSError) as error:
            raise LearnerStatePersistenceError(
                f"Local learner-state health check failed: {type(error).__name__}."
            ) from None

    def profile_exists(self, learner_id: str) -> bool:
        self.initialize_schema()
        learner_id = _learner_id(learner_id)
        try:
            with self._connection() as connection:
                return connection.execute(
                    "SELECT 1 FROM learner_profiles WHERE learner_id = ?", (learner_id,)
                ).fetchone() is not None
        except sqlite3.DatabaseError as error:
            raise LearnerStatePersistenceError(
                f"Local learner-state lookup failed: {type(error).__name__}."
            ) from None

    def load_profile(self, learner_id: str) -> LoadedLearnerProfile | None:
        """Recover one profile, skipping malformed rows without rewriting them."""
        self.initialize_schema()
        learner_id = _learner_id(learner_id)
        try:
            with self._connection() as connection:
                profile = connection.execute(
                    "SELECT course_id, preferred_style FROM learner_profiles WHERE learner_id = ?",
                    (learner_id,),
                ).fetchone()
                if profile is None:
                    return None
                warnings: list[str] = []
                mastery: dict[str, float] = {}
                for row in connection.execute(
                    "SELECT concept_id, mastery FROM concept_state WHERE learner_id = ?",
                    (learner_id,),
                ):
                    concept_id, value = row["concept_id"], row["mastery"]
                    if not isinstance(concept_id, str) or not _valid_score(value):
                        warnings.append("一条掌握度记录格式无效，未恢复。")
                        continue
                    mastery[concept_id] = float(value)
                misconceptions = [
                    row["misconception_id"]
                    for row in connection.execute(
                        "SELECT misconception_id FROM misconception_state WHERE learner_id = ? ORDER BY misconception_id",
                        (learner_id,),
                    )
                    if isinstance(row["misconception_id"], str) and row["misconception_id"].strip()
                ]
                summaries: list[dict[str, Any]] = []
                for row in connection.execute(
                    "SELECT event_id, payload_json FROM evidence_events WHERE learner_id = ? ORDER BY occurred_at, event_id",
                    (learner_id,),
                ):
                    try:
                        payload = json.loads(row["payload_json"])
                    except (TypeError, json.JSONDecodeError):
                        warnings.append("一条审核证据记录无法恢复。")
                        continue
                    if not _valid_evidence_payload(payload):
                        warnings.append("一条审核证据记录格式无效，未恢复。")
                        continue
                    summaries.append({"event_id": row["event_id"], **payload})
                state = {
                    "student_id": learner_id,
                    "course_id": profile["course_id"],
                    "mastery": mastery,
                    "misconceptions": misconceptions,
                    "learning_evidence": [_learner_evidence(summary) for summary in summaries],
                    "preferred_style": profile["preferred_style"],
                }
                return LoadedLearnerProfile(state, summaries, warnings)
        except sqlite3.DatabaseError as error:
            raise LearnerStatePersistenceError(
                f"Local learner-state recovery failed: {type(error).__name__}."
            ) from None

    def save_profile(
        self,
        *,
        learner_id: str,
        learner_state: dict[str, Any],
        completed_summary: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> bool:
        """Atomically store a state snapshot and, optionally, one audit event.

        Returns ``True`` for a duplicate same-payload event no-op. A repeated
        event never rewrites a newer snapshot; a conflicting payload fails
        closed before any write.
        """
        self.initialize_schema()
        learner_id = _learner_id(learner_id)
        snapshot = _state_snapshot(learner_state, learner_id)
        payload = None
        payload_hash = None
        if completed_summary is not None or event_id is not None:
            if not isinstance(event_id, str) or not event_id.strip():
                raise LearnerStatePersistenceError("event_id is required for persisted evidence.")
            payload = _minimal_evidence_payload(completed_summary)
            payload_hash = _payload_hash(payload)
        now = _now()
        try:
            with self._connection() as connection:
                with _transaction(connection):
                    if payload is not None:
                        existing = connection.execute(
                            "SELECT payload_hash FROM evidence_events WHERE event_id = ?",
                            (event_id,),
                        ).fetchone()
                        if existing is not None:
                            if existing["payload_hash"] != payload_hash:
                                raise LearnerStatePersistenceError(
                                    "Evidence event ID conflicts with a different payload."
                                )
                            return True
                    connection.execute(
                        """INSERT INTO learner_profiles
                        (learner_id, course_id, preferred_style, created_at, last_seen_at, state_version)
                        VALUES (?, ?, ?, ?, ?, 1)
                        ON CONFLICT(learner_id) DO UPDATE SET
                          course_id=excluded.course_id,
                          preferred_style=excluded.preferred_style,
                          last_seen_at=excluded.last_seen_at,
                          state_version=excluded.state_version""",
                        (learner_id, snapshot["course_id"], snapshot["preferred_style"], now, now),
                    )
                    connection.executemany(
                        """INSERT INTO concept_state (learner_id, concept_id, mastery, updated_at) VALUES (?, ?, ?, ?)
                        ON CONFLICT(learner_id, concept_id) DO UPDATE SET
                          mastery=excluded.mastery, updated_at=excluded.updated_at""",
                        [(learner_id, concept_id, score, now) for concept_id, score in snapshot["mastery"].items()],
                    )
                    connection.executemany(
                        """INSERT INTO misconception_state (learner_id, misconception_id, updated_at) VALUES (?, ?, ?)
                        ON CONFLICT(learner_id, misconception_id) DO UPDATE SET
                          updated_at=excluded.updated_at""",
                        [(learner_id, item, now) for item in snapshot["misconceptions"]],
                    )
                    if payload is not None:
                        connection.execute(
                            """INSERT INTO evidence_events
                            (event_id, learner_id, payload_json, payload_hash, occurred_at, schema_version)
                            VALUES (?, ?, ?, ?, ?, 1)""",
                            (event_id, learner_id, _canonical_json(payload), payload_hash, now),
                        )
            return False
        except LearnerStatePersistenceError:
            raise
        except sqlite3.DatabaseError as error:
            raise LearnerStatePersistenceError(
                f"Local learner-state save failed: {type(error).__name__}."
            ) from None

    def append_evidence(
        self,
        *,
        learner_id: str,
        learner_state: dict[str, Any],
        completed_summary: dict[str, Any],
        event_id: str,
    ) -> bool:
        """Persist one accepted reviewed event with its post-update snapshot."""
        return self.save_profile(
            learner_id=learner_id,
            learner_state=learner_state,
            completed_summary=completed_summary,
            event_id=event_id,
        )

    def reviewed_template_exposures(self, learner_id: str) -> dict[str, dict[str, str]]:
        """Return only minimal per-template first-exposure metadata."""
        self.initialize_schema()
        learner_id = _learner_id(learner_id)
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """SELECT template_id, first_exposed_at, exposure_reason
                    FROM reviewed_template_exposure
                    WHERE learner_id = ? ORDER BY template_id""",
                    (learner_id,),
                )
                result: dict[str, dict[str, str]] = {}
                for row in rows:
                    template_id = row["template_id"]
                    timestamp = row["first_exposed_at"]
                    reason = row["exposure_reason"]
                    if (
                        isinstance(template_id, str)
                        and template_id.strip()
                        and isinstance(timestamp, str)
                        and timestamp.strip()
                        and reason in _EXPOSURE_REASONS
                    ):
                        result[template_id] = {
                            "first_exposed_at": timestamp,
                            "exposure_reason": reason,
                        }
                return result
        except sqlite3.DatabaseError as error:
            raise LearnerStatePersistenceError(
                f"Local learner-state exposure lookup failed: {type(error).__name__}."
            ) from None

    def claim_reviewed_template_exposure(
        self, *, learner_id: str, template_id: str, reason: str
    ) -> bool:
        """Insert first exposure once, returning ``True`` when it already existed."""
        self.initialize_schema()
        learner_id = _learner_id(learner_id)
        template_id = _template_id(template_id)
        if reason not in _EXPOSURE_REASONS - {"migrated_existing_evidence"}:
            raise LearnerStatePersistenceError("reviewed-template exposure reason is invalid.")
        try:
            with self._connection() as connection:
                with _transaction(connection):
                    cursor = connection.execute(
                        """INSERT INTO reviewed_template_exposure
                        (learner_id, template_id, first_exposed_at, exposure_reason, schema_version)
                        VALUES (?, ?, ?, ?, 1)
                        ON CONFLICT(learner_id, template_id) DO NOTHING""",
                        (learner_id, template_id, _now(), reason),
                    )
                    return cursor.rowcount == 0
        except sqlite3.DatabaseError as error:
            raise LearnerStatePersistenceError(
                f"Local learner-state exposure save failed: {type(error).__name__}."
            ) from None

    def clear_profile(self, learner_id: str) -> None:
        self.initialize_schema()
        learner_id = _learner_id(learner_id)
        try:
            with self._connection() as connection:
                with _transaction(connection):
                    connection.execute("DELETE FROM evidence_events WHERE learner_id = ?", (learner_id,))
                    connection.execute("DELETE FROM reviewed_template_exposure WHERE learner_id = ?", (learner_id,))
                    connection.execute("DELETE FROM concept_state WHERE learner_id = ?", (learner_id,))
                    connection.execute("DELETE FROM misconception_state WHERE learner_id = ?", (learner_id,))
                    connection.execute(
                        "UPDATE learner_profiles SET last_seen_at = ?, state_version = 1 WHERE learner_id = ?",
                        (_now(), learner_id),
                    )
        except sqlite3.DatabaseError as error:
            raise LearnerStatePersistenceError(
                f"Local learner-state clear failed: {type(error).__name__}."
            ) from None

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, timeout=2.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 2000")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
        finally:
            connection.close()


@contextmanager
def _transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


_EXPOSURE_REASONS = frozenset(
    {
        "formal_answer_submitted",
        "hint_used",
        "answer_revealed",
        "migrated_existing_evidence",
    }
)


def _create_schema_v3(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS learner_profiles (
        learner_id TEXT PRIMARY KEY,
        course_id TEXT NOT NULL,
        preferred_style TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        state_version INTEGER NOT NULL)"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS concept_state (
        learner_id TEXT NOT NULL REFERENCES learner_profiles(learner_id) ON DELETE CASCADE,
        concept_id TEXT NOT NULL,
        mastery REAL NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (learner_id, concept_id))"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS misconception_state (
        learner_id TEXT NOT NULL REFERENCES learner_profiles(learner_id) ON DELETE CASCADE,
        misconception_id TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (learner_id, misconception_id))"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS evidence_events (
        event_id TEXT PRIMARY KEY,
        learner_id TEXT NOT NULL REFERENCES learner_profiles(learner_id) ON DELETE CASCADE,
        payload_json TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        schema_version INTEGER NOT NULL)"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_evidence_learner ON evidence_events(learner_id, occurred_at)")
    _create_reviewed_template_exposure_table(connection)


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    # v1 already had profiles and concept_state. Preserve all existing rows;
    # v2 adds only the minimal audit tables and index.
    connection.execute(
        """CREATE TABLE IF NOT EXISTS misconception_state (
        learner_id TEXT NOT NULL REFERENCES learner_profiles(learner_id) ON DELETE CASCADE,
        misconception_id TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (learner_id, misconception_id))"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS evidence_events (
        event_id TEXT PRIMARY KEY,
        learner_id TEXT NOT NULL REFERENCES learner_profiles(learner_id) ON DELETE CASCADE,
        payload_json TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        schema_version INTEGER NOT NULL)"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_evidence_learner ON evidence_events(learner_id, occurred_at)")


def _migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    """Add minimal template exposure and safely backfill readable old evidence."""
    _create_reviewed_template_exposure_table(connection)
    for row in connection.execute(
        "SELECT learner_id, payload_json, occurred_at FROM evidence_events ORDER BY occurred_at, event_id"
    ):
        learner_id, payload_text, occurred_at = (
            row["learner_id"], row["payload_json"], row["occurred_at"]
        )
        if not isinstance(learner_id, str) or not learner_id.strip():
            continue
        if not isinstance(occurred_at, str) or not occurred_at.strip():
            continue
        try:
            payload = json.loads(payload_text)
        except (TypeError, json.JSONDecodeError):
            continue
        if not _valid_evidence_payload(payload):
            continue
        for step in payload["steps"]:
            template_id = step["template_id"]
            connection.execute(
                """INSERT INTO reviewed_template_exposure
                (learner_id, template_id, first_exposed_at, exposure_reason, schema_version)
                VALUES (?, ?, ?, 'migrated_existing_evidence', 1)
                ON CONFLICT(learner_id, template_id) DO NOTHING""",
                (learner_id, template_id, occurred_at),
            )


def _create_reviewed_template_exposure_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS reviewed_template_exposure (
        learner_id TEXT NOT NULL REFERENCES learner_profiles(learner_id) ON DELETE CASCADE,
        template_id TEXT NOT NULL,
        first_exposed_at TEXT NOT NULL,
        exposure_reason TEXT NOT NULL,
        schema_version INTEGER NOT NULL,
        PRIMARY KEY (learner_id, template_id))"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_template_exposure_learner "
        "ON reviewed_template_exposure(learner_id, first_exposed_at)"
    )


def _learner_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 64:
        raise LearnerStatePersistenceError("learner_id is invalid.")
    return value.strip()


def _template_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise LearnerStatePersistenceError("template_id is invalid.")
    return value.strip()


def _state_snapshot(value: Any, learner_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LearnerStatePersistenceError("learner_state must be an object.")
    course_id = value.get("course_id")
    preferred_style = value.get("preferred_style")
    if not isinstance(course_id, str) or not course_id.strip():
        raise LearnerStatePersistenceError("learner_state.course_id is invalid.")
    if not isinstance(preferred_style, str) or not preferred_style.strip():
        raise LearnerStatePersistenceError("learner_state.preferred_style is invalid.")
    mastery = value.get("mastery")
    if not isinstance(mastery, dict):
        raise LearnerStatePersistenceError("learner_state.mastery is invalid.")
    normalized_mastery: dict[str, float] = {}
    for concept_id, score in mastery.items():
        if not isinstance(concept_id, str) or not concept_id.strip() or not _valid_score(score):
            raise LearnerStatePersistenceError("learner_state contains invalid mastery data.")
        normalized_mastery[concept_id] = float(score)
    misconceptions = value.get("misconceptions", [])
    if not isinstance(misconceptions, list):
        raise LearnerStatePersistenceError("learner_state.misconceptions is invalid.")
    normalized_misconceptions: list[str] = []
    for item in misconceptions:
        if isinstance(item, str):
            identifier = item.strip()
        elif isinstance(item, dict):
            identifier = item.get("misconception_id", "")
            identifier = identifier.strip() if isinstance(identifier, str) else ""
        else:
            identifier = ""
        if not identifier:
            raise LearnerStatePersistenceError("learner_state contains invalid misconception data.")
        if identifier not in normalized_misconceptions:
            normalized_misconceptions.append(identifier)
    return {
        "learner_id": learner_id,
        "course_id": course_id.strip(),
        "preferred_style": preferred_style.strip(),
        "mastery": normalized_mastery,
        "misconceptions": normalized_misconceptions,
    }


def _minimal_evidence_payload(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict) or summary.get("purpose") != "mastery_verification":
        raise LearnerStatePersistenceError("completed_summary must be mastery verification data.")
    if summary.get("evidence_eligible") is not True or summary.get("status") != "completed":
        raise LearnerStatePersistenceError("completed_summary is not eligible accepted evidence.")
    track_id = summary.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        raise LearnerStatePersistenceError("completed_summary.track_id is invalid.")
    steps = summary.get("step_results")
    if not isinstance(steps, list):
        raise LearnerStatePersistenceError("completed_summary.step_results is invalid.")
    compact_steps = []
    for step in steps:
        if not isinstance(step, dict):
            raise LearnerStatePersistenceError("completed_summary has invalid step data.")
        template_id = step.get("question_id")
        status = step.get("status")
        if not isinstance(template_id, str) or not template_id.strip() or status not in {"passed", "unresolved"}:
            raise LearnerStatePersistenceError("completed_summary has invalid reviewed-template evidence.")
        compact_steps.append({
            "template_id": template_id,
            "status": status,
            "attempts": _non_negative_int(step.get("attempts"), "attempts"),
            "final_attempt_assistance_level": _assistance_level(step.get("final_attempt_assistance_level", "none")),
        })
    payload = {
        "schema_version": 1,
        "track_id": track_id.strip(),
        "evidence_eligible": True,
        "passed_steps": _non_negative_int(summary.get("passed_steps"), "passed_steps"),
        "total_steps": _non_negative_int(summary.get("total_steps"), "total_steps"),
        "steps": compact_steps,
    }
    if payload["passed_steps"] > payload["total_steps"]:
        raise LearnerStatePersistenceError("completed_summary step counts are invalid.")
    if any(key in payload for key in _FORBIDDEN_EVIDENCE_KEYS):
        raise LearnerStatePersistenceError("completed_summary contains forbidden persisted data.")
    return payload


def _learner_evidence(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": summary["event_id"],
        "track_id": summary["track_id"],
        "evidence_eligible": True,
        "template_ids": [item["template_id"] for item in summary["steps"]],
        # Compact per-template outcomes already exist in the persisted
        # evidence payload. Restoring them into learner state lets the
        # recommendation layer distinguish exhausted independent success from
        # exhausted incorrect/assisted evidence without storing any answer.
        "template_outcomes": [
            {
                "template_id": item["template_id"],
                "status": item["status"],
                "final_attempt_assistance_level": item[
                    "final_attempt_assistance_level"
                ],
            }
            for item in summary["steps"]
        ],
        "passed_steps": summary["passed_steps"],
        "total_steps": summary["total_steps"],
    }


def _valid_evidence_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("schema_version") != 1 or value.get("evidence_eligible") is not True:
        return False
    if not isinstance(value.get("track_id"), str) or not value["track_id"].strip():
        return False
    if not isinstance(value.get("passed_steps"), int) or not isinstance(value.get("total_steps"), int):
        return False
    if value["passed_steps"] < 0 or value["total_steps"] < 0 or value["passed_steps"] > value["total_steps"]:
        return False
    steps = value.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            return False
        if not isinstance(step.get("template_id"), str) or step.get("status") not in {"passed", "unresolved"}:
            return False
        if isinstance(step.get("attempts"), bool) or not isinstance(step.get("attempts"), int) or step["attempts"] < 0:
            return False
        if step.get("final_attempt_assistance_level") not in {"none", "hint", "scaffold", "clarification", "reveal"}:
            return False
    return not any(key in value for key in _FORBIDDEN_EVIDENCE_KEYS)


def _valid_score(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LearnerStatePersistenceError(f"{name} must be a non-negative integer.")
    return value


def _assistance_level(value: Any) -> str:
    if value not in {"none", "hint", "scaffold", "clarification", "reveal"}:
        raise LearnerStatePersistenceError("assistance level is invalid.")
    return value


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _schema_lock(path: Path) -> Iterator[None]:
    """Prevent same-process first-open races across Streamlit tabs/reruns."""
    key = str(path.resolve())
    with _SCHEMA_LOCKS_GUARD:
        lock = _SCHEMA_LOCKS.setdefault(key, threading.Lock())
    with lock:
        yield
