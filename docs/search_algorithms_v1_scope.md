# Search Algorithms v1 范围与完成定义

## 1. 文档目的

本文基于 `feature/search-algorithms-v1-scope` 分支的真实仓库状态，定义 Search Algorithms v1 的课程边界、诊断完成标准和安全约束。本文是后续 reviewed diagnostic templates 与 deterministic scorers 的实施依据，不改变现有生产行为。

## 2. 当前系统能力

### 2.1 已验证的课程与问答资产

- `data/knowledge_points.json` 定义 26 个 Search Algorithms concept IDs 及其前置关系。
- `data/course_chunks.json` 包含 69 个本地课程 chunks：58 个 `course_core`、11 个 `prerequisite_support`。
- 26 个 concept ID 均至少被一个 chunk 覆盖；当前不存在“知识图谱中有 concept、课程材料中完全没有 chunk”的情况。
- 课程主线来源为：
  - `ai_lec2_uninformed_search.pdf`：19 chunks；
  - `ai_lec3_informed_search.pdf`：16 chunks；
  - `ai_lec4_local_search_and_llm_search.pdf`：8 chunks；
  - `ai_lec5_adversarial_search.pdf`：6 chunks；
  - `ai_lec6_mcts_and_search_summary.pdf`：9 chunks。
- 三份 `prerequisite_support` 共 11 chunks，只用于解释 stack、queue、priority queue、tree、graph、visited、heap 与 Dijkstra 等先修内容，不替代 AI 搜索算法定义。
- 自由问答链已经支持课程约束回答、页码引用、`topic_ids`、`diagnostic_topic_ids`、`supporting_topic_ids`，以及从 QA 到 reviewed diagnostic plan 的主动 handoff。

| Source file | Role | 当前 PDF 页数 | Chunk 数 | 诊断规划中的定位 |
| --- | --- | ---: | ---: | --- |
| `ai_lec2_uninformed_search.pdf` | `course_core` | 66 | 19 | v1 问题表示、通用搜索、BFS/DFS/IDDFS/UCS 的主要依据 |
| `ai_lec3_informed_search.pdf` | `course_core` | 65 | 16 | v1 heuristic、Greedy、A*、admissibility/consistency 的主要依据 |
| `ai_lec4_local_search_and_llm_search.pdf` | `course_core` | 32 | 8 | v1.1 |
| `ai_lec5_adversarial_search.pdf` | `course_core` | 38 | 6 | v1.1 |
| `ai_lec6_mcts_and_search_summary.pdf` | `course_core` | 44 | 9 | v1.1 与单元总结；p.33 仍需人工审核 |
| `ds_stack_queue_priority_queue.pdf` | `prerequisite_support` | 15 | 4 | BFS/DFS/UCS 容器先修 |
| `ds_tree_traversal_heap.pdf` | `prerequisite_support` | 13 | 3 | 搜索树、BFS、UCS 容器先修 |
| `ds_graph_traversal_shortest_path.pdf` | `prerequisite_support` | 26 | 4 | graph/visited/BFS/Dijkstra 对照先修 |

69 个 chunks 的 review status 为：66 个 `codex_draft`、2 个 `human_verified`、1 个 `needs_human_review`。Chunk review status 与 diagnostic template 的 `human_verified` 是两道独立门槛；不能因为 chunk 已审核就自动产生 mastery evidence。

### 2.2 已验证的诊断与学习状态边界

- 双轨诊断已把开放式形成性反馈与 mastery verification 分离。
- 开放式 formative 轨道的 `purpose="formative"`、`evidence_eligible=false`，不得更新 learner state。
- verification 轨道只接受 `human_verified`、`purpose="mastery_verification"` 的模板。
- 只有 completed 且 `evidence_eligible=true` 的 verification summary 才能进入 `DiagnosticStateIntegrationService.apply()`。
- `DiagnosticStateIntegrationService` 使用最后一次未辅助 observation 作为 `selected_signal`；只有受辅助 observation 时不更新该 concept。
- mastery 公式保持为 `new = (1 - observation_weight) * old + observation_weight * selected_signal`，默认 `observation_weight=0.35`。
- recommendation 根据知识图谱顺序、`mastery < 0.6` 和前置关系回溯生成；本轮不改变该算法。
- 现有 41-case `data/diagnostic_scoring_benchmark.json` 验证的是三道开放式 formative 问题的自然语言判题边界，不是 mastery-verification template bank。

### 2.3 当前受控验证能力

