import copy
import json
from collections import defaultdict
from pathlib import Path

import pytest

from introai_tutor.diagnostic_state_integration import (
    DiagnosticStateIntegrationService,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.ui_formatting import choice_text_by_id
from introai_tutor.template_selection import (
    DiagnosticTemplateError,
    SUPPORTED_SCORERS,
    TemplateSelectionService,
    load_diagnostic_templates,
    validate_diagnostic_templates,
)
from introai_tutor.verification_diagnostics import (
    VerificationDiagnosticError,
    VerificationDiagnosticService,
    score_verification_answer,
)
from tools.course_material_manifest import load_course_material_manifest, material_index
from tools.verification_quality_gate import validate_source_roles
from template_acceptance_cases import (
    PRODUCTION_MULTIPLE_CHOICE_DISPLAY_CONTRACTS,
    PRODUCTION_SINGLE_CHOICE_DISPLAY_CONTRACTS,
    PRODUCTION_TEMPLATE_ACCEPTANCE_CASES,
)


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_PATH = ROOT / "data" / "diagnostic_templates.json"
CANDIDATE_PATH = (
    ROOT
    / "data"
    / "candidate_templates"
    / "search_algorithms_p2c_candidates.json"
)
P2D_CANDIDATE_PATH = (
    ROOT
    / "data"
    / "candidate_templates"
    / "search_algorithms_p2d_candidates.json"
)
P2E_CANDIDATE_PATH = (
    ROOT
    / "data"
    / "candidate_templates"
    / "search_algorithms_p2e_candidates.json"
)
P2F_CANDIDATE_PATH = (
    ROOT
    / "data"
    / "candidate_templates"
    / "search_algorithms_p2f_candidates.json"
)
P5B_CANDIDATE_PATH = (
    ROOT
    / "data"
    / "candidate_templates"
    / "search_algorithms_p5b_candidates.json"
)
PROMOTED_TEMPLATE_IDS = {
    "verify_search_problem_components_v1",
    "verify_successor_operator_v1",
    "verify_frontier_explored_membership_v1",
}
P2D_PROMOTED_TEMPLATE_IDS = {
    "verify_graph_search_repeated_state_handling_v1",
    "verify_dfs_frontier_choice_v1",
    "verify_iddfs_depth_limit_schedule_v1",
}
P2E_CANDIDATE_TEMPLATE_IDS = {
    "verify_informed_search_g_h_roles_v1",
    "verify_greedy_min_h_choice_v1",
    "verify_astar_min_f_choice_v1",
    "verify_admissibility_no_overestimate_v1",
}
P2F_PROMOTED_TEMPLATE_IDS = {
    "verify_path_cost_accumulation_v1",
    "verify_search_node_state_distinction_v1",
    "verify_dfs_infinite_branch_risk_v1",
    "verify_search_algorithm_properties_v1",
    "verify_greedy_suboptimality_v1",
    "verify_astar_f_value_v1",
    "verify_consistency_edge_check_v1",
}
P5B_PROMOTED_TEMPLATE_IDS = {
    "verify_local_search_final_state_focus_v1",
    "verify_hill_climbing_stop_at_local_best_v1",
    "verify_simulated_annealing_worse_successor_v1",
    "verify_evolutionary_search_parent_cycle_v1",
    "verify_minimax_max_min_value_choice_v1",
    "verify_alpha_beta_prune_when_bounds_cross_v1",
    "verify_mcts_four_stage_order_v1",
    "verify_ucb_upper_bound_selection_v1",
}
EXPECTED_PRODUCTION_TEMPLATE_COUNT = 28


def _knowledge_data():
    return load_knowledge_points(ROOT / "data" / "knowledge_points.json")


def _concept_ids():
    return {point["id"] for point in _knowledge_data()["knowledge_points"]}


def _production_document():
    return load_diagnostic_templates(
        PRODUCTION_PATH,
        valid_concept_ids=_concept_ids(),
    )


def _production_templates():
    return {
        template["id"]: template
        for template in _production_document()["templates"]
    }


def _candidate_document():
    return json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))


def _p2d_candidate_document():
    return json.loads(P2D_CANDIDATE_PATH.read_text(encoding="utf-8"))


def _p2e_candidate_document():
    return json.loads(P2E_CANDIDATE_PATH.read_text(encoding="utf-8"))


def _p5b_candidate_document():
    return json.loads(P5B_CANDIDATE_PATH.read_text(encoding="utf-8"))


