# Verification source-role inventory

- Production templates: 20
- Candidate templates: 0
- Blocked slots: 1

| Template | Bank | Primary concept | Source | Page | Context only | Topic match | Role | Strength | Result |
|---|---|---|---|---|---|---|---|---|---|
| verify_bfs_frontier_choice_v1 | production | breadth_first_search | lec2_bfs_layer_order | ai_lec2_uninformed_search.pdf:31-34 | False | True | evidence | production | pass |
| verify_bfs_equal_cost_condition_v1 | production | breadth_first_search | lec2_bfs_properties | ai_lec2_uninformed_search.pdf:35-35 | False | True | evidence | production | pass |
| verify_ucs_min_g_choice_v1 | production | uniform_cost_search | lec2_ucs_lowest_cost | ai_lec2_uninformed_search.pdf:60-62 | False | True | evidence | production | pass |
| verify_search_problem_components_v1 | production | search_problem_formulation | lec2_search_problem_components | ai_lec2_uninformed_search.pdf:6-10 | False | True | evidence | production | pass |
| verify_successor_operator_v1 | production | state_space_and_operators | lec2_eight_puzzle_formulation | ai_lec2_uninformed_search.pdf:12-12 | False | True | evidence | production | pass |
| verify_frontier_explored_membership_v1 | production | frontier_and_explored_set | lec2_frontier_expansion | ai_lec2_uninformed_search.pdf:20-20 | False | True | evidence | production | pass |
| verify_frontier_explored_membership_v1 | production | frontier_and_explored_set | lec2_graph_search_repeated_states | ai_lec2_uninformed_search.pdf:27-27 | False | True | evidence | production | pass |
| verify_graph_search_repeated_state_handling_v1 | production | tree_search_vs_graph_search | lec2_graph_search_repeated_states | ai_lec2_uninformed_search.pdf:27-27 | False | True | evidence | production | pass |
| verify_dfs_frontier_choice_v1 | production | depth_first_search | lec2_dfs_deepest_first | ai_lec2_uninformed_search.pdf:37-46 | False | True | evidence | production | pass |
| verify_dfs_frontier_choice_v1 | production | depth_first_search | support_stack_lifo | ds_stack_queue_priority_queue.pdf:1-2 | False | True | evidence | production | pass |
| verify_iddfs_depth_limit_schedule_v1 | production | iterative_deepening_search | lec2_iddfs_strategy | ai_lec2_uninformed_search.pdf:53-57 | False | True | evidence | production | pass |
| verify_informed_search_g_h_roles_v1 | production | informed_search_and_heuristics | lec3_a_star_f_g_h | ai_lec3_informed_search.pdf:18-18 | False | True | evidence | direct | pass |
| verify_greedy_min_h_choice_v1 | production | greedy_best_first_search | lec3_greedy_search | ai_lec3_informed_search.pdf:9-9 | False | True | evidence | direct | pass |
| verify_astar_min_f_choice_v1 | production | a_star_search | lec3_a_star_f_g_h | ai_lec3_informed_search.pdf:18-18 | False | True | evidence | direct | pass |
| verify_astar_min_f_choice_v1 | production | a_star_search | lec3_a_star_f_g_h | ai_lec3_informed_search.pdf:21-21 | False | True | evidence | direct | pass |
| verify_admissibility_no_overestimate_v1 | production | admissibility_and_consistency | lec3_admissibility | ai_lec3_informed_search.pdf:30-30 | False | True | evidence | direct | pass |
| verify_path_cost_accumulation_v1 | production | search_problem_formulation | lec2_solution_and_optimality | ai_lec2_uninformed_search.pdf:11-11 | False | True | evidence | supported_inference | pass |
| verify_path_cost_accumulation_v1 | production | search_problem_formulation | lec2_eight_puzzle_formulation | ai_lec2_uninformed_search.pdf:12-12 | False | True | evidence | supported_inference | pass |
| verify_search_node_state_distinction_v1 | production | tree_search_vs_graph_search | lec2_graph_search_repeated_states | ai_lec2_uninformed_search.pdf:27-27 | False | True | evidence | supported_inference | pass |
| verify_dfs_infinite_branch_risk_v1 | production | depth_first_search | lec2_dfs_deepest_first | ai_lec2_uninformed_search.pdf:37-46 | False | True | evidence | supported_inference | pass |
| verify_dfs_infinite_branch_risk_v1 | production | depth_first_search | lec2_dfs_properties | ai_lec2_uninformed_search.pdf:48-48 | False | True | evidence | supported_inference | pass |
| verify_search_algorithm_properties_v1 | production | completeness_optimality_complexity | lec2_iddfs_strategy | ai_lec2_uninformed_search.pdf:53-53 | True | False | context_only | supported_inference | pass |
| verify_search_algorithm_properties_v1 | production | completeness_optimality_complexity | lec2_iddfs_properties | ai_lec2_uninformed_search.pdf:58-58 | False | True | evidence | supported_inference | pass |
| verify_search_algorithm_properties_v1 | production | completeness_optimality_complexity | lec2_bfs_properties | ai_lec2_uninformed_search.pdf:35-35 | False | True | evidence | supported_inference | pass |
| verify_search_algorithm_properties_v1 | production | completeness_optimality_complexity | lec2_dfs_properties | ai_lec2_uninformed_search.pdf:48-48 | False | True | evidence | supported_inference | pass |
| verify_search_algorithm_properties_v1 | production | completeness_optimality_complexity | lec2_ucs_properties | ai_lec2_uninformed_search.pdf:63-63 | False | True | evidence | supported_inference | pass |
| verify_greedy_suboptimality_v1 | production | greedy_best_first_search | lec3_greedy_limitations | ai_lec3_informed_search.pdf:14-14 | False | True | evidence | direct | pass |
| verify_astar_f_value_v1 | production | a_star_search | lec3_a_star_f_g_h | ai_lec3_informed_search.pdf:18-18 | False | True | evidence | direct | pass |
| verify_consistency_edge_check_v1 | production | admissibility_and_consistency | lec3_consistency | ai_lec3_informed_search.pdf:39-39 | False | True | evidence | direct | pass |

## Statistics
- total_source_refs: 29
- production_source_refs: 29
- candidate_source_refs: 0
- context_only_refs: 1
- declared_primary_evidence_refs: 1
- non_context_evidence_refs: 28
- templates_with_zero_evidence_refs: 0
- templates_with_all_refs_context_only: 0
- topic_mismatches: 0
- invalid_pages: 0
- filename_mismatches: 0
- unknown_chunks: 0
- invalid_templates: 0
- duplicate_refs: 0
- evidence_strength_distribution: {'direct': 8, 'supported_inference': 10}