当前 `data/diagnostic_templates.json` 有 20 个 reviewed templates：

| Template | 被验证的能力 | 写入的 concept observations |
| --- | --- | --- |
| `verify_bfs_frontier_choice_v1` | BFS 按 FIFO 顺序从 frontier 选节点 | `breadth_first_search` |
| `verify_bfs_equal_cost_condition_v1` | 等步代价时，最少步数与最低路径总代价等价 | `breadth_first_search`、`completeness_optimality_complexity` |
| `verify_ucs_min_g_choice_v1` | UCS 选择累计路径代价 `g(n)` 最小的 frontier 节点 | `uniform_cost_search` |
| `verify_search_problem_components_v1` | 识别课件明确列出的五项搜索问题定义要素 | `search_problem_formulation` |
| `verify_successor_operator_v1` | 对八数码状态应用一次合法 operator | `state_space_and_operators` |
| `verify_frontier_explored_membership_v1` | 在明确 graph-search 时间线中区分 frontier node 与 explored state | `frontier_and_explored_set` |
| `verify_graph_search_repeated_state_handling_v1` | 应用 Lec2 p.27 的 closed-state 条件处理重复 problem state | `tree_search_vs_graph_search` |
| `verify_dfs_frontier_choice_v1` | 根据 deepest-first 与 stack LIFO 选择 DFS 下一节点 | `depth_first_search` |
| `verify_iddfs_depth_limit_schedule_v1` | 提高 depth limit 并从根重新运行下一轮受限 DFS | `iterative_deepening_search` |
| `verify_informed_search_g_h_roles_v1` | 区分 g(n) 已付开销与 h(n) 到目标的估计 | `informed_search_and_heuristics` |
| `verify_greedy_min_h_choice_v1` | 按唯一最小 h(n) 选择 Greedy frontier 节点 | `greedy_best_first_search` |
| `verify_astar_min_f_choice_v1` | 按唯一最小 f(n)=g(n)+h(n) 选择 A* frontier 节点 | `a_star_search` |
| `verify_admissibility_no_overestimate_v1` | 判断 h(n)≤h*(n)，包括等号允许 | `admissibility_and_consistency` |

当前生产 template bank 使用：

- `question_type="single_choice"` / `deterministic_scorer="single_choice_v1"`；
- `question_type="multiple_choice"` / `deterministic_scorer="multiple_choice_v1"`；
- single-choice 的唯一正确 `choice_id`；
- multiple-choice 的 exact-match `choice_ids`；
- 二元分数 `0.0/1.0`；
- single-choice 可使用显式 choice-to-misconception mapping；
- reviewed hint、explanation 和 benchmark case IDs。

因此，当前真实 mastery-evidence 覆盖为：

- 20 / 26 个 concept IDs；
- 13 / 13 个本文件定义的 v1 concept IDs；
- 其中 `completeness_optimality_complexity` 只由 BFS 等步代价这一项提供局部证据，不能视为已经覆盖完整的完备性、最优性、时间和空间复杂度能力；A* 只覆盖一次 min-f 选择，`admissibility_and_consistency` 只覆盖可采纳性，不代表完整 capability coverage。

## 3. Search Algorithms v1 边界

v1 定义为“搜索问题表示 → 通用搜索结构 → 无信息搜索 → 有信息搜索”的连续黄金样板，共使用 13 个现有 concept IDs。

### 3.1 搜索问题表示

| concept_id | 中文名称 | 主要课程证据 |
| --- | --- | --- |
| `search_problem_formulation` | 搜索问题建模 | Lec2 pp.6–12 |
| `state_space_and_operators` | 状态空间与操作 | Lec2 pp.6–12 |

验证范围包括 state、initial state、action、transition model、goal test、path cost。它们是现有 concept 的组成部分，不新增六个更细 concept IDs。

### 3.2 通用搜索结构

| concept_id | 中文名称 | 主要课程证据 |
| --- | --- | --- |
| `tree_search_vs_graph_search` | 树搜索与图搜索 | Lec2 pp.14–18、21–27；Lec3 pp.37–38 |
| `frontier_and_explored_set` | 边界队列与已探索集合 | Lec2 pp.20–27 |

验证范围包括 frontier、explored set、repeated states、cycle handling，以及“问题状态”和“搜索树节点”的区别。

### 3.3 无信息搜索

