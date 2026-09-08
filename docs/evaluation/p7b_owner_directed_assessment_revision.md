# P7b Owner-Directed External Assessment Revision

> 文档性质：本文件记录负责人已给出的 6 / 4 / 2 处理方向，以及本轮对 6 道变更题的
> source、independence 与 ambiguity 审计。它不是新的负责人决定，也不表示可开展真人研究。
> 所有 active external candidate 仍为 `assessment_status=pending_owner_review` 与
> `human_review_status=pending_owner_review`。它们不进入 production、普通学生 UI、
> learner-state evidence、exposure 或 recommendation。

## Owner-directed input

负责人已确认以下处理方向，而非由 Terra 自行决定：

| Direction | Items |
| --- | --- |
| Preserve | `p7_ext_bfs_queue_trace_b`、`p7_ext_ucs_cost_accumulation_a`、`p7_ext_astar_component_change_b`、`p7_ext_minimax_min_node_a`、`p7_ext_minimax_two_level_b`、`p7_ext_mcts_expand_untried_child_b` |
| Revise | `p7_ext_bfs_depth_claim_a`、`p7_ext_local_search_neighbor_a`、`p7_ext_local_search_representation_b`、`p7_ext_mcts_backpropagation_a` |
| Reject and replace | `p7_ext_ucs_equal_depth_cost_b`、`p7_ext_astar_f_computation_a` |

`p7_ext_minimax_two_level_b` 的角色固定为 `TRANSFER_EXPLORATORY_ONLY`；本轮不把它
包装为 immediate/delayed 的严格平行题。

## Approved-six immutability audit

本轮对以下六题按 `stem`、choice ID/text、`expected_answer`、`capability_slice`、
`source_refs` 与 suggested role 进行语义冻结检查；candidate JSON 未改写其题干、选项、
答案、来源或 capability：

- `p7_ext_bfs_queue_trace_b`
- `p7_ext_ucs_cost_accumulation_a`
- `p7_ext_astar_component_change_b`
- `p7_ext_minimax_min_node_a`
- `p7_ext_minimax_two_level_b`（仅 transfer exploratory）
- `p7_ext_mcts_expand_untried_child_b`

它们仍须遵循候选 bank 的 `pending_owner_review` 状态；此处的 preserve 仅表示遵从
负责人已确认的方向，不是把它们升级为 human-verified 或 production item。

## Rejection history and replacements

| Original ID | Original problem summary | Owner rejection | Representation now | Replacement ID |
| --- | --- | --- | --- | --- |
| `p7_ext_ucs_equal_depth_cost_b` | 已给两个累计 `g`，选较小者 | `TOO_SIMILAR`：与 production min-g 选点同一解题路径，且更简单 | 从 active JSON 移除；历史保留在本文 | `p7_ext_ucs_depth_cost_tradeoff_c` |
| `p7_ext_astar_f_computation_a` | 计算两节点 `f=g+h` 后选最小 f | `TOO_SIMILAR`：production 已测计算及 min-f 选择 | 从 active JSON 移除；历史保留在本文 | `p7_ext_astar_zero_heuristic_c` |

新 ID 不复用被拒绝 ID，因而研究轨迹保持为：candidate → P7a adversarial audit →
owner rejection → P7b replacement。candidate JSON 只保留未来待审核的 active items；
它不承担 rejected-history workflow 的存档职责。

## Changed-item owner review packs

### Changed Item 1

**Original ID:** `p7_ext_bfs_depth_claim_a`
**Current ID:** `p7_ext_bfs_depth_claim_a`
**Concept / change type:** BFS / REVISION
**Suggested role:** `BUNDLE_COMPONENT_NOT_PARALLEL`

**Original problem:** 在所有边代价为 1 时，从首次到达深度直接推出最少边数和最低总代价。

**Owner instruction:** 保留 equal-step-cost 下的 fewest-step / lowest-total-cost capability family，
改为独立 application judgment；不能只重述 production 条件或利用最长正确选项猜测。

**New question:** 一个导航图中原本每一步代价都为 1，BFS 找到了一条经过 3 步的路径。后来其中一条边的代价改为 5，系统仍按 BFS 的层次顺序搜索。仅根据这些信息，下列哪项判断最恰当？

