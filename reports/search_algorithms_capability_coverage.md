# Search Algorithms verification capability coverage

A production template is narrow evidence, not a claim of complete concept mastery.

| Concept | Status | Production | Candidate | Blocked | Templates |
|---|---|---:|---:|---:|---|
| search_problem_formulation | production | 2 | 0 | 0 | verify_search_problem_components_v1, verify_path_cost_accumulation_v1 |
| state_space_and_operators | production | 1 | 0 | 0 | verify_successor_operator_v1 |
| tree_search_vs_graph_search | production | 2 | 0 | 0 | verify_graph_search_repeated_state_handling_v1, verify_search_node_state_distinction_v1 |
| frontier_and_explored_set | production | 1 | 0 | 0 | verify_frontier_explored_membership_v1 |
| breadth_first_search | production | 2 | 0 | 0 | verify_bfs_frontier_choice_v1, verify_bfs_equal_cost_condition_v1 |
| depth_first_search | production | 2 | 0 | 0 | verify_dfs_frontier_choice_v1, verify_dfs_infinite_branch_risk_v1 |
| completeness_optimality_complexity | production | 1 | 0 | 0 | verify_search_algorithm_properties_v1 |
| uniform_cost_search | production | 1 | 0 | 1 | verify_ucs_min_g_choice_v1 |
| informed_search_and_heuristics | production | 1 | 0 | 0 | verify_informed_search_g_h_roles_v1 |
| greedy_best_first_search | production | 2 | 0 | 0 | verify_greedy_min_h_choice_v1, verify_greedy_suboptimality_v1 |
| a_star_search | production | 2 | 0 | 0 | verify_astar_min_f_choice_v1, verify_astar_f_value_v1 |
| admissibility_and_consistency | production | 2 | 0 | 0 | verify_admissibility_no_overestimate_v1, verify_consistency_edge_check_v1 |
| local_search | none | 0 | 0 | 0 | — |
| hill_climbing | none | 0 | 0 | 0 | — |
| simulated_annealing | none | 0 | 0 | 0 | — |
| evolutionary_search | none | 0 | 0 | 0 | — |
| iterative_deepening_search | production | 1 | 0 | 0 | verify_iddfs_depth_limit_schedule_v1 |
| llm_search_and_test_time_scaling | none | 0 | 0 | 0 | — |
| adversarial_search | none | 0 | 0 | 0 | — |
| minimax_search | none | 0 | 0 | 0 | — |
| alpha_beta_pruning | none | 0 | 0 | 0 | — |
| game_state_evaluation | none | 0 | 0 | 0 | — |
| monte_carlo_search | none | 0 | 0 | 0 | — |
| exploration_exploitation | none | 0 | 0 | 0 | — |
| upper_confidence_bound | none | 0 | 0 | 0 | — |
| monte_carlo_tree_search | none | 0 | 0 | 0 | — |