| concept_id | 中文名称 | 主要课程证据 |
| --- | --- | --- |
| `breadth_first_search` | 广度优先搜索 | Lec2 pp.31–35、49、53–57 |
| `depth_first_search` | 深度优先搜索 | Lec2 pp.37–49、53–57 |
| `iterative_deepening_search` | 迭代加深深度优先搜索 | Lec2 pp.53–58 |
| `completeness_optimality_complexity` | 完备性、最优性与复杂度 | Lec2 pp.28–29、35、48–49、58、63；Lec3 pp.14、26 |
| `uniform_cost_search` | 一致代价搜索 | Lec2 pp.60–64；Lec3 pp.40–41 |

Depth-Limited Search 在当前材料中作为 iterative deepening 的内部机制出现，但没有独立 concept ID。v1 应验证“深度限制、cutoff 与逐轮增大限制”的能力，并把 evidence 归到 `iterative_deepening_search`；本阶段不新增 `depth_limited_search` concept。

### 3.4 有信息搜索

| concept_id | 中文名称 | 主要课程证据 |
| --- | --- | --- |
| `informed_search_and_heuristics` | 有信息搜索与启发函数 | Lec3 pp.2–5、52–59 |
| `greedy_best_first_search` | 贪心最佳优先搜索 | Lec3 pp.7–14 |
| `a_star_search` | A* 搜索 | Lec3 pp.16–41、48–50、53–60 |
| `admissibility_and_consistency` | 可采纳性与一致性 | Lec3 pp.27–39、52、59 |

`g(n)`、`h(n)`、`f(n)` 是这些现有 concepts 的能力切片，不新增独立 concept IDs。当前 chunks 在 Lec3 pp.53–56 比较了两种八数码启发式，但没有把 heuristic dominance 单独建模为 concept 或专门 chunk。v1 可在人工复核原页后把 dominance 作为 `informed_search_and_heuristics` / `admissibility_and_consistency` 的候选扩展能力；在复核前不把它计入必达 template 数，也不为其单独创建 mastery 节点。

## 4. Search Algorithms v1.1 边界

v1.1 使用剩余 13 个现有 concept IDs：

### 4.1 局部与演化搜索

- `local_search`
- `hill_climbing`
- `simulated_annealing`
- `evolutionary_search`

课程证据主要在 Lec4 pp.9–27。它们具有真实材料，但受控题需要新的状态邻域、目标值变化或概率接受等题目设计，暂不挤占 v1 主线。

### 4.2 LLM search 与测试时扩展

- `llm_search_and_test_time_scaling`

课程证据主要在 Lec4 pp.3–8、28–30 和 Lec6 pp.37–42。该内容变化较快，且部分学习目标更适合概念比较而非基础搜索算法 scorer，延后到 v1.1。

### 4.3 对抗搜索

- `adversarial_search`
- `minimax_search`
- `alpha_beta_pruning`
- `game_state_evaluation`

课程证据主要在 Lec5 pp.4–38。Minimax 值回传和 Alpha-Beta 剪枝适合确定性验证，但需要树结构题目 schema 与更精细的节点/边展示，作为 v1.1 独立增量更安全。

### 4.4 Monte Carlo 与 MCTS

- `monte_carlo_search`
- `exploration_exploitation`
- `upper_confidence_bound`
- `monte_carlo_tree_search`

课程证据主要在 Lec6 pp.6–36。`lec6_adversarial_mcts_statistics`（Lec6 p.33）仍为 `needs_human_review`，不得直接成为 reviewed diagnostic 依据。其余材料可用于自由问答，但 UCB 数值、MCTS 四阶段和回传验证留到 v1.1。

## 5. 当前材料中存在但暂不进入诊断覆盖的内容

- 三份 prerequisite support 中的数据结构实现细节；
- Lec3 A* 应用案例和课堂综合练习中不适合作为唯一答案题的部分；
- Lec4 的 LLM Agent 规划、LLM-guided evolution；
- Lec6 的 AlphaGo、游戏 AI 应用与大模型讨论；
- 纯历史、应用或宽泛讨论内容；
- `needs_human_review` 的 Lec6 p.33。

这些内容可以继续作为 grounded QA evidence，但不自动获得 mastery-verification template。

## 6. 当前知识图谱或材料中的细粒度缺口

以下不是“缺失课程章节”，而是现有图谱刻意没有拆成独立 mastery 节点：

- Depth-Limited Search；
- `g(n)`、`h(n)`、`f(n)`；
- heuristic dominance（现有 chunks 有启发式比较案例，但没有专门的 dominance 定义或 concept）；
- repeated-state reopening / path replacement；
- tree-search 与 graph-search 下 A* 最优性条件差异。