def _p2d_candidate_template_document():
    candidate = _p2d_candidate_document()
    return {
        "schema_version": candidate["schema_version"],
        "templates": copy.deepcopy(candidate["templates"]),
    }


def _p2e_candidate_template_document():
    candidate = _p2e_candidate_document()
    return {
        "schema_version": candidate["schema_version"],
        "templates": copy.deepcopy(candidate["templates"]),
    }


def _p2d_candidate_templates():
    return {
        template["id"]: template
        for template in _p2d_candidate_document()["templates"]
    }


def _p2e_candidate_templates():
    return {
        template["id"]: template
        for template in _p2e_candidate_document()["templates"]
    }


def _learner_state():
    return {
        "student_id": "template-acceptance",
        "course_id": "intro_ai",
        "mastery": {},
        "misconceptions": [],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }


def _complete(template, answer):
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template["id"]])
    return service, started, service.submit(
        session=started["session"],
        answer=copy.deepcopy(answer),
        submitted_template_id=template["id"],
    )


def _assert_source_refs_resolve(template, source_refs):
    chunks = {
        chunk["id"]: chunk
        for chunk in json.loads(
            (ROOT / "data" / "course_chunks.json").read_text(encoding="utf-8")
        )["chunks"]
    }
    materials = material_index(
        load_course_material_manifest(ROOT / "data" / "course_material_manifest.json")
    )
    entry = {
        "bank_type": "production",
        "primary_concept": template["concept_ids"][0],
        "source_expectations": source_refs,
    }
    assert validate_source_roles(entry, chunks, materials) == []


def test_all_production_templates_have_unique_ids_and_acceptance_cases():
    document = _production_document()
    template_ids = [template["id"] for template in document["templates"]]

    assert len(template_ids) == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert len(template_ids) == len(set(template_ids))
    assert set(template_ids) == set(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES)


def test_all_production_choice_display_mappings_match_registry_text():
    for template in _production_document()["templates"]:
        registry_mapping = {
            choice["id"]: choice["text"] for choice in template["choices"]
        }

        assert all(text.strip() for text in registry_mapping.values())
        assert choice_text_by_id(template["choices"]) == registry_mapping


def test_single_choice_ids_expected_answers_and_display_order_are_stable():
    first = _production_templates()
    second = _production_templates()
    single_choice_ids = {
        template_id
        for template_id, template in first.items()
        if template["deterministic_scorer"] == "single_choice_v1"
    }

    assert single_choice_ids == set(
        PRODUCTION_SINGLE_CHOICE_DISPLAY_CONTRACTS
    )
    for template_id, contract in (
        PRODUCTION_SINGLE_CHOICE_DISPLAY_CONTRACTS.items()
    ):
        first_template = first[template_id]
        second_template = second[template_id]
        first_ids = [choice["id"] for choice in first_template["choices"]]
        second_ids = [choice["id"] for choice in second_template["choices"]]
        expected_id = first_template["expected_answer"]["choice_id"]

        assert first_ids == contract["choice_ids"]
        assert second_ids == first_ids
        assert len(first_ids) == len(set(first_ids))
        assert expected_id == contract["expected_choice_id"]
        assert expected_id in first_ids
        assert first_ids.index(expected_id) == second_ids.index(expected_id)


def test_single_choice_answer_positions_are_static_and_in_range():
    positions_by_choice_count = defaultdict(list)
    for template_id, contract in (
        PRODUCTION_SINGLE_CHOICE_DISPLAY_CONTRACTS.items()
    ):
        choice_ids = contract["choice_ids"]
        positions_by_choice_count[len(choice_ids)].append(
            choice_ids.index(contract["expected_choice_id"]) + 1
        )

    assert set(positions_by_choice_count) == {3, 4}
    for choice_count, positions in positions_by_choice_count.items():
        assert all(1 <= position <= choice_count for position in positions)


