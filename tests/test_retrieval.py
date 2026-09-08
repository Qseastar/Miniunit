import copy
from pathlib import Path

import pytest

from introai_tutor.course_materials import load_course_chunks
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.retrieval import retrieve_course_chunks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
CHUNKS_FILE = PROJECT_ROOT / "data" / "course_chunks.json"


@pytest.fixture(scope="module")
def course_data():
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    return load_course_chunks(CHUNKS_FILE, knowledge_data)


@pytest.fixture(scope="module")
def valid_topic_ids():
    return {
        point["id"]
        for point in load_knowledge_points(KNOWLEDGE_FILE)["knowledge_points"]
    }


def _retrieve(course_data, valid_topic_ids, query, **kwargs):
    return retrieve_course_chunks(
        course_data,
        query=query,
        valid_topic_ids=valid_topic_ids,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("query", "expected_prefix"),
    [
        ("BFS 为什么能找到最短路径？", "lec2_bfs"),
        ("What is BFS?", "lec2_bfs"),
        ("A-star search", "lec3_"),
        ("f(n) = g(n) + h(n)", "lec3_a_star_f_g_h"),
        ("admissibility", "lec3_"),
        ("一致性条件", "lec3_"),
        ("hill climbing", "lec4_hill_climbing"),
        ("模拟退火为什么能跳出局部最优？", "lec4_simulated_annealing"),
        ("Minimax", "lec5_minimax_search"),
        ("Alpha-Beta pruning", "lec5_alpha_beta_pruning"),
        ("UCB", "lec6_upper_confidence_bound"),
        ("MCTS", "lec6_"),
    ],
)
def test_real_material_queries_retrieve_expected_course_core(
    course_data, valid_topic_ids, query, expected_prefix
):
    results = _retrieve(course_data, valid_topic_ids, query)

    assert results
    assert results[0]["chunk"]["id"].startswith(expected_prefix)
    assert results[0]["chunk"]["source_role"] == "course_core"


def test_bfs_cost_question_returns_bfs_and_path_cost_material(course_data, valid_topic_ids):
    results = _retrieve(
        course_data,
        valid_topic_ids,
        "BFS 找到的是步数最少还是总代价最低？",
        top_k=10,
    )
    result_ids = {result["chunk"]["id"] for result in results}

    assert any(chunk_id.startswith("lec2_bfs") for chunk_id in result_ids)
    assert any("路径代价" in result["matched_terms"] for result in results)


def test_bfs_ucs_top_five_keeps_conceptual_core_evidence(course_data, valid_topic_ids):
    results = _retrieve(
        course_data,
        valid_topic_ids,
        "What is the difference between BFS and UCS?",
        top_k=5,
    )
    result_ids = {result["chunk"]["id"] for result in results}

    assert "lec2_bfs_properties" in result_ids
    assert "lec2_ucs_properties" in result_ids


def test_default_review_statuses_exclude_unreviewed_page_33(course_data, valid_topic_ids):
    results = _retrieve(course_data, valid_topic_ids, "对抗 MCTS 节点统计", top_k=10)

    assert "lec6_adversarial_mcts_statistics" not in {
        result["chunk"]["id"] for result in results
    }


def test_ucb_question_prefers_the_verified_ucb_chunk(course_data, valid_topic_ids):
    results = _retrieve(course_data, valid_topic_ids, "UCB 如何平衡探索和利用？")

    assert results[0]["chunk"]["id"] == "lec6_upper_confidence_bound"
    assert results[0]["chunk"]["review_status"] == "human_verified"


def test_explicit_review_status_allows_unreviewed_page_33(course_data, valid_topic_ids):
    results = _retrieve(
        course_data,
        valid_topic_ids,
        "对抗 MCTS 节点统计",
        top_k=10,
        allowed_review_statuses=(
            "codex_draft",
            "human_verified",
            "needs_human_review",
        ),
    )

    assert "lec6_adversarial_mcts_statistics" in {
        result["chunk"]["id"] for result in results
    }


