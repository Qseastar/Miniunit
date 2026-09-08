# P7 External Assessment Owner Review Sheet

> Status: research-only candidate material. Every item remains
> `pending_owner_review`. Independent review is not owner approval; none of
> these items may be registered as a production diagnostic, learner-state
> evidence, recommendation input, or student-visible assessment before a future
> separately approved study mode.

## Review instructions

For each candidate, the owner should inspect the cited authorized PDF page(s),
the corresponding production capability boundary, and the item itself. Record
one final decision only after human review: `APPROVE_FOR_HUMAN_PILOT`, `REVISE`,
or `REJECT`. The “recommended review focus” below is not a final owner decision.

| ID | Concept / production capability | External item and closed answer | Course source | Parallel-form / ambiguity audit | Tool recommendation | Owner decision |
| --- | --- | --- | --- | --- | --- | --- |
| `p7_ext_bfs_depth_claim_a` | `breadth_first_search`; production checks FIFO and equal-cost condition. | Unit-cost BFS first reaches G in 3 edges. **a**: minimum edges and, under unit cost, minimum total cost. | Lec2 `lec2_bfs_properties`, p.35 | Independent conditional conclusion; not a copied production stem/options. Check that unit-cost wording is unambiguous. Second-answer risk low. Difficulty comparable. | `RECOMMENDED`: review condition/conclusion wording and distractor b’s UCS distinction. | ______ |
| `p7_ext_bfs_queue_trace_b` | `breadth_first_search`; FIFO frontier behavior. | After P,Q entered, P expands and adds R,S; Q unexpanded. **a Q**. | Lec2 `lec2_bfs_layer_order`, pp.31–34 | Same family, two-operation FIFO trace rather than production’s one-step A/B/C instance. Second-answer risk low. | `RECOMMENDED`: confirm a parallel capability sample, not cosmetic relabeling. | ______ |
| `p7_ext_ucs_cost_accumulation_a` | `uniform_cost_search`; compare cumulative path cost. | X costs 2+4, Y costs 5, Z costs 1+7; select Y. **b**. | Lec2 `lec2_ucs_lowest_cost`, pp.60–62 | Complementary accumulated-cost distinction, not production frontier tuple. Check all numbers/choices yield one minimum. | `RECOMMENDED`: confirm no distractor can be read as an equal-cost tie. | ______ |
| `p7_ext_ucs_equal_depth_cost_b` | `uniform_cost_search`; cost can dominate equal depth. | Equal-depth M costs 9 and N costs 4; select N. **b**. | Lec2 `lec2_ucs_lowest_cost`, pp.60–62 | Independent contrast of equal edge count versus cumulative cost. Second-answer risk low because costs differ. | `RECOMMENDED`: confirm it measures UCS selection rather than merely arithmetic. | ______ |
| `p7_ext_astar_f_computation_a` | `a_star_search`; evaluate and minimize `f=g+h`. | R has g=3,h=4; S has g=5,h=1; select S. **c**. | Lec3 `lec3_a_star_f_g_h`, pp.18,21 | Independent calculation instance; same concept but not production stem/options. Check arithmetic and tie absence. | `RECOMMENDED`: confirm capability level is comparable, not stronger than production. | ______ |
| `p7_ext_astar_component_change_b` | `a_star_search`; distinguish g's contribution to f. | Equal h=3; T has g=2 and U has g=6; A* prefers T. **a**. | Lec3 `lec3_a_star_f_g_h`, pp.18,21 | Complementary role-of-components item, not a cosmetic calculation rewrite. Potential language ambiguity only; review labels. | `RECOMMENDED`: confirm it does not inadvertently test admissibility. | ______ |
| `p7_ext_local_search_neighbor_a` | `local_search`; state plus neighboring-state formulation. | Which representation fits local search? **a** current state plus neighboring states/evaluation. | Lec4 `lec4_local_search_state_neighbors`, pp.9–11 | Complementary representation construct. Ensure distractors are clearly outside local-search formulation. | `RECOMMENDED`: confirm one unique course-supported answer. | ______ |
| `p7_ext_local_search_representation_b` | `local_search`; local move changes current configuration. | Low-conflict board layout: retain the current layout while generating one-piece-move neighbors. **a**. | Lec4 `lec4_local_search_state_neighbors`, pp.9–11 | Independent applied scenario; not production wording. Potential overlap with generic optimization needs review. | `RECOMMENDED`: confirm it stays within local-search, not simulated annealing. | ______ |
| `p7_ext_minimax_min_node_a` | `minimax_search`; opponent/MIN node selects smaller utility. | MIN child values 6,2,5; return 2. **c**. | Lec5 `lec5_minimax_search`, pp.16–19 | Independent numerical MIN-node instance. Verify sign/value convention in the cited slides. | `RECOMMENDED`: confirm numerical direction and unique correct answer. | ______ |
| `p7_ext_minimax_two_level_b` | `minimax_search`; alternate MAX/MIN values. | MIN subtrees yield 3 and 4; root MAX chooses right. **b**. | Lec5 `lec5_minimax_search`, pp.16–19 | Complementary two-level evaluation, not a renamed production choice. Check cognitive load remains feasible. | `RECOMMENDED`: confirm no unstated tie-breaking is needed. | ______ |
| `p7_ext_mcts_backpropagation_a` | `monte_carlo_tree_search`; update tree statistics after simulation. | After rollout result, update previously selected tree nodes: backpropagation. **a**. | Lec6 `lec6_mcts_selection_simulation_backpropagation`, p.32 | Same course process but independent phrasing. Check option labels match course terminology. | `RECOMMENDED`: confirm not a mere verbatim definition recall. | ______ |
| `p7_ext_mcts_expand_untried_child_b` | `monte_carlo_tree_search`; add an untried child. | At an arrived node with an unadded legal action, add its child: expansion. **b**. | Lec6 `lec6_mcts_four_stages`, p.20; `lec6_mcts_selection_simulation_backpropagation`, p.32 | Complementary phase distinction. Second-answer risk low if “untried child” stays explicit. | `RECOMMENDED`: confirm selection/expansion boundary is clear. | ______ |

## Batch-level owner checks

- Verify all cited physical PDF pages directly; chunk references are locator
  metadata, not a substitute for page-level review.
- Confirm every item is source-grounded, has one defensible correct answer, and
  does not measure a materially different concept from its production capability.
- Confirm each external form is independent enough that remembering a production
  answer alone cannot trivially pass it.
- Decide whether immediate and delayed forms should be paired, swapped, or
  sampled as a balanced incomplete block; do not show an immediate item again as
  delayed assessment.
- Keep the full batch outside production even after approval. Owner approval
  enables a future research study mode, not automatic production promotion.
