"""Deterministic lexical retrieval for local Search Algorithms material.

The retriever deliberately uses no embeddings, network calls, or mutable index.
It scores each chunk in the input document order using exact topic IDs and
normalized lexical matches. A matching chunk receives 200 points per requested
topic ID, 20 per ordinary keyword match, 8 per ordinary title match, and 1 per
ordinary content match. Direct algorithm expressions (for example ``UCB`` or
``A*``) receive 40, 16, and 3 points in those same fields so a named algorithm
outranks merely adjacent vocabulary such as "exploration".
Course-core chunks receive one additional point *only after* a real match, so
they win otherwise equal matches without allowing source role to create a hit.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


_ALLOWED_REVIEW_STATUSES = {
    "codex_draft",
    "human_verified",
    "needs_human_review",
}
_ENGLISH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "between",
    "can",
    "does",
    "how",
    "is",
    "of",
    "the",
    "to",
    "what",
    "why",
}
_MULTI_WORD_TERMS = (
    "a*",
    "alpha beta",
    "breadth first search",
    "depth first search",
    "hill climbing",
    "iterative deepening",
    "local search",
    "monte carlo search",
    "monte carlo tree search",
    "priority queue",
    "simulated annealing",
    "shortest path",
    "uniform cost search",
    "upper confidence bound",
)
_TERM_ALIASES = {
    # The course keywords use the adjective while student questions often use
    # the noun. This is a deterministic lexical alias, not semantic expansion.
    "admissibility": ("admissible",),
}
_PHRASE_ALIASES = {
    # The source consistently calls cumulative cost "路径代价"; students also
    # commonly ask about the same idea as "总代价".
    "总代价": ("路径代价",),
}
_KNOWN_CHINESE_TERMS = (
    "一致性",
    "可采纳",
    "局部最优",
    "探索",
    "利用",
    "最短路径",
    "模拟退火",
    "爬山法",
    "路径代价",
    "队列",
)
_ALGORITHM_ANCHORS = {
    "a*",
    "alpha beta",
    "bfs",
    "dfs",
    "dijkstra",
    "f(n)",
    "g(n)",
    "h(n)",
    "iddfs",
    "mcts",
    "minimax",
    "ucb",
    "ucs",
}


def retrieve_course_chunks(
    course_data: dict,
    *,
    query: str,
    valid_topic_ids: set[str] | list[str] | tuple[str, ...],
    topic_ids: list[str] | None = None,
    search_terms: list[str] | None = None,
    top_k: int = 5,
    include_prerequisite_support: bool = True,
    allowed_review_statuses: tuple[str, ...] = (
        "codex_draft",
        "human_verified",
    ),
) -> list[dict]:
    """Return the highest-scoring locally grounded course chunks.

    ``course_data`` is the document returned by ``load_course_chunks``. The
    function neither mutates that document nor adds retrieval metadata to its
    chunks. Topic matches are exact; text matching is deterministic normalized
    substring matching over keywords, section title, and content.
    """
    chunks = _validate_course_data(course_data)
    _validate_query(query)
    valid_topics = _validate_valid_topic_ids(valid_topic_ids)
    requested_topics = _validate_topic_ids(topic_ids, valid_topics)
    requested_search_terms = _validate_search_terms(search_terms)
    statuses = _validate_review_statuses(allowed_review_statuses)
    _validate_top_k(top_k)

    query_terms = _extract_match_terms(query)
    for search_term in requested_search_terms:
        query_terms = _ordered_unique(
            [*query_terms, *_extract_match_terms(search_term)]
        )

    if not requested_topics and not query_terms:
        return []

    results: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"course_data chunks[{index}] must be an object.")
        if chunk.get("review_status") not in statuses:
            continue
        if not include_prerequisite_support and chunk.get("source_role") == "prerequisite_support":
            continue

        result = _score_chunk(chunk, requested_topics, query_terms)
        if result is None:
            continue

        # Source role is a tie preference, never a reason to retrieve a chunk.
        if chunk.get("source_role") == "course_core":
            result["score_breakdown"]["source_role"] = 1.0
            result["score"] += 1.0
        results.append({"_index": index, **result})

    results.sort(key=lambda item: (-item["score"], item["_index"]))
    return [
        {
            "chunk": item["chunk"],
            "score": item["score"],
            "matched_topic_ids": item["matched_topic_ids"],
            "matched_terms": item["matched_terms"],
            "score_breakdown": item["score_breakdown"],
        }
        for item in results[:top_k]
    ]


def _score_chunk(
    chunk: dict[str, Any],
    requested_topics: list[str],
    query_terms: list[str],
) -> dict[str, Any] | None:
    chunk_topics = chunk.get("topic_ids", [])
    if not isinstance(chunk_topics, list):
        raise ValueError(f"Chunk '{chunk.get('id', '<unknown>')}' topic_ids must be a list.")
    matched_topics = [topic_id for topic_id in requested_topics if topic_id in chunk_topics]

    keywords_text = _normalize_text(" ".join(chunk.get("keywords", [])))
    title_text = _normalize_text(chunk.get("section_title", ""))
    content_text = _normalize_text(chunk.get("content", ""))
    keyword_matches = _matching_terms(query_terms, keywords_text)
    title_matches = _matching_terms(query_terms, title_text)
    content_matches = _matching_terms(query_terms, content_text)
    matched_terms = _ordered_unique(
        [*keyword_matches, *title_matches, *content_matches]
    )

    if not matched_topics and not matched_terms:
        return None

    score_breakdown = {
        "topic": float(200 * len(matched_topics)),
        "keyword": float(_field_score(keyword_matches, ordinary=20, anchor=40)),
        "title": float(_field_score(title_matches, ordinary=8, anchor=16)),
        "content": float(_field_score(content_matches, ordinary=1, anchor=3)),
        "source_role": 0.0,
    }
    return {
        "chunk": chunk,
        "score": sum(score_breakdown.values()),
        "matched_topic_ids": matched_topics,
        "matched_terms": matched_terms,
        "score_breakdown": score_breakdown,
    }


def _normalize_text(value: str) -> str:
    """Normalize Chinese/English lexical forms without losing algorithm names."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"(?<![a-z0-9])a\s*(?:-|–|—)?\s*star(?![a-z0-9])", "a*", normalized)
    normalized = re.sub(r"(?<![a-z0-9])a\s*\*(?![a-z0-9])", "a*", normalized)
    normalized = re.sub(r"(?<![a-z0-9])([fgh])\s*\(\s*n\s*\)(?![a-z0-9])", r"\1(n)", normalized)
    normalized = re.sub(r"[-–—_/]+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff*()\s]+", " ", normalized)
    return " ".join(normalized.split())