def test_queue_bfs_query_keeps_course_core_and_can_return_support(
    course_data, valid_topic_ids
):
    results = _retrieve(course_data, valid_topic_ids, "队列为什么适合 BFS？", top_k=5)

    assert any(result["chunk"]["source_role"] == "course_core" for result in results)
    assert any(
        result["chunk"]["id"] == "support_queue_fifo" for result in results
    )


def test_can_exclude_prerequisite_support(course_data, valid_topic_ids):
    results = _retrieve(
        course_data,
        valid_topic_ids,
        "队列为什么适合 BFS？",
        top_k=10,
        include_prerequisite_support=False,
    )

    assert results
    assert all(result["chunk"]["source_role"] == "course_core" for result in results)


def test_dijkstra_and_ucs_keep_distinct_sources(course_data, valid_topic_ids):
    results = _retrieve(course_data, valid_topic_ids, "Dijkstra 和 UCS 有什么关系？", top_k=5)
    result_ids = {result["chunk"]["id"] for result in results}

    assert "support_dijkstra_shortest_path" in result_ids
    assert any(chunk_id.startswith("lec2_ucs") for chunk_id in result_ids)
    dijkstra = next(
        result for result in results if result["chunk"]["id"] == "support_dijkstra_shortest_path"
    )
    assert dijkstra["chunk"]["source_role"] == "prerequisite_support"
    assert "uniform_cost_search" in dijkstra["chunk"]["topic_ids"]


def test_unknown_topic_id_fails(course_data, valid_topic_ids):
    with pytest.raises(ValueError, match="Unknown topic_ids: invented_topic"):
        _retrieve(
            course_data,
            valid_topic_ids,
            "",
            topic_ids=["invented_topic"],
        )


def test_topic_ids_are_deduplicated_in_input_order(valid_topic_ids):
    data = {
        "chunks": [
            {
                "id": "both",
                "topic_ids": ["breadth_first_search", "uniform_cost_search"],
                "keywords": [],
                "section_title": "",
                "content": "",
                "source_role": "course_core",
                "review_status": "codex_draft",
            }
        ]
    }

    results = _retrieve(
        data,
        valid_topic_ids,
        "",
        topic_ids=["uniform_cost_search", "breadth_first_search", "uniform_cost_search"],
    )

    assert results[0]["matched_topic_ids"] == [
        "uniform_cost_search",
        "breadth_first_search",
    ]


def test_search_terms_are_stripped_deduplicated_and_ordered(valid_topic_ids):
    data = {
        "chunks": [
            {
                "id": "keywords",
                "topic_ids": [],
                "keywords": ["UCS", "BFS"],
                "section_title": "",
                "content": "",
                "source_role": "course_core",
                "review_status": "codex_draft",
            }
        ]
    }

    results = _retrieve(
        data,
        valid_topic_ids,
        "",
        search_terms=[" UCS ", "BFS", "ucs", "BFS"],
    )

    assert results[0]["matched_terms"] == ["ucs", "bfs"]


def test_empty_query_with_valid_topic_ids_retrieves(course_data, valid_topic_ids):
    results = _retrieve(
        course_data,
        valid_topic_ids,
        "",
        topic_ids=["uniform_cost_search"],
    )

    assert results
    assert results[0]["matched_topic_ids"] == ["uniform_cost_search"]


def test_no_effective_retrieval_information_returns_empty(course_data, valid_topic_ids):
    assert _retrieve(course_data, valid_topic_ids, "   ") == []


def test_unmatched_lexical_query_returns_empty(course_data, valid_topic_ids):
    assert _retrieve(course_data, valid_topic_ids, "quantum potato") == []


@pytest.mark.parametrize("top_k", [0, -1, True, "5"])
def test_invalid_top_k_fails(course_data, valid_topic_ids, top_k):
    with pytest.raises(ValueError, match="top_k"):
        _retrieve(course_data, valid_topic_ids, "BFS", top_k=top_k)