| Choice | Text |
| --- | --- |
| A | 仍以最少步数的路径为先，因此可保证总代价最低。 |
| B | 仍以最少步数的路径为先，但不能仅凭步数保证总代价最低。 |
| C | 会改以累计路径代价为先，因而不再按层搜索。 |
| D | 不再能按层比较路径，因为边代价已不相同。 |

**Correct answer:** B.
**Course source / physical pages:** Lec2 pp.31–34（BFS 分层扩展）及 p.35（最优性仅在所有行动代价相同）。
**Source basis / strength:** `STRONG`。两页共同支持“步数层次性质保留、总代价保证的等代价前提被破坏”。

**Why correct / distractors:** B 是唯一保留 BFS 的层次/最少步数性质且限制总代价外推的判断。A 忽略前提已被破坏；C 错把 UCS 的累计代价扩展规则赋给 BFS；D 错把代价变化当作层次比较失效。

**Production comparison:** 对 `verify_bfs_equal_cost_condition_v1` 是
`INDEPENDENT_CAPABILITY_SAMPLE`：production 选择“什么条件成立”，本题判断改变条件后哪些结论仍成立。
**External sibling comparison:** 与 FIFO queue trace 是不同 micro-capability；构成 BFS bundle，非平行 form。
**Memorization leakage:** `MEDIUM`，学生知道等代价边界会有帮助，但仍须做 counterfactual application。
**Second reasonable answer:** 无。题干明确只有一条边改变且仍使用 BFS，因而不是 UCS、无法比较步数或仍保证最低总代价。
**Guessing audit:** 四个选项均为具体搜索行为判断；正确项不再以唯一最长、唯一非绝对或唯一专业术语取胜。
**Correct answer supports:** 该给定情境下 BFS 的条件性结论边界。
**Correct answer does NOT support:** 任意边权最优性、UCS、完整 BFS optimality theorem。
**FIRST_PASS:** `OWNER_APPROVE_RECOMMENDED`。
**SECOND_PASS challenge:** 仍可能被背过“相同代价”结论的学生答对；但题目实际测的是前提撤销后的结论区分，未复用 production 的 answer pathway。
**FINAL TERRA RECOMMENDATION:** `OWNER_APPROVE_RECOMMENDED`，仍待 owner second review。

### Changed Item 2

**Original ID:** `p7_ext_local_search_neighbor_a`
**Current ID:** `p7_ext_local_search_neighbor_a`
**Concept / change type:** Local Search / REVISION
**Suggested role:** `BUNDLE_COMPONENT_NOT_PARALLEL`

**Original problem:** 通过排课邻居识别 local search，但错误项带有“必须/必然”等绝对提示。
**Owner instruction:** 保留 current-candidate / neighborhood / solution-quality framing；不等同 Hill Climbing 或对所有 implementation 作绝对主张。

**New question:** 按照 Lec4 对局部搜索的总体介绍，一个排课优化过程从当前候选课表出发，对只移动一门课得到的相邻课表比较冲突数。下列哪项最恰当地概括这个过程的搜索视角？

| Choice | Text |
| --- | --- |
| A | 围绕当前候选课表及其邻域比较解的质量，并据此选择后续候选。 |
| B | 围绕从初始课表到每个候选的完整动作路径比较路径质量。 |
| C | 围绕一个待扩展 frontier 的全局队列排列所有候选课表。 |
| D | 围绕全部已探索课表穷举候选后再比较整体质量。 |

**Correct answer:** A.
**Course source / physical pages:** Lec4 pp.9–11。
**Source basis / strength:** `STRONG`：课件直接说明只关心最终状态、评价当前状态邻域近邻解并移动以获得更好解。

**Why correct / distractors:** A 复述的是候选解—邻域—质量的上位 framing。B 是完整路径取向，C 是系统 frontier 取向，D 是穷举 explored-state 取向；三者是相邻 search-family misconceptions，而非荒谬答案。

