# P5b：Search Algorithms reviewed diagnostic coverage expansion

状态（历史基线）：`candidate-only`，等待负责人内容审核与批准。本文前半部分记录离线
coverage audit、课程证据和工程验收；最终负责人批准与晋级结果见文末，不覆盖历史审计记录。

## Baseline

- knowledge-point registry：26 个 concept。
- production reviewed templates：20 个，未修改。
- P5b active candidate batch：8 个，均为 `candidate_draft`。
- existing blocked slot：`verify_ucs_frontier_update_v1`，原因仍是缺少课程对 lower-cost frontier replacement 的直接证据。
- SQLite schema、evidence gate、repeat/practice-only policy、mastery formula、recommendation 和 P5B 均未修改。
- 候选只复用 `single_choice_v1`；没有 LLM 评分，也没有运行时答案随机化。

P5b 直接回应内测对“正式诊断覆盖不足”的反馈；它增加可审核的 evidence opportunity，不声称已经证明 mastery 测量更准确。

## 26-concept coverage matrix

这里的 direct formal count 只统计该 concept 作为 production template 的明确 primary concept。多概念 BFS 等步代价题的第二个 concept 是已审核的同等 mastery target，不把 supporting appearance 当作覆盖。

| Concept | Production primary | Supporting-only | Scorers | Source chunks | Risk | P5b 状态 |
|---|---:|---:|---|---:|---|---|
| `search_problem_formulation` | 2 | 0 | single | 4 | GOOD | — |
| `state_space_and_operators` | 1 | 0 | single | 3 | THIN | — |
| `tree_search_vs_graph_search` | 2 | 0 | single | 8 | GOOD | — |
| `frontier_and_explored_set` | 1 | 0 | multiple | 4 | THIN | — |
| `breadth_first_search` | 2 | 0 | single | 9 | GOOD | — |
| `depth_first_search` | 2 | 0 | single | 10 | GOOD | — |
| `completeness_optimality_complexity` | 1 | 0 | single | 9 | THIN | — |
| `uniform_cost_search` | 1 | 0 | single | 11 | THIN / blocked capability | frontier-update blocked |
| `informed_search_and_heuristics` | 1 | 0 | multiple | 9 | THIN | — |
| `greedy_best_first_search` | 2 | 0 | single | 2 | GOOD | — |
| `a_star_search` | 2 | 0 | single | 13 | GOOD | — |
| `admissibility_and_consistency` | 2 | 0 | single | 5 | GOOD | — |
| `local_search` | 0 | 0 | — | 3 | MISSING | candidate |
| `hill_climbing` | 0 | 0 | — | 3 | MISSING | candidate |
| `simulated_annealing` | 0 | 0 | — | 1 | MISSING | candidate |
| `evolutionary_search` | 0 | 0 | — | 4 | MISSING | candidate |
| `iterative_deepening_search` | 1 | 0 | single | 2 | THIN | — |
| `llm_search_and_test_time_scaling` | 0 | 0 | — | 4 | MISSING | no candidate: needs a narrower reviewed claim |
| `adversarial_search` | 0 | 0 | — | 7 | MISSING | no candidate: broad framing, not a closed ability slice |
| `minimax_search` | 0 | 0 | — | 3 | MISSING | candidate |
| `alpha_beta_pruning` | 0 | 0 | — | 3 | MISSING | candidate |
| `game_state_evaluation` | 0 | 0 | — | 3 | MISSING | no candidate: evaluation design is too open-ended |
| `monte_carlo_search` | 0 | 0 | — | 4 | MISSING | no candidate: keep separate from MCTS stage evidence |
| `exploration_and_exploitation` | 0 | 0 | — | 2 | MISSING | no candidate: UCB candidate is narrower |
| `upper_confidence_bound` | 0 | 0 | — | 2 | MISSING | candidate |
| `monte_carlo_tree_search` | 0 | 0 | — | 6 | MISSING | candidate |

## Highest-priority gaps

The eight selected gaps have direct, finite claims in the current course subset and can be scored by the existing single-choice scorer. The remaining missing concepts are intentionally not forced into this batch: broad adversarial framing, evaluation-function design, LLM search, Monte-Carlo estimation, and exploration/exploitation require a tighter reviewed boundary or a separate content review.

## Candidate batch

File: `data/candidate_templates/search_algorithms_p5b_candidates.json`

All entries have `review_status="candidate_draft"`, `purpose="mastery_verification"`, one primary concept, deterministic `single_choice_v1`, fixed choice order, and `candidate_status="pending_human_review"`. The candidate loader and source-role gate pass offline. The candidate file is not read by the production selector.