def _extract_match_terms(value: str) -> list[str]:
    normalized = _normalize_text(value)
    terms: list[str] = []

    for phrase in _MULTI_WORD_TERMS:
        if phrase in normalized:
            terms.append(phrase)
    phrase_components = {
        component
        for phrase in terms
        if " " in phrase
        for component in phrase.split()
    }

    for token in re.findall(r"a\*|[fgh]\(n\)|[a-z]+|\d+|[\u4e00-\u9fff]+", normalized):
        if "\u4e00" <= token[:1] <= "\u9fff":
            terms.extend(_chinese_phrases(token))
        elif len(token) >= 2 and token not in _ENGLISH_STOP_WORDS:
            if token in phrase_components:
                continue
            terms.append(token)
            terms.extend(_TERM_ALIASES.get(token, ()))

    for phrase, aliases in _PHRASE_ALIASES.items():
        if phrase in normalized:
            terms.extend(aliases)
    for term in _KNOWN_CHINESE_TERMS:
        if term in normalized:
            terms.append(term)

    return _ordered_unique(terms)


def _chinese_phrases(run: str) -> list[str]:
    """Return a continuous Chinese phrase plus bounded useful subphrases."""
    phrases = [run] if len(run) >= 2 else []
    max_length = min(6, len(run))
    # Very short overlapping fragments such as "路径" make broad Chinese
    # questions dominate algorithm acronyms. The complete phrase is always
    # retained; only longer subphrases provide partial-match recall.
    for length in range(4, max_length + 1):
        for start in range(0, len(run) - length + 1):
            phrases.append(run[start : start + length])
    return phrases


def _matching_terms(terms: list[str], field_text: str) -> list[str]:
    return [term for term in terms if term and term in field_text]


def _field_score(matches: list[str], *, ordinary: int, anchor: int) -> int:
    return sum(anchor if term in _ALGORITHM_ANCHORS else ordinary for term in matches)


def _validate_course_data(course_data: Any) -> list[Any]:
    if not isinstance(course_data, dict):
        raise ValueError("course_data must be an object containing a chunks list.")
    chunks = course_data.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("course_data['chunks'] must be a list.")
    return chunks


def _validate_query(query: Any) -> None:
    if not isinstance(query, str):
        raise ValueError("query must be a string.")


def _validate_valid_topic_ids(value: Any) -> set[str]:
    if not isinstance(value, (set, list, tuple)):
        raise ValueError("valid_topic_ids must be a set, list, or tuple of strings.")
    if any(not isinstance(topic_id, str) or not topic_id.strip() for topic_id in value):
        raise ValueError("valid_topic_ids must contain non-empty strings.")
    return set(value)


def _validate_topic_ids(value: Any, valid_topic_ids: set[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("topic_ids must be a list of strings.")
    if any(not isinstance(topic_id, str) or not topic_id.strip() for topic_id in value):
        raise ValueError("topic_ids must contain non-empty strings.")
    topics = _ordered_unique(value)
    unknown_topics = [topic_id for topic_id in topics if topic_id not in valid_topic_ids]
    if unknown_topics:
        raise ValueError(f"Unknown topic_ids: {', '.join(unknown_topics)}")
    return topics


def _validate_search_terms(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("search_terms must be a list of strings.")
    cleaned: list[str] = []
    for term in value:
        if not isinstance(term, str):
            raise ValueError("search_terms must contain strings.")
        stripped = term.strip()
        if not stripped:
            raise ValueError("search_terms must not contain empty strings.")
        cleaned.append(stripped)
    return _ordered_unique_by_normalized_value(cleaned)


def _validate_review_statuses(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("allowed_review_statuses must be a tuple or list of strings.")
    if any(not isinstance(status, str) for status in value):
        raise ValueError("allowed_review_statuses must contain strings.")
    invalid = [status for status in value if status not in _ALLOWED_REVIEW_STATUSES]
    if invalid:
        raise ValueError(
            "allowed_review_statuses contains unsupported values: "
            + ", ".join(_ordered_unique(invalid))
        )
    return tuple(_ordered_unique(value))


def _validate_top_k(top_k: Any) -> None:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _ordered_unique_by_normalized_value(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _normalize_text(value)
        if normalized not in seen:
            seen.add(normalized)
            result.append(value)
    return result