@pytest.mark.parametrize(
    "allowed_review_statuses",
    [("unknown",), "codex_draft", ("codex_draft", 3)],
)
def test_invalid_review_statuses_fail(course_data, valid_topic_ids, allowed_review_statuses):
    with pytest.raises(ValueError, match="allowed_review_statuses"):
        _retrieve(
            course_data,
            valid_topic_ids,
            "BFS",
            allowed_review_statuses=allowed_review_statuses,
        )


def test_sorting_is_stable_and_uses_document_order_on_equal_scores(valid_topic_ids):
    data = {
        "chunks": [
            {
                "id": "first",
                "topic_ids": [],
                "keywords": ["BFS"],
                "section_title": "",
                "content": "",
                "source_role": "course_core",
                "review_status": "codex_draft",
            },
            {
                "id": "second",
                "topic_ids": [],
                "keywords": ["BFS"],
                "section_title": "",
                "content": "",
                "source_role": "course_core",
                "review_status": "codex_draft",
            },
        ]
    }

    results = _retrieve(data, valid_topic_ids, "BFS", top_k=2)

    assert [result["chunk"]["id"] for result in results] == ["first", "second"]
    assert results[0]["score"] == results[1]["score"]


def test_multiword_phrase_does_not_repeat_component_token_scores(valid_topic_ids):
    data = {
        "chunks": [
            {
                "id": "alpha_beta",
                "topic_ids": [],
                "keywords": ["Alpha-Beta"],
                "section_title": "Alpha-Beta pruning",
                "content": "Alpha-Beta pruning.",
                "source_role": "course_core",
                "review_status": "codex_draft",
            },
            {
                "id": "alpha_only",
                "topic_ids": [],
                "keywords": ["AlphaGo"],
                "section_title": "AlphaGo",
                "content": "AlphaGo.",
                "source_role": "course_core",
                "review_status": "codex_draft",
            },
        ]
    }

    results = _retrieve(data, valid_topic_ids, "Alpha-Beta pruning", top_k=2)

    assert [result["chunk"]["id"] for result in results] == ["alpha_beta"]
    assert results[0]["matched_terms"] == ["alpha beta", "pruning"]
    assert "alpha" not in results[0]["matched_terms"]
    assert "beta" not in results[0]["matched_terms"]


def test_score_breakdown_sums_to_score(course_data, valid_topic_ids):
    result = _retrieve(course_data, valid_topic_ids, "UCB")[0]

    assert sum(result["score_breakdown"].values()) == result["score"]


def test_retrieval_does_not_mutate_course_data_or_chunks(course_data, valid_topic_ids):
    before = copy.deepcopy(course_data)
    original_chunk = course_data["chunks"][0]

    results = _retrieve(course_data, valid_topic_ids, "BFS")

    assert course_data == before
    assert original_chunk is course_data["chunks"][0]
    assert all("score" not in result["chunk"] for result in results)


def test_returned_chunk_keeps_source_metadata(course_data, valid_topic_ids):
    result = _retrieve(course_data, valid_topic_ids, "UCB")[0]
    chunk = result["chunk"]

    assert chunk["source_file"] == "ai_lec6_mcts_and_search_summary.pdf"
    assert chunk["page_start"] == 19
    assert chunk["page_end"] == 19
    assert chunk["source_role"] == "course_core"
    assert chunk["review_status"] == "human_verified"


@pytest.mark.parametrize(
    ("argument_name", "value", "message"),
    [
        ("query", None, "query must be a string"),
        ("topic_ids", ("breadth_first_search",), "topic_ids must be a list"),
        ("search_terms", ("BFS",), "search_terms must be a list"),
    ],
)
def test_invalid_query_and_list_inputs_fail(
    course_data, valid_topic_ids, argument_name, value, message
):
    kwargs = {argument_name: value}
    if argument_name != "query":
        kwargs["query"] = "BFS"

    with pytest.raises(ValueError, match=message):
        retrieve_course_chunks(
            course_data,
            valid_topic_ids=valid_topic_ids,
            **kwargs,
        )


def test_empty_search_term_fails(course_data, valid_topic_ids):
    with pytest.raises(ValueError, match="search_terms must not contain empty strings"):
        _retrieve(course_data, valid_topic_ids, "", search_terms=["  "])