def test_multiple_choice_display_order_is_reviewed_without_single_choice_quota():
    templates = _production_templates()
    multiple_choice_ids = {
        template_id
        for template_id, template in templates.items()
        if template["deterministic_scorer"] == "multiple_choice_v1"
    }

    assert multiple_choice_ids == set(
        PRODUCTION_MULTIPLE_CHOICE_DISPLAY_CONTRACTS
    )
    for template_id, expected_order in (
        PRODUCTION_MULTIPLE_CHOICE_DISPLAY_CONTRACTS.items()
    ):
        actual_order = [
            choice["id"] for choice in templates[template_id]["choices"]
        ]
        assert actual_order == expected_order

    formulation = templates["verify_search_problem_components_v1"]
    formulation_order = [
        choice["id"] for choice in formulation["choices"]
    ]
    correct_positions = [
        formulation_order.index(choice_id) + 1
        for choice_id in formulation["expected_answer"]["choice_ids"]
    ]
    wrong_positions = [
        position
        for position in range(1, len(formulation_order) + 1)
        if position not in correct_positions
    ]
    assert correct_positions == [1, 3, 4, 6, 7]
    assert wrong_positions == [2, 5]

    g_h = templates["verify_informed_search_g_h_roles_v1"]
    g_h_order = [choice["id"] for choice in g_h["choices"]]
    g_h_correct_positions = [
        g_h_order.index(choice_id) + 1
        for choice_id in g_h["expected_answer"]["choice_ids"]
    ]
    assert g_h_correct_positions == [1, 3]


def test_all_production_templates_reference_known_primary_concepts():
    known = _concept_ids()
    for template_id, template in _production_templates().items():
        case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]
        expected_concepts = [
            case["primary_concept_id"],
            *case["additional_mastery_concept_ids"],
        ]
        assert template["concept_ids"] == expected_concepts
        assert set(expected_concepts) <= known
        if len(expected_concepts) == 1:
            assert case["multi_concept_rationale"] is None
        else:
            assert (
                isinstance(case["multi_concept_rationale"], str)
                and case["multi_concept_rationale"].strip()
            )


def test_all_production_templates_have_registered_matching_scorers():
    for template in _production_templates().values():
        assert template["deterministic_scorer"] in SUPPORTED_SCORERS
        service = VerificationDiagnosticService(templates=[template])
        assert service.start(template_ids=[template["id"]])["question"][
            "question_type"
        ] == template["question_type"]


def test_all_production_templates_have_valid_sources():
    for template_id, template in _production_templates().items():
        _assert_source_refs_resolve(
            template,
            PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]["source_refs"],
        )


@pytest.mark.smoke
@pytest.mark.parametrize(
    "template_id", sorted(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES)
)
def test_all_production_templates_accept_expected_answer(template_id):
    template = _production_templates()[template_id]
    answer = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]["correct_answer"]

    _service, _started, completed = _complete(template, answer)

    assert completed["evaluation"]["score"] == 1.0
    assert completed["evaluation"]["passed"] is True
    assert completed["status"] == "completed"


@pytest.mark.parametrize(
    "template_id", sorted(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES)
)
def test_all_production_templates_reject_known_wrong_answer(template_id):
    template = _production_templates()[template_id]
    answer = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]["wrong_answer"]

    _service, _started, result = _complete(template, answer)

    assert result["evaluation"]["score"] == 0.0
    assert result["evaluation"]["passed"] is False
    assert result["summary"] is None


@pytest.mark.parametrize(
    ("template_id", "answer"),
    [
        (template_id, answer)
        for template_id, case in PRODUCTION_TEMPLATE_ACCEPTANCE_CASES.items()
        for answer in case.get("additional_wrong_answers", [])
    ],
)
def test_production_templates_reject_additional_reviewed_wrong_answers(
    template_id, answer
):
    template = _production_templates()[template_id]

    _service, _started, result = _complete(template, answer)

    assert result["evaluation"]["score"] == 0.0
    assert result["evaluation"]["passed"] is False
    assert result["summary"] is None


@pytest.mark.parametrize(
    "template_id", sorted(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES)
)
@pytest.mark.smoke
def test_all_production_templates_reject_malformed_without_attempt(template_id):
    template = _production_templates()[template_id]
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template_id])
    original = copy.deepcopy(started["session"])

    with pytest.raises(VerificationDiagnosticError):
        service.submit(
            session=started["session"],
            answer=PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id][
                "malformed_answer"
            ],
            submitted_template_id=template_id,
        )

    assert started["session"] == original
    assert started["session"]["history"] == []


@pytest.mark.parametrize(
    "template_id", sorted(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES)
)
def test_all_production_templates_are_repeatable_and_json_serializable(template_id):
    template = _production_templates()[template_id]
    answer = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]["correct_answer"]
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template_id])

    first = service.submit(
        session=started["session"],
        answer=copy.deepcopy(answer),
        submitted_template_id=template_id,
    )
    second = service.submit(
        session=started["session"],
        answer=copy.deepcopy(answer),
        submitted_template_id=template_id,
    )

    assert first == second
    json.dumps(first, allow_nan=False)