**Production comparison:** 对 `verify_local_search_final_state_focus_v1` 是
`INDEPENDENT_CAPABILITY_SAMPLE`，新题要求从排课邻域应用识别 framing。
**External sibling comparison:** 与 representation item 是 `COMPLEMENTARY_CAPABILITY`：本题测动态邻域评估，另一题测不关心完整路径时的核心表示。
**Memorization leakage:** `MEDIUM`。
**Second reasonable answer:** 无。题干明确限定“按照 Lec4 的总体介绍”，没有要求某一具体 local-search variant 的接受规则。
**Guessing audit:** 四项均以“围绕…比较/排列”写成平行描述；正确项不是唯一不绝对的选项。
**Correct answer supports:** upper-level candidate/neighborhood quality framing。
**Correct answer does NOT support:** Hill Climbing 必然只移向更优邻居、SA 接受规则、全局最优或所有实现的内存声明。
**FIRST_PASS:** `OWNER_APPROVE_RECOMMENDED`。
**SECOND_PASS challenge:** 现实系统可额外维护路径或缓存；题干没有声称不能这么做，只问课件 framing 的最恰当概括。
**FINAL TERRA RECOMMENDATION:** `OWNER_APPROVE_RECOMMENDED`，仍待 owner second review。

### Changed Item 3

**Original ID:** `p7_ext_local_search_representation_b`
**Current ID:** `p7_ext_local_search_representation_b`
**Concept / change type:** Local Search / REVISION
**Suggested role:** `BUNDLE_COMPONENT_NOT_PARALLEL`

**Original problem:** “最需要保留”容易被读成所有实现只能保存一个当前状态。
**Owner instruction:** 限定 Lec4 的总体 conceptual framing，测 candidate-state/neighborhood focus 与 path/frontier systematic search 的区分。

**New question:** 按照 Lec4 对局部搜索的总体介绍，若目标是找到低冲突棋盘布局而不关心从初始布局到该布局的完整路径，下列哪项最贴近该过程的核心关注对象？

| Choice | Text |
| --- | --- |
| A | 一个当前候选布局及其邻域中可比较的近邻布局。 |
| B | 从初始布局到当前布局的完整动作序列。 |
| C | 按累计路径代价排序、等待逐一扩展的全局 frontier。 |
| D | 为覆盖所有状态而维护的全部可达布局集合。 |

**Correct answer:** A.
**Course source / physical pages:** Lec4 pp.9–11.
**Source basis / strength:** `STRONG`。

**Why correct / distractors:** A 反映课件的当前状态与近邻解关注；B/C/D 分别是完整路径、UCS-style frontier 与 exhaustive state-space framing。题干不声称这些信息永远不能作为实现的附加状态。

**Production comparison:** `COMPLEMENTARY_CAPABILITY`：production 定义性区分总体对象，本题在明确“不关心完整路径”的棋盘情境中检验 representation/focus。
**External sibling comparison:** 与 neighbor item 互补，不是同一个 question rewrite。
**Memorization leakage:** `MEDIUM`。
**Second reasonable answer:** 无；“核心关注对象”在题干限定的 Lec4 framing 内不等于“唯一可保存的对象”。
**Guessing audit:** 选项均为可理解的搜索表示，避免“最需要保留”和唯一非绝对答案。
**Correct answer supports:** candidate-solution / neighborhood focus。
**Correct answer does NOT support:** 所有 local-search variant 只存一个 state、tabu list、temperature、population、全局最优或终止条件。
**FIRST_PASS:** `OWNER_APPROVE_RECOMMENDED`。
**SECOND_PASS challenge:** candidate/neighborhood 也可能搭配额外历史；经题干语义限制后，这不构成第二正确答案。
**FINAL TERRA RECOMMENDATION:** `OWNER_APPROVE_RECOMMENDED`，仍待 owner second review。

### Changed Item 4

**Original ID:** `p7_ext_mcts_backpropagation_a`
**Current ID:** `p7_ext_mcts_backpropagation_a`
**Concept / change type:** MCTS / REVISION (source correction only)
**Suggested role:** `BUNDLE_COMPONENT_NOT_PARALLEL`

**Original problem:** 模拟结束后如何让访问路径节点利用结果；题干和答案语义不变。
**Owner instruction:** 不扩大能力，只用直接支持回传/更新作用的来源页。

