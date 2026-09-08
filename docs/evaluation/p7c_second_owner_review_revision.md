# P7c Second-Owner-Review-Directed External Assessment Revision

> 本文记录第二轮 human owner review 后的窄范围 instrument revision。它是 research-only
> audit material，不是 production diagnostic、human-study launch 或 readiness promotion。
> 当前 P7 仍为 **LEVEL 1 — synthetic pipeline validated**。外部作答至多解释为
> *independent course-grounded performance criterion*，不是 true mastery、ground-truth
> knowledge、calibrated probability 或 production learner-state evidence。

## Second-owner decisions recorded

| Item | Second owner decision | P7c action |
| --- | --- | --- |
| `p7_ext_bfs_depth_claim_a` | `OWNER_APPROVE` | Frozen; no substantive change |
| `p7_ext_local_search_neighbor_a` | `OWNER_APPROVE` | Frozen; no substantive change |
| `p7_ext_local_search_representation_b` | `OWNER_REVISE` | Revised below; pending third owner review |
| `p7_ext_mcts_backpropagation_a` | `OWNER_APPROVE` | Frozen; no substantive change |
| `p7_ext_ucs_depth_cost_tradeoff_c` | `OWNER_REJECT` | Removed from active pool; retained as rejection history |
| `p7_ext_astar_zero_heuristic_c` | `OWNER_APPROVE` | Frozen; no substantive change |

The six P7a/P7b preserve-direction items also remain unchanged. No owner-approved item is
promoted to production or treated as human-study approval.

## Frozen approved-item audit

P7c records canonical JSON hashes for the four second-review-approved changed items. Their
stem, choice IDs/text, expected answer, source refs, capability slice and substantive metadata
were not changed:

| Item | SHA-256 canonical representation |
| --- | --- |
| `p7_ext_bfs_depth_claim_a` | `802dc213cd9a13bd2d624bd57b723f94acc0c891cd4d1aae5e8cc9997fd1b231` |
| `p7_ext_local_search_neighbor_a` | `2243b54a80e834ad19675fc4f608db5981c2c7dc8b790b946905ef7009f96092` |
| `p7_ext_mcts_backpropagation_a` | `67583fdf6b125d0d331a54f2724478e7b53f3b0b8c8bba6f3470c83b7f8ae1c5` |
| `p7_ext_astar_zero_heuristic_c` | `3322f375f4f4c82dfb295969f686aa23d62649fcd6fb1b8d7348f57e6e5695bd` |

The existing P7b hash test continues to freeze the six preserve-direction items.

## Local Search representation revision

**Original ID / current ID:** `p7_ext_local_search_representation_b`  
**Concept / change type:** `local_search` / `REVISION`  
**Human owner instruction:** The P7b item and `p7_ext_local_search_neighbor_a` could both be
answered through the shortcut “current candidate/neighbors, not path/frontier.” The representation
item required a genuinely different answer pathway.

### Retired active formulation

The P7b version asked what the “core focus object” was for a low-conflict board, with the correct
choice “a current candidate layout and comparable neighbors.” Its alternatives were complete path,
global frontier and exhaustive-state representations. This is removed from the active wording,
but retained here as the audit history.

### New exact item

**Stem:**

> 按照 Lec4 对局部搜索的总体介绍，下列哪项任务结果最适合采用“只关心最终返回状态是否达到目标，而不关心完整路径”的搜索视角？

| Choice | Text |
| --- | --- |
| A | 给出一个满足 N 皇后约束的最终棋盘布局，不要求从初始布局到它的完整移动序列。 |
| B | 给出机器人从起点到终点必须逐步执行的完整动作序列。 |
| C | 给出从起点到每个候选状态的完整路线，供后续逐条比较。 |
| D | 给出对所有可达状态的完整枚举，以证明没有遗漏任何状态。 |

**Expected answer:** A.  
**Course source / physical pages:** Lec4 pp.9–11.  
**Source basis / strength:** `STRONG`. The course states that, for many problems, only the final
returned state reaching the goal matters rather than the path; it presents N-Queens and explains
local search as evaluating nearby solutions.

**Capability slice:** determine whether a task's required output supports a final-state-focused
Local Search framing.  
**Production comparison:** `COMPLEMENTARY_CAPABILITY` to
`verify_local_search_final_state_focus_v1`: production asks a direct definition question; this
item requires applying the final-output criterion to a task requirement.  
**External sibling comparison:** `COMPLEMENTARY_CAPABILITY` to
`p7_ext_local_search_neighbor_a`: neighbor item is solved from an explicitly described dynamic
process (current schedule, one-move neighbors, quality comparison). This item supplies no
candidate, neighborhood, frontier or update operation; it is solved by deciding whether the
requested deliverable is a final configuration or an action/path/coverage deliverable.

**Special shortcut test:** A learner knowing only “Local Search uses a current candidate and its
neighbors unlike path/frontier search” can answer the neighbor item, but cannot derive the new
item's final-output criterion from its wording alone: neither `candidate` nor `neighborhood`
appears. The item therefore passes the required distinct-pathway test.

