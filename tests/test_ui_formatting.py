from introai_tutor.ui_formatting import (
    choice_text_by_id,
    citation_rows,
    format_pages,
    format_qa_result,
    escape_algorithm_markdown_tokens,
    mastery_rows,
    misconception_label,
    reset_session_state,
    source_role_label,
    update_rows,
    tracked_mastery_count,
    concept_display_name,
    format_concept_label,
)
from copy import deepcopy
from pathlib import Path

from introai_tutor.knowledge import load_knowledge_points


def _knowledge():
    return {
        "knowledge_points": [
            {
                "id": "breadth_first_search",
                "title_zh": "宽度优先搜索",
                "title_en": "Breadth-First Search",
            },
            {
                "id": "uniform_cost_search",
                "title_zh": "一致代价搜索",
                "title_en": "Uniform-Cost Search",
            },
        ]
    }


def test_format_pages_single_and_range():
    assert format_pages(3, 3) == "第 3 页"
    assert format_pages(3, 5) == "第 3–5 页"


def test_format_pages_rejects_invalid_range():
    for args in [(0, 1), (True, 1), (3, 2)]:
        try:
            format_pages(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid page range was accepted")


def test_source_role_labels_and_safe_unknown_fallback():
    assert source_role_label("course_core") == "课程核心材料"
    assert source_role_label("prerequisite_support") == "先修补充材料"
    assert source_role_label("other") == "other"


def test_choice_text_mapping_displays_text_but_preserves_internal_ids():
    choices = [
        {"id": "equal_cost", "text": "所有动作或边的代价相同"},
        {"id": "nonnegative", "text": "所有边权非负"},
    ]

    assert choice_text_by_id(choices) == {
        "equal_cost": "所有动作或边的代价相同",
        "nonnegative": "所有边权非负",
    }


def test_mastery_rows_use_titles_without_filling_missing_concepts():
    rows = mastery_rows(
        {"mastery": {"breadth_first_search": 0.45}},
        _knowledge(),
    )

    assert rows == [
        {
            "concept_id": "breadth_first_search",
            "title_zh": "宽度优先搜索",
            "title_en": "Breadth-First Search",
            "mastery": 0.45,
        }
    ]


def test_empty_mastery_has_zero_tracked_concepts():
    assert tracked_mastery_count(
        {
            "student_id": "streamlit_user",
            "mastery": {},
            "misconceptions": [],
            "learning_evidence": [],
        }
    ) == 0


def test_update_rows_show_titles_and_old_new_mastery():
    rows = update_rows(
        {
            "updates": [
                {
                    "concept_id": "uniform_cost_search",
                    "old_mastery": 0.2,
                    "selected_signal": 1.0,
                    "new_mastery": 0.48,
                    "observation_scores": [1.0],
                }
            ]
        },
        _knowledge(),
    )

    assert rows[0]["title_zh"] == "一致代价搜索"
    assert rows[0]["old_mastery"] == 0.2
    assert rows[0]["new_mastery"] == 0.48


def test_concept_display_names_use_authoritative_chinese_titles_and_safe_fallbacks():
    assert concept_display_name("uniform_cost_search", _knowledge()) == "一致代价搜索"
    assert format_concept_label("uniform_cost_search", _knowledge()) == "一致代价搜索"
    assert format_concept_label("uniform_cost_search", _knowledge(), developer=True) == "一致代价搜索（uniform_cost_search）"
    assert concept_display_name("unknown_concept", _knowledge()) == "未知知识点"
    assert format_concept_label("unknown_concept", _knowledge(), developer=True) == "未知知识点（unknown_concept）"


def test_all_real_concepts_have_non_internal_chinese_display_names():
    root = Path(__file__).resolve().parents[1]
    knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")

    for point in knowledge["knowledge_points"]:
        label = concept_display_name(point["id"], knowledge)
        assert label.strip()
        assert label != point["id"]
        assert "_" not in label


def test_update_rows_never_exposes_unknown_internal_id_to_student_table():
    rows = update_rows(
        {"updates": [{"concept_id": "unknown_concept", "old_mastery": 0.0, "new_mastery": 0.0}]},
        _knowledge(),
    )

    assert rows[0]["title_zh"] == "未知知识点"


def test_misconception_labels_and_unknown_fallback():
    assert "BFS" in misconception_label("bfs_is_depth_first")
    assert "总代价" in misconception_label("bfs_always_cost_optimal")
    assert misconception_label("new_rule") == "new_rule"


def test_citation_rows_format_pages_and_source_role():
    rows = citation_rows(
        {
            "answer_blocks": [
                {
                    "citations": [
                        {
                            "chunk_id": "bfs",
                            "source_file": "lec2.pdf",
                            "page_start": 3,
                            "page_end": 5,
                            "section_title": "BFS",
                            "source_role": "course_core",
                        }
                    ]
                }
            ]
        }
    )
    assert rows[0]["pages"] == "第 3–5 页"
    assert rows[0]["source_role_label"] == "课程核心材料"


def test_citation_rows_have_stable_source_order_and_deduplicate_same_physical_page():
    formula = {
        "chunk_id": "z_formula",
        "source_file": "lec3.pdf",
        "page_start": 16,
        "page_end": 25,
        "section_title": "公式说明",
        "source_role": "course_core",
    }
    same_page = {
        **formula,
        "chunk_id": "a_formula_duplicate",
        "section_title": "A* 搜索",
    }
    support = {
        "chunk_id": "queue_support",
        "source_file": "support.pdf",
        "page_start": 7,
        "page_end": 7,
        "section_title": "队列",
        "source_role": "prerequisite_support",
    }
    other_core = {
        "chunk_id": "a_star_property",
        "source_file": "lec3.pdf",
        "page_start": 26,
        "page_end": 26,
        "section_title": "A* 性质",
        "source_role": "course_core",
    }
    first = citation_rows(
        {"answer_blocks": [{"citations": [support, formula, other_core, same_page]}]}
    )
    second = citation_rows(
        {"answer_blocks": [{"citations": [same_page, other_core, support, formula]}]}
    )

    assert first == second
    assert [(row["source_file"], row["page_start"], row["chunk_id"]) for row in first] == [
        ("lec3.pdf", 16, "a_formula_duplicate"),
        ("lec3.pdf", 26, "a_star_property"),
        ("support.pdf", 7, "queue_support"),
    ]


def test_citation_rows_do_not_merge_distinct_overlapping_ranges():
    rows = citation_rows(
        {
            "answer_blocks": [
                {
                    "citations": [
                        {
                            "chunk_id": "formula",
                            "source_file": "lec3.pdf",
                            "page_start": 16,
                            "page_end": 25,
                            "section_title": "A* 公式",
                            "source_role": "course_core",
                        },
                        {
                            "chunk_id": "optimality",
                            "source_file": "lec3.pdf",
                            "page_start": 25,
                            "page_end": 29,
                            "section_title": "A* 最优性",
                            "source_role": "course_core",
                        },
                    ]
                }
            ]
        }
    )

    assert [(row["page_start"], row["page_end"]) for row in rows] == [(16, 25), (25, 29)]


def test_qa_result_formats_all_non_answer_states_safely():
    for status in ("out_of_scope", "needs_clarification", "insufficient_evidence"):
        view = format_qa_result(
            {"response": {"status": status, "answer": "message", "limitations": []}}
        )
        assert view["status"] == status
        assert view["status_label"]
        assert view["citations"] == []


def test_qa_result_formats_answered_citations():
    view = format_qa_result(
        {
            "response": {
                "status": "answered",
                "answer": "grounded",
                "limitations": ["limit"],
                "answer_blocks": [
                    {
                        "citations": [
                            {
                                "chunk_id": "bfs",
                                "source_file": "lec2.pdf",
                                "page_start": 1,
                                "page_end": 1,
                                "section_title": "BFS",
                                "source_role": "prerequisite_support",
                            }
                        ]
                    }
                ],
            }
        }
    )
    assert view["answer"] == "grounded"
    assert view["citations"][0]["source_role_label"] == "先修补充材料"
    assert view["limitations"] == ["limit"]


def test_qa_result_hides_known_chunk_markers_but_preserves_prose_and_sources():
    response = {
        "status": "answered",
        "answer": "BFS 按层扩展（lec2_bfs_layer_order）。普通括号 (A*) 应保留。",
        "used_chunk_ids": ["lec2_bfs_layer_order"],
        "limitations": [],
        "answer_blocks": [
            {
                "citations": [
                    {
                        "chunk_id": "lec2_bfs_layer_order",
                        "source_file": "ai_lec2_uninformed_search.pdf",
                        "page_start": 10,
                        "page_end": 10,
                        "section_title": "BFS",
                        "source_role": "course_core",
                    }
                ]
            }
        ],
    }
    view = format_qa_result({"response": response})

    assert "lec2_bfs_layer_order" not in view["answer"]
    assert "（lec2_bfs_layer_order）" not in view["answer"]
    assert "(A\\*)" in view["answer"]
    assert view["citations"][0]["chunk_id"] == "lec2_bfs_layer_order"
    assert view["citations"][0]["source_file"] == "ai_lec2_uninformed_search.pdf"


def test_qa_result_hides_ascii_and_fullwidth_known_chunk_markers_only():
    response = {
        "status": "answered",
        "answer": "one (chunk_a) two（chunk_b） three (ordinary note)",
        "used_chunk_ids": ["chunk_a"],
        "answer_blocks": [
            {
                "citations": [
                    {
                        "chunk_id": "chunk_b",
                        "source_file": "lec2.pdf",
                        "page_start": 1,
                        "page_end": 1,
                        "source_role": "course_core",
                    }
                ]
            }
        ],
    }

    answer = format_qa_result({"response": response})["answer"]

    assert "chunk_a" not in answer
    assert "chunk_b" not in answer
    assert "(ordinary note)" in answer


def test_qa_result_hides_all_known_bracket_forms_and_preserves_other_text():
    response = {
        "status": "answered",
        "answer": (
            "A (chunk_a) B（chunk_b） C [chunk_c] D【chunk_d】 "
            "普通括号 (A*) 普通方括号 [Markdown link] 未知 [chunk_unknown]"
        ),
        "used_chunk_ids": ["chunk_a", "chunk_b"],
        "citations": [{"chunk_id": "chunk_c"}, {"chunk_id": "chunk_d"}],
        "answer_blocks": [],
    }
    original = deepcopy(response)

    answer = format_qa_result({"response": response})["answer"]

    for chunk_id in ("chunk_a", "chunk_b", "chunk_c", "chunk_d"):
        assert chunk_id not in answer
    assert "(A\\*)" in answer
    assert "[Markdown link]" in answer
    assert "[chunk_unknown]" in answer
    assert response == original


def test_a_star_markdown_display_escaping_is_narrow_and_preserves_markdown():
    raw = (
        "A* 搜索与 A* 的 f(n)=g(n)+h(n)。\n\n"
        "**保留粗体**\n- 保留列表\n`A*` 保留代码文本"
    )

    displayed = escape_algorithm_markdown_tokens(raw)

    assert "A\\* 搜索" in displayed
    assert "A\\* 的 f(n)=g(n)+h(n)" in displayed
    assert "**保留粗体**" in displayed
    assert "- 保留列表" in displayed
    assert "`A*`" in displayed


def test_a_star_display_escape_applies_to_answer_and_citation_without_mutating_response():
    response = {
        "status": "answered",
        "answer": "A* 搜索使用 f(n)=g(n)+h(n)。",
        "used_chunk_ids": [],
        "limitations": [],
        "answer_blocks": [
            {
                "citations": [
                    {
                        "chunk_id": "astar",
                        "source_file": "lec3.pdf",
                        "page_start": 18,
                        "page_end": 18,
                        "section_title": "A* 搜索",
                        "source_role": "course_core",
                    }
                ]
            }
        ],
    }
    original = deepcopy(response)

    view = format_qa_result({"response": response})

    assert view["answer"] == "A\\* 搜索使用 f(n)=g(n)+h(n)。"
    assert view["citations"][0]["section_title"] == "A\\* 搜索"
    assert response == original


def test_reset_session_state_only_clears_introai_keys():
    state = {
        "introai_learner_state": {"mastery": {}},
        "introai_diagnostic_session": {},
        "introai_diagnostic_result": {},
        "introai_last_qa_result": {},
        "introai_qa_error": "error",
        "introai_qa_retry_state": {"question": "question"},
        "introai_qa_question": "question",
        "introai_qa_input_session_token": "a" * 32,
        "introai_qa_question_" + "a" * 32: "dynamic question",
        "introai_diagnostic_answer": "answer",
        "introai_diagnostic_answer_0_1": "dynamic answer",
        "introai_diagnostic_flash": {"type": "success"},
        "introai_diagnostic_error": "diagnostic error",
        "introai_dual_track_result": {},
        "introai_dual_track_session": {},
        "introai_diagnostic_mode": "formative",
        "introai_formative_feedback_error": True,
        "introai_formative_answer_1_1": "formative answer",
        "introai_verification_answer_1_1": "verification answer",
        "introai_last_recommendation": {"concept_id": "uniform_cost_search"},
        "introai_shared_deepseek_configuration_error": "configuration",
        "introai_pilot_tester_code": "G01",
        "introai_pilot_task_course_question_answering": True,
        "introai_pilot_prepared_feedback": {"schema_version": 1},
        "introai_pilot_anonymous_code": "G-ABCDEF",
        "introai_pilot_form_0_task_course_question_answering": True,
        "introai_pilot_serialized_feedback_json": b"{}\n",
        "other_key": "keep",
    }
    reset_session_state(state)

    assert state == {
        "introai_pilot_tester_code": "G01",
        "introai_pilot_task_course_question_answering": True,
        "introai_pilot_prepared_feedback": {"schema_version": 1},
        "introai_pilot_anonymous_code": "G-ABCDEF",
        "introai_pilot_form_0_task_course_question_answering": True,
        "introai_pilot_serialized_feedback_json": b"{}\n",
        "other_key": "keep",
    }