**New question:** 一次 MCTS 模拟已经结束，并得到本次 rollout 的结果。接下来系统应执行什么操作，才能让之前选择过的树节点利用这次结果？

| Choice | Text |
| --- | --- |
| A | 沿本次访问路径回传并更新节点统计。 |
| B | 从根开始重新随机模拟，且不更新任何节点。 |
| C | 删除所有未访问子节点。 |
| D | 只按最小 g(n) 选择下一节点。 |

**Correct answer:** A.
**Course source / physical page:** Lec6 p.20（替换原 p.32 图示引用）。
**Source basis / strength:** `STRONG`：p.20 明文说明回溯基于模拟结果，自底向上更新路径节点的奖励均值与被访问次数。

**Why correct / distractors:** A 是课件定义的 backpropagation；B 取消统计更新，C 无来源支持，D 混入 UCS。
**Production comparison:** `COMPLEMENTARY_CAPABILITY`，production 测四阶段完整顺序，本题测单一阶段的 operational role。
**External sibling comparison:** 与 expansion item 是不同阶段功能；能组成 MCTS concept bundle，不是 strict parallel。
**Memorization leakage:** `MEDIUM`。
**Second reasonable answer:** 无。题干已在 rollout 结束后询问如何利用结果。
**Guessing audit:** 所有选项都是具体后续操作；A 不依赖唯一术语或唯一长度。
**Correct answer supports:** 回传将模拟结果写入访问路径统计。
**Correct answer does NOT support:** UCB 公式、统计分子/分母的普遍解释、四阶段顺序 mastery。
**FIRST_PASS:** `OWNER_APPROVE_RECOMMENDED`。
**SECOND_PASS challenge:** p.20 中某些统计细节依游戏结果而异；题目只声称“更新节点统计”，不外推具体胜负计数规则。
**FINAL TERRA RECOMMENDATION:** `OWNER_APPROVE_RECOMMENDED`，仍待 owner second review。

### Changed Item 5

**Original ID:** `p7_ext_ucs_equal_depth_cost_b`
**Current / replacement ID:** `p7_ext_ucs_depth_cost_tradeoff_c`
**Concept / change type:** UCS / REPLACEMENT

**Original problem:** 两条相同深度、已给 g 的路径中选最小 g。
**Owner instruction:** 原题 `TOO_SIMILAR`；新题不能仍是“已给 g → 选最小”，不能复制 cost-accumulation sibling，也不得触及 lower-cost frontier replacement/decrease-key。

**New question:** UCS 的 frontier 中有两条路径：P 经过 2 步、累计代价为 8；Q 经过 4 步、累计代价为 6。若现在只能扩展一条路径，哪项判断符合课件中的一致代价搜索原则？

| Choice | Text |
| --- | --- |
| A | 扩展 P，因为它经过的步数更少。 |
| B | 扩展 Q，因为它的累计路径代价更小，即使经过的步数更多。 |
| C | 扩展 P，因为 UCS 会优先保留较浅层的路径。 |
| D | 无法判断，必须先知道每条路径到目标的启发式估计。 |

**Correct answer:** B.
**Course source / physical pages:** Lec2 pp.60–62。
**Source basis / strength:** `STRONG`：课件明示 UCS 扩展路径消耗最小的节点，并在代价敏感搜索图中区分边数与累计代价。

**Why correct / distractors:** B 是唯一应用累计路径代价规则的结论；A/C 引入 BFS 的深度直觉；D 错将 A* 的 heuristic 加为 UCS 条件。
**Production comparison:** `COMPLEMENTARY_CAPABILITY`。production 是三个已给 g 值的排序；本题需在较浅但更贵与较深但更便宜的取舍中拒绝 depth criterion。
**External sibling comparison:** 对 `p7_ext_ucs_cost_accumulation_a` 是 `COMPLEMENTARY_CAPABILITY`：sibling 先做代价相加，本题不给分段算式而检验 depth-vs-cost conflict。
**Memorization leakage:** `MEDIUM`。
**Second reasonable answer:** 无；无 tie、无 replacement/decrease-key、也不需要 h。
**Guessing audit:** 四项均以扩展判断呈现；正确项不是“唯一专业术语”或唯一数值项。
**Correct answer supports:** 该 frontier 里的累计 cost 优先于步数。
**Correct answer does NOT support:** UCS 的完整性/最优性证明、frontier replacement、decrease-key 或 A*。
**FIRST_PASS:** `OWNER_APPROVE_RECOMMENDED`。
**SECOND_PASS challenge:** 仍包含“选哪个 frontier 节点”，可能被认为接近 production；但解题路径从 min-g list 转为 depth-cost conflict，且不含 cost accumulation，故不属 cosmetic rewrite。
**FINAL TERRA RECOMMENDATION:** `OWNER_APPROVE_RECOMMENDED`，仍待 owner second review。