@pytest.mark.parametrize(
    "template_id", sorted(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES)
)
@pytest.mark.smoke
def test_all_production_templates_complete_through_existing_evidence_pipeline(
    template_id,
):
    template = _production_templates()[template_id]
    answer = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]["correct_answer"]
    _service, started, completed = _complete(template, answer)
    state = _learner_state()
    original = copy.deepcopy(state)

    update = DiagnosticStateIntegrationService(
        knowledge_data=_knowledge_data(),
        recommendation_fn=lambda *_args: None,
    ).apply(learner_state=state, diagnostic_summary=completed["summary"])

    assert started["summary"] is None
    assert all(item["selected_signal"] == 1.0 for item in update["updates"])
    assert state == original


@pytest.mark.parametrize(
    "template_id", sorted(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES)
)
def test_all_production_templates_reveal_only_creates_no_mastery_evidence(
    template_id,
):
    template = _production_templates()[template_id]
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template_id])
    revealed = service.request_reveal(
        session=started["session"], template_id=template_id
    )
    completed = service.acknowledge_reveal(
        session=revealed["session"], template_id=template_id
    )
    state = _learner_state()

    update = DiagnosticStateIntegrationService(
        knowledge_data=_knowledge_data(),
        recommendation_fn=lambda *_args: None,
    ).apply(learner_state=state, diagnostic_summary=completed["summary"])

    assert completed["summary"]["concept_observations"] == {}
    assert completed["summary"]["no_observation_reason"] == "all_revealed"
    assert update["learner_state"] == state


def test_unknown_production_contract_inputs_still_fail_closed():
    invalid = copy.deepcopy(_production_document())
    invalid["templates"][0]["concept_ids"] = ["unknown_concept"]
    with pytest.raises(DiagnosticTemplateError, match="unknown concept"):
        validate_diagnostic_templates(
            invalid,
            valid_concept_ids=_concept_ids(),
        )

    invalid = copy.deepcopy(_production_document())
    invalid["templates"][0]["deterministic_scorer"] = "unknown_v1"
    with pytest.raises(DiagnosticTemplateError, match="unsupported"):
        validate_diagnostic_templates(
            invalid,
            valid_concept_ids=_concept_ids(),
        )


def test_promoted_candidate_batch_is_no_longer_active():
    candidate = _candidate_document()
    assert candidate == {
        "schema_version": 1,
        "candidate_batch_id": "search_algorithms_p2c_a",
        "candidate_status": "promoted_to_production",
        "templates": [],
        "acceptance_cases": {},
    }
    with pytest.raises(
        DiagnosticTemplateError,
        match="exactly schema_version and templates",
    ):
        load_diagnostic_templates(
            CANDIDATE_PATH,
            valid_concept_ids=_concept_ids(),
        )


