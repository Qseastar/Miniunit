# Verification source traceability

- Production templates: 20
- Candidate templates: 0
- Blocked slots: 1

| Template | Bank | Concept | Sources | Source-role result |
|---|---|---|---|---|
| verify_bfs_frontier_choice_v1 | production | breadth_first_search | ai_lec2_uninformed_search.pdf:31-34 (lec2_bfs_layer_order; evidence) | pass |
| verify_bfs_equal_cost_condition_v1 | production | breadth_first_search | ai_lec2_uninformed_search.pdf:35-35 (lec2_bfs_properties; evidence) | pass |
| verify_ucs_min_g_choice_v1 | production | uniform_cost_search | ai_lec2_uninformed_search.pdf:60-62 (lec2_ucs_lowest_cost; evidence) | pass |
| verify_search_problem_components_v1 | production | search_problem_formulation | ai_lec2_uninformed_search.pdf:6-10 (lec2_search_problem_components; evidence) | pass |
| verify_successor_operator_v1 | production | state_space_and_operators | ai_lec2_uninformed_search.pdf:12-12 (lec2_eight_puzzle_formulation; evidence) | pass |
| verify_frontier_explored_membership_v1 | production | frontier_and_explored_set | ai_lec2_uninformed_search.pdf:20-20 (lec2_frontier_expansion; evidence); ai_lec2_uninformed_search.pdf:27-27 (lec2_graph_search_repeated_states; evidence) | pass |
| verify_graph_search_repeated_state_handling_v1 | production | tree_search_vs_graph_search | ai_lec2_uninformed_search.pdf:27-27 (lec2_graph_search_repeated_states; evidence) | pass |
| verify_dfs_frontier_choice_v1 | production | depth_first_search | ai_lec2_uninformed_search.pdf:37-46 (lec2_dfs_deepest_first; evidence); ds_stack_queue_priority_queue.pdf:1-2 (support_stack_lifo; evidence) | pass |
| verify_iddfs_depth_limit_schedule_v1 | production | iterative_deepening_search | ai_lec2_uninformed_search.pdf:53-57 (lec2_iddfs_strategy; evidence) | pass |
| verify_informed_search_g_h_roles_v1 | production | informed_search_and_heuristics | ai_lec3_informed_search.pdf:18-18 (lec3_a_star_f_g_h; evidence) | pass |
| verify_greedy_min_h_choice_v1 | production | greedy_best_first_search | ai_lec3_informed_search.pdf:9-9 (lec3_greedy_search; evidence) | pass |
| verify_astar_min_f_choice_v1 | production | a_star_search | ai_lec3_informed_search.pdf:18-18 (lec3_a_star_f_g_h; evidence); ai_lec3_informed_search.pdf:21-21 (lec3_a_star_f_g_h; evidence) | pass |
| verify_admissibility_no_overestimate_v1 | production | admissibility_and_consistency | ai_lec3_informed_search.pdf:30-30 (lec3_admissibility; evidence) | pass |
| verify_path_cost_accumulation_v1 | production | search_problem_formulation | ai_lec2_uninformed_search.pdf:11-11 (lec2_solution_and_optimality; evidence); ai_lec2_uninformed_search.pdf:12-12 (lec2_eight_puzzle_formulation; evidence) | pass |
| verify_search_node_state_distinction_v1 | production | tree_search_vs_graph_search | ai_lec2_uninformed_search.pdf:27-27 (lec2_graph_search_repeated_states; evidence) | pass |
| verify_dfs_infinite_branch_risk_v1 | production | depth_first_search | ai_lec2_uninformed_search.pdf:37-46 (lec2_dfs_deepest_first; evidence); ai_lec2_uninformed_search.pdf:48-48 (lec2_dfs_properties; evidence) | pass |
| verify_search_algorithm_properties_v1 | production | completeness_optimality_complexity | ai_lec2_uninformed_search.pdf:53-53 (lec2_iddfs_strategy; context_only); ai_lec2_uninformed_search.pdf:58-58 (lec2_iddfs_properties; evidence); ai_lec2_uninformed_search.pdf:35-35 (lec2_bfs_properties; evidence); ai_lec2_uninformed_search.pdf:48-48 (lec2_dfs_properties; evidence); ai_lec2_uninformed_search.pdf:63-63 (lec2_ucs_properties; evidence) | pass |
| verify_greedy_suboptimality_v1 | production | greedy_best_first_search | ai_lec3_informed_search.pdf:14-14 (lec3_greedy_limitations; evidence) | pass |
| verify_astar_f_value_v1 | production | a_star_search | ai_lec3_informed_search.pdf:18-18 (lec3_a_star_f_g_h; evidence) | pass |
| verify_consistency_edge_check_v1 | production | admissibility_and_consistency | ai_lec3_informed_search.pdf:39-39 (lec3_consistency; evidence) | pass |