v1 先把它们作为现有 concept 的受控能力切片。只有当多道 reviewed templates、推荐策略和 learner-state 展示都确实需要单独追踪时，才评审新增 concept；本轮不建议新增 concept。

## 7. 不做事项

v1 不包括：

- 开放式 formative 回答直接更新 mastery；
- LLM 生成、选择或评分 mastery-verification 题；
- 为自然语言 matcher 无上限添加同义词；
- 自动把 diagnostic open questions 转成 reviewed templates；
- small graph 的任意路径判定、图形编辑器或拖拽 UI；
- 新 recommendation 算法、mastery 公式或 observation weight；
- 新 learner-state schema；
- 本地材料重新解析、OCR 或课程内容扩写；
- v1.1 中的局部搜索、对抗搜索、MCTS/UCB 模板。

## 8. v1 完成定义

建议目标为 **21 个 human-reviewed templates**：当前已有 20 个，剩余 1 个因证据不足而 blocked。该数量位于 15–25 的目标区间，并能覆盖 13 个 v1 concepts 的至少一个核心可验证能力。

P2f 七道 owner-approved candidate 已晋级 production；staging 为 `promoted_to_production`、active
candidate 为 0，production 为 20 / 21。UCS lower-cost frontier-update slot 因缺少主课件
direct replacement 规则仍为 `blocked`，因此当前 course-core 支持的高质量 reviewed 总数上限为 20。

每个新增 template 必须满足：

1. `concept_ids` 均来自现有知识图谱；
2. 课程来源精确到当前 chunk 的文件名和物理页码；
3. 有唯一或可确定的正确答案；
4. 使用版本化 deterministic scorer；
5. 有 reviewed misconception、hint 和 explanation；
6. 有至少一个正确、一个典型错误、一个非法输入测试；
7. 有稳定 selection 顺序与 intent tests；
8. `review_status="human_verified"`、`purpose="mastery_verification"`；
9. assistance provenance、reveal、evidence gate 和 P5B 不回归；
10. 同一 template 映射多个 concepts 时，必须证明该题对每个 concept 提供同等强度证据；否则只映射主要 concept。

v1 的“覆盖”分三级报告，避免用一个数字掩盖质量：

- **material coverage**：concept 有课程 chunks；
- **template coverage**：concept 至少有一项 reviewed verification；
- **capability coverage**：知识点的主要 mastery criteria 是否被不同能力题覆盖。

## 9. 安全边界

- Python 与 reviewed data 对 template selection、scoring、evidence、mastery 和 recommendation 保持最终控制权。
- 只有 verification observation 可进入 learner state。
- formative benchmark 与 semantic advisory 不能转换为 verification evidence。
- assisted pass 可以推进题目，但不能冒充 independent mastery evidence。
- scorer 必须拒绝未知 choice、重复选择、非有限数值、未知字段和损坏 session。
- 新 scorer 必须输出与现有 pipeline 兼容的规范结果：`score`、`passed`、`misconception_ids`、`feedback`。
- v1 首版仍采用二元 evidence（0.0/1.0）；不引入未经评审的部分分公式。

## 10. 验收标准

### 自动验收

- 全量 pytest 通过；
- template loader 对每个新 question type 严格校验；
- 每个 scorer 有正例、负例、边界、损坏输入和输入不变性测试；
- selector 对相同 concepts/intents 返回稳定顺序；
- QA handoff 对有模板 concept 可用、无模板 concept 继续安全 abstain；
- verification completed 前不 integration，completed 后只 integration 一次；
- reveal-only 不创建 observation，hint-assisted retry 不成为独立 evidence；
- existing BFS/UCS flows、41-case formative benchmark、retrieval 和自由问答不回归。

### 人工验收

- 学生只看到题面与可理解的 choice text，不看到 expected answer ID；
- 每道题的正确答案、错误解释和课程页码经人工复核；
- 同一题在刷新/rerun 后不会换模板、换选项或重复提交；
- 错误答案产生的 misconception 与题目设计一致，不做超出选择证据的推断；
- 每个增量至少从空 learner state 完成一次，并检查 observation、assistance、state update 和 recommendation trace。
# P2g status note

P2g hardening established the gate; P5b promotion now leaves 28 production reviewed templates,
0 active candidates, one blocked capability slot, and the existing blocked slot unchanged. A production template is
still only a narrow evidence slice: Search Algorithms v1 is not complete merely because template
metadata exists.