def test_promoted_production_content_matches_human_approved_boundaries():
    templates = _production_templates()
    cases = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES

    formulation = templates["verify_search_problem_components_v1"]
    formulation_choices = {
        choice["id"]: choice["text"] for choice in formulation["choices"]
    }
    expected_components = {
        "initial_state",
        "actions",
        "transition_model",
        "goal_test",
        "path_cost",
    }
    assert "五个组成部分" in formulation["prompt"]
    assert set(formulation["expected_answer"]["choice_ids"]) == expected_components
    assert set(cases[formulation["id"]]["correct_answer"]) == expected_components
    assert "state_space" not in formulation_choices
    assert formulation_choices["transition_model"] == "状态转移模型"
    assert score_verification_answer(
        template=formulation,
        answer=cases[formulation["id"]]["wrong_answer"],
    )["passed"] is False
    assert score_verification_answer(
        template=formulation,
        answer=[*sorted(expected_components), "algorithm_choice"],
    )["passed"] is False

    path_cost = templates["verify_path_cost_accumulation_v1"]
    path_cost_choices = {
        choice["id"]: choice["text"] for choice in path_cost["choices"]
    }
    assert [choice["id"] for choice in path_cost["choices"]] == [
        "last_step_only",
        "two_actions",
        "three_action_costs",
        "four_nodes",
    ]
    assert path_cost_choices["two_actions"] == "2，只计算其中两个行动的代价"
    assert choice_text_by_id(path_cost["choices"]) == path_cost_choices
    assert path_cost["expected_answer"] == {"choice_id": "three_action_costs"}
    assert path_cost["deterministic_scorer"] == "single_choice_v1"
    assert score_verification_answer(
        template=path_cost,
        answer="two_actions",
    )["passed"] is False
    assert score_verification_answer(
        template=path_cost,
        answer="three_action_costs",
    )["passed"] is True

    successor = templates["verify_successor_operator_v1"]
    successor_explanation = successor["teaching_support"]["explanation"]
    assert "以下四个候选状态中" in successor["prompt"]
    assert "合法 operator 有向右和向下" in successor_explanation
    assert "另一个合法 successor 没有出现在选项中" in successor_explanation
    assert "全局只有一个合法 successor" in successor_explanation
    assert successor["expected_answer"] == {"choice_id": "move_right"}

    membership = templates["verify_frontier_explored_membership_v1"]
    membership_sources = {
        (
            source["chunk_id"],
            source["page_start"],
            source["page_end"],
        )
        for source in cases[membership["id"]]["source_refs"]
    }
    membership_choices = {
        choice["id"]: choice["text"] for choice in membership["choices"]
    }
    assert "graph-search 约定" in membership["prompt"]
    assert "frontier 保存已经生成但尚未扩展的搜索节点" in membership["prompt"]
    assert "把它表示的状态加入 explored" in membership["prompt"]
    assert "在第2步完成后" in membership["prompt"]
    assert membership_choices["x_frontier"] == "节点 X 位于 frontier"
    assert membership_choices["y_explored"] == "状态 Y 位于 explored"
    assert set(membership["expected_answer"]["choice_ids"]) == {
        "x_frontier",
        "y_explored",
    }
    assert membership_sources == {
        ("lec2_frontier_expansion", 20, 20),
        ("lec2_graph_search_repeated_states", 27, 27),
    }
    explanation = membership["teaching_support"]["explanation"]
    assert "frontier=[Y]" in explanation
    assert "frontier=[]" in explanation
    assert "frontier=[X]" in explanation
    assert "所有教材和实现的唯一规则" in explanation


def test_promoted_ids_exist_once_in_production_and_not_in_active_staging():
    candidate = _candidate_document()
    candidate_ids = {item["id"] for item in candidate["templates"]}
    production = _production_document()
    production_ids = {item["id"] for item in production["templates"]}

    assert len(production_ids) == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert PROMOTED_TEMPLATE_IDS <= production_ids
    assert candidate_ids.isdisjoint(production_ids)
    assert candidate_ids == set()

    selector = TemplateSelectionService(
        templates_data=production,
        valid_concept_ids=_concept_ids(),
    )
    selected_ids = {
        item["id"]
        for concept_id in _concept_ids()
        for intent in ("diagnostic_request", "definition", "explanation")
        for item in selector.select(concept_ids=[concept_id], intent=intent)
    }
    assert PROMOTED_TEMPLATE_IDS <= selected_ids
    assert P5B_PROMOTED_TEMPLATE_IDS <= selected_ids


@pytest.mark.parametrize(
    "template_id",
    sorted(
        PROMOTED_TEMPLATE_IDS
        | P2D_PROMOTED_TEMPLATE_IDS
        | P2E_CANDIDATE_TEMPLATE_IDS
        | P2F_PROMOTED_TEMPLATE_IDS
        | P5B_PROMOTED_TEMPLATE_IDS
    ),
)
def test_promoted_template_hint_assisted_pass_uses_prior_independent_zero(
    template_id,
):
    template = _production_templates()[template_id]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template_id])
    failed = service.submit(
        session=started["session"],
        answer=copy.deepcopy(case["wrong_answer"]),
        submitted_template_id=template_id,
    )
    retry = service.choose_hint_retry(
        session=failed["session"], template_id=template_id
    )
    completed = service.submit(
        session=retry["session"],
        answer=copy.deepcopy(case["correct_answer"]),
        submitted_template_id=template_id,
    )
    state_update = DiagnosticStateIntegrationService(
        knowledge_data=_knowledge_data(),
        recommendation_fn=lambda *_args: None,
    ).apply(
        learner_state=_learner_state(),
        diagnostic_summary=completed["summary"],
    )

    assert completed["status"] == "completed"
    assert [
        (item["score"], item["assisted"])
        for item in completed["session"]["history"]
    ] == [(0.0, False), (1.0, True)]
    assert state_update["updates"][0]["selected_signal"] == 0.0