| Template | Primary concept | Difficulty | Evidence closure | Source |
|---|---|---|---|---|
| `verify_local_search_final_state_focus_v1` | `local_search` | basic | DIRECT | `ai_lec4_local_search_and_llm_search.pdf` pp.9–11, `lec4_local_search_state_neighbors` |
| `verify_hill_climbing_stop_at_local_best_v1` | `hill_climbing` | basic | DIRECT | Lec4 pp.12–16, `lec4_hill_climbing` |
| `verify_simulated_annealing_worse_successor_v1` | `simulated_annealing` | basic | DIRECT | Lec4 pp.17–19, `lec4_simulated_annealing` |
| `verify_evolutionary_search_parent_cycle_v1` | `evolutionary_search` | basic | DIRECT | Lec4 pp.20–25, `lec4_evolutionary_search_cycle` |
| `verify_minimax_max_min_value_choice_v1` | `minimax_search` | closed instance | DIRECT_PLUS_CLOSED_INSTANCE | Lec5 pp.16–19, `lec5_minimax_search` |
| `verify_alpha_beta_prune_when_bounds_cross_v1` | `alpha_beta_pruning` | closed instance | DIRECT_PLUS_CLOSED_INSTANCE | Lec5 pp.20–31, `lec5_alpha_beta_pruning` |
| `verify_mcts_four_stage_order_v1` | `monte_carlo_tree_search` | basic | DIRECT | Lec6 p.20, `lec6_mcts_four_stages` |
| `verify_ucb_upper_bound_selection_v1` | `upper_confidence_bound` | basic | DIRECT | Lec6 p.19, `lec6_upper_confidence_bound` |

### Per-candidate evidence and capability audit

1. **Local search final-state focus** — p.11 directly contrasts final-state focus with complete paths. It can update only `local_search` for this distinction; it cannot establish optimality, convergence, or a particular neighborhood policy. It is novel relative to all 20 production templates.
2. **Hill climbing stopping condition** — p.12 gives the basic repeat/stop rule; pp.13–16 are context for variants and limitations. It measures the stopping condition, not global optimality. It is novel.
3. **Simulated annealing worse-successor rule** — p.19 directly states probabilistic acceptance and temperature-dependent randomness. It does not measure a numerical schedule or convergence. It is novel.
4. **Evolutionary parent cycle** — pp.20–25 directly show fitness-weighted selection, crossover, and mutation. It does not prove convergence or best-solution guarantees. It is novel.
5. **Minimax MAX choice** — pp.16–19 give the MAX/MIN recurrence; values 3 and 5 are a closed mechanical instance. It measures one MAX choice only, not a full game-tree strategy. It is novel.
6. **Alpha-Beta crossed bounds** — pp.20–31 give the bound updates, `alpha > beta` pruning condition, and pseudocode; `alpha=5,beta=4` is a closed instance. It does not measure move ordering or full minimax correctness. It is novel.
7. **MCTS four-stage order** — p.20 directly lists selection, expansion, simulation, backpropagation. It does not claim mastery of UCB values or adversarial statistics. It is novel.
8. **UCB upper-bound choice** — p.19 directly defines `Q_k + δ(k)` and selecting the highest upper bound. It does not claim mastery of all exploration/exploitation policies or numerical confidence calibration. It is novel.

## Second-reasonable-answer audit

Each candidate was reviewed against the exact stem, declared assumptions, option wording, and course page. The answer is unique for all eight:

| Template | Second reasonable answer | Result |
|---|---|---|
| all eight candidates | none under the stated stem and closed values | no blocking ambiguity |

The two closed-instance questions explicitly name MAX and provide the bound values. The other questions ask for a single rule quoted or directly paraphrased from the cited pages; they do not ask for an unbounded strategy or an external textbook conclusion.

## Production-overlap audit

All eight are `NOVEL_DIRECT_EVIDENCE`: their primary concepts have no existing production template. No candidate changes an existing production question or scorer. The answer-position distribution is static and balanced within the batch (positions 1–4 each occur twice); runtime shuffle is not used.

## Independent second-pass verdicts

An independent second reading using the question-as-reviewer perspective found no second answer, source mismatch, unsupported capability claim, or scorer ambiguity:

| Candidate | Verdict |
|---|---|
| `verify_local_search_final_state_focus_v1` | APPROVE pending owner review |
| `verify_hill_climbing_stop_at_local_best_v1` | APPROVE pending owner review |
| `verify_simulated_annealing_worse_successor_v1` | APPROVE pending owner review |
| `verify_evolutionary_search_parent_cycle_v1` | APPROVE pending owner review |
| `verify_minimax_max_min_value_choice_v1` | APPROVE pending owner review |
| `verify_alpha_beta_prune_when_bounds_cross_v1` | APPROVE pending owner review |
| `verify_mcts_four_stage_order_v1` | APPROVE pending owner review |
| `verify_ucb_upper_bound_selection_v1` | APPROVE pending owner review |

“Independent review APPROVE” is not owner approval and does not promote a candidate.

## Promotion decisions