### Changed Item 6

**Original ID:** `p7_ext_astar_f_computation_a`
**Current / replacement ID:** `p7_ext_astar_zero_heuristic_c`
**Concept / change type:** A* / REPLACEMENT

**Original problem:** 计算两个 `f=g+h` 后选较小 f。
**Owner instruction:** 原题 `TOO_SIMILAR`；禁止再做 f 计算、数值替换或与 component-change sibling 重叠。若找不到独立课程直接证据，应标 blocked。

**New question:** 按照课件对启发式函数两个极端的讨论，若 A* 对每个节点都使用 h(n)=0，它的选择行为与哪种搜索策略相同？

| Choice | Text |
| --- | --- |
| A | 一致代价搜索，因为此时 f(n) 只由累计路径代价 g(n) 决定。 |
| B | 贪婪搜索，因为此时只依据 h(n) 估计选择节点。 |
| C | 宽度优先搜索，因为 h(n) 对所有节点都相同。 |
| D | 深度优先搜索，因为不再使用启发式函数。 |

**Correct answer:** A.
**Course source / physical page:** Lec3 p.57。
**Source basis / strength:** `STRONG`：课件直接写明 `h(n)=0` 的第一种极端“等价于一致代价搜索”。

**Why correct / distractors:** A 准确陈述课件极端；B 把零启发式误作贪婪只看 h，C 把相同 h 误作按层，D 把无启发式误作 DFS。
**Production comparison:** `COMPLEMENTARY_CAPABILITY`：production 测 f 计算与 min-f；replacement 测 heuristic-extreme consequence，不计算 f 或选择 frontier node。
**External sibling comparison:** 对 `p7_ext_astar_component_change_b` 是 `COMPLEMENTARY_CAPABILITY`：sibling 固定 h 观察 g 的作用，replacement 取 h=0 并考察与 UCS 的课程明确关系。
**Memorization leakage:** `LOW–MEDIUM`。
**Second reasonable answer:** 无；课件明确给出该等价关系，题干不要求关于 A* 最优性的任何判断。
**Guessing audit:** 四个皆为已学搜索策略并带平行理由；正确项不依赖唯一公式计算、唯一数字或唯一不绝对表达。
**Correct answer supports:** `h=0` 这一课程明确极端下 A* 与 UCS 的行为关系。
**Correct answer does NOT support:** admissibility、consistency、A* 完整最优性或一般 heuristic quality。
**FIRST_PASS:** `OWNER_APPROVE_RECOMMENDED`。
**SECOND_PASS challenge:** 题目较短，可能偏易；但其 capability 不与 production f-computation 重叠，且 course source 是直接文本。是否接受其难度应由第二轮 owner review 决定。
**FINAL TERRA RECOMMENDATION:** `OWNER_APPROVE_RECOMMENDED`，仍待 owner second review。

## Source-evidence audit

| Changed item | Physical source | Strength | Result |
| --- | --- | --- | --- |
| BFS revision | Lec2 pp.31–35 | STRONG | 分层与等行动代价条件共同成立 |
| Local neighbor revision | Lec4 pp.9–11 | STRONG | 当前状态、邻域、近邻质量直接支持 |
| Local representation revision | Lec4 pp.9–11 | STRONG | final-state focus 与不关心完整路径直接支持 |
| MCTS source revision | Lec6 p.20 | STRONG | 直接文字说明回传更新统计 |
| UCS replacement | Lec2 pp.60–62 | STRONG | 直接说明扩展路径消耗最小的节点 |
| A* replacement | Lec3 p.57 | STRONG | 直接说明 `h(n)=0` 等价 UCS |