def test_p2d_promoted_candidate_batch_is_no_longer_active():
    candidate = _p2d_candidate_document()

    assert candidate == {
        "schema_version": 1,
        "candidate_batch_id": "search_algorithms_p2d_a",
        "candidate_status": "promoted_to_production",
        "templates": [],
        "acceptance_cases": {},
    }
    with pytest.raises(
        DiagnosticTemplateError,
        match="exactly schema_version and templates",
    ):
        load_diagnostic_templates(
            P2D_CANDIDATE_PATH,
            valid_concept_ids=_concept_ids(),
        )


def test_p2d_promoted_templates_have_unique_primary_concepts_and_resolvable_sources():
    candidate = _p2d_candidate_document()
    templates = _production_templates()
    cases = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES
    production_ids = set(templates)

    assert candidate["templates"] == []
    assert candidate["acceptance_cases"] == {}
    assert len(production_ids) == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert P2D_PROMOTED_TEMPLATE_IDS <= production_ids
    for template_id in P2D_PROMOTED_TEMPLATE_IDS:
        template = templates[template_id]
        case = cases[template_id]
        assert template["concept_ids"] == [case["primary_concept_id"]]
        assert template["misconception_rules"] == []
        assert case["primary_concept_id"] in _concept_ids()
        _assert_source_refs_resolve(template, case["source_refs"])


@pytest.mark.parametrize(
    "template_id",
    [
        "verify_graph_search_repeated_state_handling_v1",
        "verify_dfs_frontier_choice_v1",
        "verify_iddfs_depth_limit_schedule_v1",
    ],
)
def test_p2d_promoted_templates_pass_positive_negative_and_malformed_contracts(
    template_id,
):
    template = _production_templates()[template_id]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]

    positive = score_verification_answer(
        template=template,
        answer=copy.deepcopy(case["correct_answer"]),
    )
    negative = score_verification_answer(
        template=template,
        answer=copy.deepcopy(case["wrong_answer"]),
    )
    with pytest.raises(VerificationDiagnosticError):
        score_verification_answer(
            template=template,
            answer=copy.deepcopy(case["malformed_answer"]),
        )

    assert (positive["score"], positive["passed"]) == (1.0, True)
    assert (negative["score"], negative["passed"]) == (0.0, False)
    assert positive == score_verification_answer(
        template=template,
        answer=copy.deepcopy(case["correct_answer"]),
    )
    json.dumps({"template": template, "positive": positive}, allow_nan=False)


def test_p2d_promoted_ids_exist_once_and_candidate_staging_is_isolated():
    candidate_ids = set(_p2d_candidate_templates())
    production = _production_document()
    production_ids = {item["id"] for item in production["templates"]}
    selector = TemplateSelectionService(
        templates_data=production,
        valid_concept_ids=_concept_ids(),
    )

    with pytest.raises(DiagnosticTemplateError):
        load_diagnostic_templates(
            P2D_CANDIDATE_PATH,
            valid_concept_ids=_concept_ids(),
        )
    selected_ids = {
        item["id"]
        for concept_id in _concept_ids()
        for intent in ("diagnostic_request", "definition", "explanation")
        for item in selector.select(concept_ids=[concept_id], intent=intent)
    }
    assert candidate_ids == set()
    assert candidate_ids.isdisjoint(production_ids)
    assert len(production_ids) == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert P2D_PROMOTED_TEMPLATE_IDS <= selected_ids
    VerificationDiagnosticService(
        templates=[
            _production_templates()[template_id]
            for template_id in sorted(P2D_PROMOTED_TEMPLATE_IDS)
        ]
    )


def test_p2d_repeated_state_production_template_applies_reviewed_p27_condition():
    template = _production_templates()[
        "verify_graph_search_repeated_state_handling_v1"
    ]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template["id"]]
    explanation = template["teaching_support"]["explanation"]

    assert template["review_status"] == "human_verified"
    assert template["concept_ids"] == ["tree_search_vs_graph_search"]
    assert "Lec2 p.27" in template["prompt"]
    assert "将其中的 closed 称为 explored" in template["prompt"]
    assert "frontier 保存 search node" in template["prompt"]
    assert "STATE[node]" in template["prompt"]
    assert "节点 N" in template["prompt"]
    assert "STATE[N]=S" in template["prompt"]
    assert "若已经存在，就丢弃" not in template["prompt"]
    assert "不再次扩展这个 state" not in template["prompt"]
    assert template["expected_answer"] == {"choice_id": "discard_repeat"}
    assert case["source_refs"] == [
        {
            "chunk_id": "lec2_graph_search_repeated_states",
            "source_file": "ai_lec2_uninformed_search.pdf",
            "page_start": 27,
            "page_end": 27,
        }
    ]
    assert "另一个 search node" in explanation
    assert "同一个 problem state" in explanation
    assert "不涵盖生成时去重" in explanation
    assert "reopening" in explanation
    assert "lower-cost replacement" in explanation