**Memorization leakage:** `MEDIUM`; the course's N-Queens example is intentionally recognizable,
but the scored inference concerns output requirements rather than a memorized neighbor rule.  
**Second reasonable answer audit:** only A specifies a goal-satisfying final state while explicitly
not requiring a path. B/C require path output; D requires exhaustive coverage.  
**Guessing-cue audit:** choices are parallel task-output descriptions; the correct answer is not
the only technical term, number, non-absolute statement or grammatical form.  
**Correct answer supports:** this task's fit with the course's final-state Local Search framing.  
**Correct answer does NOT support:** a claim that all local-search implementations store one
state, any Hill Climbing/SA acceptance rule, tabu/history/population restrictions, global
optimality or convergence.

**Skeptical challenge:** N-Queens is the lecture example and may make the item easier; however,
the source directly uses it to motivate final-state search, and the capability pathway is distinct
from neighbor-operation recognition.  
**Terra recommendation:** `OWNER_APPROVE_RECOMMENDED`; item remains
`human_review_status=pending_owner_review` pending third owner review.

## UCS rejection and replacement

### Rejection history

**Rejected active P7b ID:** `p7_ext_ucs_depth_cost_tradeoff_c`.  
**Owner rejection:** although it introduced depth/cost conflict, the decisive procedure remained
“read the already supplied cumulative costs 8 and 6, then choose the smaller.” This is still the
production min-g selection pathway. It is no longer active and is retained only in this history.

### New exact replacement

**New ID:** `p7_ext_ucs_positive_cost_bound_d`  
**Concept / change type:** `uniform_cost_search` / `REPLACEMENT`

**Stem:**

> 课件在分析一致代价搜索（UCS）的完备性时，对每一步行动代价作了哪项假设？

| Choice | Text |
| --- | --- |
| A | 存在 ε>0，使每一步行动代价都至少为 ε。 |
| B | 所有行动代价都必须相同。 |
| C | 每一步行动代价只需非负，允许为 0。 |
| D | 搜索图中不能存在环。 |

**Expected answer:** A.  
**Course source / physical page:** Lec2 p.63.  
**Source basis / strength:** `STRONG`. The UCS performance slide explicitly lists completeness
under the condition that each step cost is at least ε with ε>0.

**Capability slice:** identify the positive lower-bound assumption used in the course's UCS
completeness analysis.  
**Production comparison:** `COMPLEMENTARY_CAPABILITY` to
`verify_ucs_min_g_choice_v1` and `verify_search_algorithm_properties_v1`. Production UCS evidence
tests min-g expansion; the generic property question's correct answer is about IDDFS, not the UCS
positive-bound premise. This replacement contains no g values, frontier comparison or arithmetic.  
**External sibling comparison:** `COMPLEMENTARY_CAPABILITY` to
`p7_ext_ucs_cost_accumulation_a`. Sibling procedure: add segment costs and compare totals. New
procedure: distinguish a strictly positive per-step lower bound from equality, non-negativity, and
acyclicity. It cannot be solved by that sibling's arithmetic.

**UCS special test:** the item cannot be solved by “look at given cumulative costs and select the
smallest,” because it supplies no path costs or frontier nodes. It also cannot be solved by merely
reproducing cost accumulation.  
**Memorization leakage:** `LOW–MEDIUM`; this is a direct course property statement, but it is a
different capability family from production and sibling decision procedures.  
**Second reasonable answer audit:** A alone preserves ε>0. B is an equal-cost condition for BFS/
IDDFS optimality; C permits zero and does not provide the stated positive lower bound; D is not
the course's UCS completeness assumption.  
**Guessing-cue audit:** all choices state a concrete search condition; no h(n), g(n), numerical
frontier ranking or deliberately absurd distractor is used.  
**Correct answer supports:** the stated UCS completeness premise only.  
**Correct answer does NOT support:** UCS min-g skill, cost accumulation, full completeness/
optimality proof, frontier replacement/decrease-key, or A*.

**Skeptical challenge:** this is a declarative performance-condition item and may be easier than
an operational trace. It is nevertheless a directly sourced, closed construct that is independent
of both existing UCS answer pathways. Owner review should decide if its difficulty fits the
research instrument.  
**Terra recommendation:** `OWNER_APPROVE_RECOMMENDED`; replacement remains
`human_review_status=pending_owner_review` pending third owner review.

## P7c candidate state and study-design boundary

The active research-only bank remains 12 closed deterministic items, all at
`assessment_status=pending_owner_review`. P7c does not force strict immediate/delayed parallel
pairs, select a feasibility subset, create a study, or resolve concept-bundle design. The Minimax
two-level item remains `TRANSFER_EXPLORATORY_ONLY` by the existing P7b decision.

No P7/P7c external item is in the production selector, `diagnostic_templates.json`, learner state,
formal evidence, exposure, recommendation, or ordinary student UI. The synthetic runner's S2
references the new UCS replacement only; its synthetic-only and privacy boundaries are unchanged.

## Readiness and remaining owner action

P7 remains **LEVEL 1 — synthetic pipeline validated**. The two P7c active changes require a
third human owner review. This file records Terra recommendations, not owner approval. No
human-participant work is authorized or started.