每个 `source_refs` 均只引用当前 course chunk 覆盖的真实 1-based physical pages；未使用网络、教材或未授权材料。

## Production and cross-external independence audit

| Changed item | Production overlap | Sibling overlap | Circularity / similarity result |
| --- | --- | --- | --- |
| BFS depth revision | INDEPENDENT_CAPABILITY_SAMPLE | FIFO trace: different micro-capability | no `TOO_SIMILAR` / no `CIRCULAR` |
| Local neighbor revision | INDEPENDENT_CAPABILITY_SAMPLE | representation: complementary | no `TOO_SIMILAR` / no `CIRCULAR` |
| Local representation revision | COMPLEMENTARY_CAPABILITY | neighbor: complementary | no `TOO_SIMILAR` / no `CIRCULAR` |
| MCTS source revision | COMPLEMENTARY_CAPABILITY | expansion: complementary stage | no `TOO_SIMILAR` / no `CIRCULAR` |
| UCS depth-cost replacement | COMPLEMENTARY_CAPABILITY | accumulation: complementary | no `TOO_SIMILAR` / no `CIRCULAR` |
| A* zero-heuristic replacement | COMPLEMENTARY_CAPABILITY | component change: complementary | no `TOO_SIMILAR` / no `CIRCULAR` |

这些分类表示内容审计结论，不将 external result 用作 production mastery 的外部“真值”。

## Parallel-form and Study A architecture reassessment

| Concept | Current external composition | Form readiness |
| --- | --- | --- |
| BFS | FIFO queue trace + conditional-cost application | BUNDLE_READY_BUT_NOT_PARALLEL |
| UCS | cost accumulation + depth/cost trade-off | BUNDLE_READY_BUT_NOT_PARALLEL |
| A* | same-h component change + `h=0` extreme | BUNDLE_READY_BUT_NOT_PARALLEL |
| Local Search | neighborhood framing + representation/focus | BUNDLE_READY_BUT_NOT_PARALLEL |
| Minimax | MIN-node item + two-level transfer item | PAIR_NOT_READY; second is TRANSFER_EXPLORATORY_ONLY |
| MCTS | expansion function + backpropagation function | BUNDLE_READY_BUT_NOT_PARALLEL |

没有 concept 拥有经过 owner-reviewed 的严格 immediate/delayed parallel pair。故不建议方案 A
（强制严格平行 form）。最诚实的近期路线是：

1. **方案 B：concept bundle**，把同一 concept 的不同 closed micro-capability 透明记录为
   `correct / total` independent course-grounded performance criteria；
2. **方案 C：reduced-concept feasibility pilot**，在所有 changed item 获 owner second review
   后，优先以 BFS、UCS、MCTS 的三 concept bundle 进行小规模 measurement feasibility
   设计评估；
3. A*、Local Search、Minimax 先保留为设计资产，不把当前两题伪装为 delayed parallel pair。

这只是 instrument-design 建议；不启动真人研究，也不称任一分数为 true mastery、ground truth
knowledge 或 calibrated probability。

## Candidate and pipeline representation

候选 JSON 仍使用既有严格 schema：12 个 active、closed、deterministic、research-only
`single_choice` items，所有 item 为 `pending_owner_review`。rejected original 不硬塞入 active
schema，而在本文件保存完整审计历史。`tools/run_p7_synthetic_study.py` 的 S2 仅从旧 UCS ID
切换到 replacement ID；synthetic pipeline 的场景、policy、隐私边界和研究含义不变。

## Owner decision still required

本轮最多达到 **READY_FOR_SECOND_OWNER_REVIEW**。进入 P7 LEVEL 2 前仍需要负责人逐题确认：

1. 四道 revision 是否接受；
2. 两道 replacement 是否接受其 source、independence 与 difficulty boundary；
3. 是否采用 concept bundle，或继续等待真正 delayed parallel forms；
4. 在任何真人研究前完成独立的伦理、机构与参与者流程审核。