def test_p2d_dfs_production_template_has_unique_lifo_frontier_choice():
    template = _production_templates()["verify_dfs_frontier_choice_v1"]
    explanation = template["teaching_support"]["explanation"]

    assert template["review_status"] == "human_verified"
    assert template["concept_ids"] == ["depth_first_search"]
    assert template["prompt"].startswith("本题中的 DFS 实现使用 stack")
    assert "栈底 → 栈顶" in template["prompt"]
    assert "A 最先入栈，随后是 B，最后是 C" in template["prompt"]
    assert template["expected_answer"] == {"choice_id": "node_c"}
    assert "比 A 更深" in explanation
    assert "B 和 C 都处于 depth=2" in explanation
    assert "C 在 B 之后入栈" in explanation
    assert "后进先出" in explanation
    assert "deepest-first" in explanation
    assert "完备性、最优性或复杂度" in explanation


def test_p2d_iddfs_production_template_declares_starting_limit_and_restart_behavior():
    template = _production_templates()[
        "verify_iddfs_depth_limit_schedule_v1"
    ]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template["id"]]
    explanation = template["teaching_support"]["explanation"]

    assert template["review_status"] == "human_verified"
    assert template["concept_ids"] == ["iterative_deepening_search"]
    assert "depth limit 依次为 0、1、2" in template["prompt"]
    assert "每一轮都从根节点重新运行" in template["prompt"]
    assert template["expected_answer"] == {"choice_id": "restart_limit_2"}
    assert case["source_refs"] == [
        {
            "chunk_id": "lec2_iddfs_strategy",
            "source_file": "ai_lec2_uninformed_search.pdf",
            "page_start": 53,
            "page_end": 57,
        }
    ]
    assert "p.53 的文字从 limit=1 开始展示" in explanation
    assert "p.54–55 的动画明确包含 limit=0 和 limit=1" in explanation
    assert "反复运行 depth-limited DFS" in explanation
    assert "下一轮应把 limit 提高到 2" in explanation
    assert "而不是继续上一轮暂停的 DFS" in explanation
    assert "复杂度、完备性或最优性" in explanation
    assert "不是独立的 mastery concept" in explanation
    assert "depth_limited_search" not in template["concept_ids"]


def test_p2e_promoted_candidate_batch_is_no_longer_active():
    assert _p2e_candidate_document() == {
        "schema_version": 1,
        "candidate_batch_id": "search_algorithms_p2e_a",
        "candidate_status": "promoted_to_production",
        "templates": [],
        "acceptance_cases": {},
    }

    with pytest.raises(DiagnosticTemplateError, match="exactly schema_version and templates"):
        load_diagnostic_templates(
            P2E_CANDIDATE_PATH,
            valid_concept_ids=_concept_ids(),
        )


@pytest.mark.parametrize("template_id", sorted(P2E_CANDIDATE_TEMPLATE_IDS))
def test_p2e_promoted_templates_have_single_primary_concept_and_sources(template_id):
    template = _production_templates()[template_id]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]

    assert template["review_status"] == "human_verified"
    assert template["purpose"] == "mastery_verification"
    assert template["concept_ids"] == [case["primary_concept_id"]]
    assert template["question_type"] == case["question_type"]
    assert template["deterministic_scorer"] == case["deterministic_scorer"]
    assert case["evidence_strength"] == "direct"
    assert template["misconception_rules"] == []
    _assert_source_refs_resolve(template, case["source_refs"])


@pytest.mark.parametrize("template_id", sorted(P2E_CANDIDATE_TEMPLATE_IDS))
def test_p2e_promoted_template_scorers_pass_wrong_and_malformed(template_id):
    template = _production_templates()[template_id]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]

    positive = score_verification_answer(
        template=template, answer=copy.deepcopy(case["correct_answer"])
    )
    negative = score_verification_answer(
        template=template, answer=copy.deepcopy(case["wrong_answer"])
    )
    with pytest.raises(VerificationDiagnosticError):
        score_verification_answer(
            template=template, answer=copy.deepcopy(case["malformed_answer"])
        )

    assert (positive["score"], positive["passed"]) == (1.0, True)
    assert (negative["score"], negative["passed"]) == (0.0, False)