- Designed: 8.
- Independent second-pass APPROVE: 8.
- REVISE: 0.
- REJECT: 0.
- BLOCKED_BY_EVIDENCE in this batch: 0.
- Promoted: 0.
- Starting production: 20; current production: 20.
- Active P5b candidates: 8, pending owner content review.
- Existing blocked slot remains 1 (`verify_ucs_frontier_update_v1`).

Promotion requires owner approval, direct/direct-plus-closed-instance evidence, no second answer, deterministic scorer tests, and the existing evidence/repeat-policy regressions. This branch intentionally stops before that decision.

## Final coverage matrix (candidate-aware)

Production direct formal coverage remains 12 concepts; after a future approval, these eight candidates would add one direct slice each for `local_search`, `hill_climbing`, `simulated_annealing`, `evolutionary_search`, `minimax_search`, `alpha_beta_pruning`, `monte_carlo_tree_search`, and `upper_confidence_bound`. They do not yet count toward production mastery coverage.

The final production bank is unchanged at 20 IDs: `verify_bfs_frontier_choice_v1`, `verify_bfs_equal_cost_condition_v1`, `verify_ucs_min_g_choice_v1`, `verify_search_problem_components_v1`, `verify_successor_operator_v1`, `verify_frontier_explored_membership_v1`, `verify_graph_search_repeated_state_handling_v1`, `verify_dfs_frontier_choice_v1`, `verify_iddfs_depth_limit_schedule_v1`, `verify_informed_search_g_h_roles_v1`, `verify_greedy_min_h_choice_v1`, `verify_astar_min_f_choice_v1`, `verify_admissibility_no_overestimate_v1`, `verify_path_cost_accumulation_v1`, `verify_search_node_state_distinction_v1`, `verify_dfs_infinite_branch_risk_v1`, `verify_search_algorithm_properties_v1`, `verify_greedy_suboptimality_v1`, `verify_astar_f_value_v1`, and `verify_consistency_edge_check_v1`.

## Engineering and policy checks

- Candidate loader, source refs, physical pages, answer positions, positive/negative scoring, and malformed answers are covered by `tests/test_p5b_candidate_templates.py`.
- `tools/verification_quality_gate.py` now recognizes `direct_plus_closed_instance` as a candidate evidence-closure label; no production scorer or runtime policy changed.
- Production templates remain isolated: candidate drafts are rejected by the production template validator and are not selected by `TemplateSelectionService`.
- No new scorer, LLM call, network call, `.env` access, PDF binary, SQLite file, runtime log, or feedback artifact is introduced.

## Final owner approval and controlled promotion

负责人已完成对本批八道候选的最终内容批准；本节记录批准后的受控晋级结果，
不将 independent review APPROVE 与 owner approval 混为一谈。

- 八道模板均已获得 `OWNER_APPROVED`；其中
  `verify_local_search_final_state_focus_v1` 使用最终批准的题干与选项版本。
- 仅执行数据层晋级：八个 `candidate_draft` 模板复制到
  `data/diagnostic_templates.json` 并标记为 `human_verified`；selector、scorer、
  evidence gate、P5B、mastery、recommendation 与 repeat policy 未修改。
- 晋级后 production reviewed templates：28；active candidates：0；blocked slots：1；
  concepts：26；SQLite schema：3。
- staging 文件保持 `candidate_status="promoted_to_production"`，`templates=[]`、
  `acceptance_cases={}`，因此不会再被 production selector 读取。
- 八个晋级 ID：`verify_local_search_final_state_focus_v1`、
  `verify_hill_climbing_stop_at_local_best_v1`、
  `verify_simulated_annealing_worse_successor_v1`、
  `verify_evolutionary_search_parent_cycle_v1`、
  `verify_minimax_max_min_value_choice_v1`、
  `verify_alpha_beta_prune_when_bounds_cross_v1`、
  `verify_mcts_four_stage_order_v1`、
  `verify_ucb_upper_bound_selection_v1`。
- 从 `HEAD` 的实际 registry 重算，晋级前 primary concept coverage 为 13 / 26（此前计划材料中的 12 / 26 与当前仓库实际模板表不一致）；晋级后增至 21 / 26；这仍是窄能力证据覆盖，
  不等同于 21 个 concept 的完整掌握。既有 UCS lower-cost frontier-update slot 继续 blocked。
- 每道新题均通过 source/scorer/malformed/selector/verification-state acceptance tests；
  真实课程页码与 evidence strength 继续由 `tests/template_acceptance_cases.py` 锁定。

## Remaining blocked concepts and limitations

The UCS lower-cost frontier-update slot remains blocked by the existing evidence audit.
`adversarial_search`, `game_state_evaluation`, `monte_carlo_search`, `exploration_and_exploitation`,
and `llm_search_and_test_time_scaling` remain without production evidence; they need narrower
reviewed claims or additional human content review. The eight P5b candidates are no longer staged:
they were owner-approved and promoted as the production templates listed above.