def test_p2e_promoted_template_boundaries_and_answer_positions_are_locked():
    templates = _production_templates()
    g_h = templates["verify_informed_search_g_h_roles_v1"]
    greedy = templates["verify_greedy_min_h_choice_v1"]
    astar = templates["verify_astar_min_f_choice_v1"]
    admissibility = templates["verify_admissibility_no_overestimate_v1"]

    assert g_h["deterministic_scorer"] == "multiple_choice_v1"
    assert g_h["expected_answer"] == {
        "choice_ids": ["g_path_cost", "h_goal_estimate"]
    }
    assert g_h["eligible_intents"] == [
        "diagnostic_request", "definition", "explanation", "comparison"
    ]
    assert "algorithm_trace" not in g_h["eligible_intents"]
    assert g_h["concept_ids"] == ["informed_search_and_heuristics"]
    assert "frontier 选择" in g_h["teaching_support"]["explanation"]

    assert greedy["expected_answer"] == {"choice_id": "node_b"}
    assert [item["id"] for item in greedy["choices"]].index("node_b") == 1
    assert "g+h" in greedy["teaching_support"]["explanation"]
    assert "最优性" not in greedy["prompt"]
    assert greedy["concept_ids"] == ["greedy_best_first_search"]

    assert astar["expected_answer"] == {"choice_id": "node_c"}
    assert [item["id"] for item in astar["choices"]] == [
        "node_a", "node_b", "node_c", "node_d"
    ]
    assert [item["id"] for item in astar["choices"]].index("node_c") == 2
    assert "f(n)=g(n)+h(n)" in astar["prompt"]
    assert "可采纳性" not in astar["prompt"]
    assert astar["concept_ids"] == ["a_star_search"]
    assert PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[
        "verify_astar_min_f_choice_v1"
    ]["source_refs"] == [
        {
            "chunk_id": "lec3_a_star_f_g_h",
            "source_file": "ai_lec3_informed_search.pdf",
            "page_start": 18,
            "page_end": 18,
        },
        {
            "chunk_id": "lec3_a_star_f_g_h",
            "source_file": "ai_lec3_informed_search.pdf",
            "page_start": 21,
            "page_end": 21,
        },
    ]

    assert admissibility["expected_answer"] == {"choice_id": "equal_and_under"}
    assert [item["id"] for item in admissibility["choices"]].index(
        "equal_and_under"
    ) == 3
    assert "h*(P)=4" in admissibility["prompt"]
    assert "一致性" not in admissibility["prompt"]
    assert "algorithm_trace" not in admissibility["eligible_intents"]
    assert admissibility["concept_ids"] == ["admissibility_and_consistency"]
    assert "不检验一致性" in admissibility["teaching_support"]["explanation"]


def test_p2e_promoted_ids_exist_once_and_candidate_staging_is_isolated():
    candidates = _p2e_candidate_templates()
    production = _production_document()
    production_ids = {item["id"] for item in production["templates"]}
    selector = TemplateSelectionService(
        templates_data=production,
        valid_concept_ids=_concept_ids(),
    )

    selected_ids = {
        item["id"]
        for concept_id in _concept_ids()
        for intent in (
            "diagnostic_request", "definition", "explanation", "comparison",
            "algorithm_trace",
        )
        for item in selector.select(concept_ids=[concept_id], intent=intent)
    }
    assert candidates == {}
    assert P2E_CANDIDATE_TEMPLATE_IDS <= production_ids
    assert P2E_CANDIDATE_TEMPLATE_IDS <= selected_ids
    assert len(production_ids) == EXPECTED_PRODUCTION_TEMPLATE_COUNT


def test_p2f_promoted_batch_is_active_in_production_and_staging_is_empty():
    candidate = json.loads(P2F_CANDIDATE_PATH.read_text(encoding="utf-8"))
    production = _production_templates()
    assert candidate == {
        "schema_version": 1,
        "candidate_batch_id": "search_algorithms_p2f_a",
        "candidate_status": "promoted_to_production",
        "templates": [],
        "acceptance_cases": {},
    }
    assert P2F_PROMOTED_TEMPLATE_IDS <= set(production)
    assert len(production) == EXPECTED_PRODUCTION_TEMPLATE_COUNT
    assert all(production[item]["review_status"] == "human_verified" for item in P2F_PROMOTED_TEMPLATE_IDS)
