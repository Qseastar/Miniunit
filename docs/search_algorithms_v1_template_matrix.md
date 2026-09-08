# Search Algorithms v1 Reviewed Template Matrix

## 1. 使用说明

本矩阵以当前仓库的 13 个 v1 concept IDs 为边界。计划总量为 **21 个 templates（现有 20 + 1 个 blocked slot）**。

状态约定：

- `current_human_verified`：当前真实存在，不修改；
- `candidate_draft`：已起草并通过工程 contract 检查，但尚待负责人内容审核，不计入 production coverage；
- `owner_approved_pending_promotion`：历史状态；P2f 七道题已完成 promotion，不再使用；
- `revised_candidate_pending_re_review`：历史修订阶段状态；
- `proposed_P0`：主线能力，优先补齐；
- `proposed_P1`：同 concept 的第二能力、性质比较或新 scorer 的深化；
- `proposed_new_concept`：本矩阵没有此类条目；细粒度内容先归入现有 concept。

题型约定：

- `single_choice` 当前已支持；
- `node_selection` 和 `true_false` 在 v1 中只是 `single_choice` 的内容形态，不新建同义 scorer；
- `multiple_choice`、`numeric_answer`、`ordering` 的 scorer foundation 已完成；当前 production 已使用 `multiple_choice`，其余题型仍需 reviewed template 才会进入生产；
- `small_graph_path` 不进入 v1。

课件页码均为当前精简 PDF 的 1-based 物理页码。

## 2. Template matrix

| Priority | concept_id | 中文名称 | 课件来源与页码 | Prerequisite | Learning objective | Verification goal | Proposed template | Question type | Scorer | Misconception | Hint / explanation requirement | Current coverage | Dependencies | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | `breadth_first_search` | 广度优先搜索 | Lec2 pp.31–34 | `frontier_and_explored_set` | 追踪 BFS 扩展顺序 | 从按序加入的 frontier 选择下一节点 | `verify_bfs_frontier_choice_v1` | `single_choice` | `single_choice_v1` | 选择最后加入节点 → `bfs_is_depth_first` | 提示 FIFO；解释先入先出与按层扩展 | 已有 9 chunks；已有 reviewed template | 现有 scorer/evidence pipeline | `current_human_verified` |
| P0 | `breadth_first_search`、`completeness_optimality_complexity` | BFS；完备性、最优性与复杂度 | Lec2 pp.11、35、63 | BFS 依赖 frontier；性质 concept 依赖 BFS/DFS | 区分最少步数和最低总代价 | 识别等步代价是 BFS cost-optimal 的条件 | `verify_bfs_equal_cost_condition_v1` | `single_choice` | `single_choice_v1` | 非负边权即足够 → `bfs_always_cost_optimal` | 提示 equal cost 与 nonnegative 不同；解释步数/总代价关系 | BFS 2 个 reviewed；性质 concept 仅此局部证据 | 现有 scorer；多 concept 等强度需持续审查 | `current_human_verified` |
| P0 | `uniform_cost_search` | 一致代价搜索 | Lec2 pp.60–62 | `frontier_and_explored_set`、`completeness_optimality_complexity` | 按累计路径代价选择节点 | 从给定 `g(n)` 中选择最小者 | `verify_ucs_min_g_choice_v1` | `single_choice`（node selection） | `single_choice_v1` | 不从错误选择推断深度误解，除非选项有明确语义 | 提示比较 `g(n)`；解释 UCS 的选择标准 | 已有 11 chunks；已有 1 个 reviewed template | 现有 scorer/evidence pipeline | `current_human_verified` |
| P0 | `search_problem_formulation` | 搜索问题建模 | Lec2 pp.6–10 | 无 | 识别搜索问题的核心组成 | 从候选项中选出 initial state、actions、transition model、goal test、path cost | `verify_search_problem_components_v1` | `multiple_choice` | `multiple_choice_v1` | 把 algorithm/frontier 当作问题定义的必需组成 | 提示区分“问题定义”和“求解方法”；解释课件明确列出的五项要素 | 4 chunks；已有 reviewed template | P2b scorer/evidence pipeline | `current_human_verified` |
| P1 | `search_problem_formulation` | 搜索问题建模 | Lec2 pp.11–12 | 无 | 正确计算并使用 path cost | 在明确单位步代价下累计三次行动的路径代价 | `verify_path_cost_accumulation_v1` | `single_choice` | `single_choice_v1` | 只取最后一步；把节点数当代价 | 提示累计行动而非节点；不外推到非单位代价 | 4 chunks；已有 reviewed template | production；supported inference；owner approved，已晋级 | `current_human_verified` |
| P0 | `state_space_and_operators` | 状态空间与操作 | Lec2 pp.6–10、12 | `search_problem_formulation` | 用 operator/transition 生成合法 successor | 给定状态和动作约束，选择合法后继 | `verify_successor_operator_v1` | `single_choice` | `single_choice_v1` | 把非法动作或动作名本身当作 successor state | 提示先应用 transition model；解释候选中唯一正确不等于全局唯一 successor | 3 chunks；已有 reviewed template | 现有 scorer/evidence pipeline | `current_human_verified` |
| P1 | `tree_search_vs_graph_search` | 树搜索与图搜索 | Lec2 p.27 | `state_space_and_operators` | 区分 problem state 与 search node | 判断不同 node 是否可由 `STATE[node]` 表示同一 state | `verify_search_node_state_distinction_v1` | `single_choice` | `single_choice_v1` | 同 state 必为同 node；state 等同 closed | 提示伪代码中 node/`STATE[node]` 的不同角色 | 8 chunks；已有 reviewed templates | production；supported inference；owner approved，已晋级 | `current_human_verified` |
| P0 | `tree_search_vs_graph_search` | 树搜索与图搜索 | Lec2 p.27 | `state_space_and_operators` | 理解 repeated-state checking 与 cycle handling | 应用课件 pop 后、expand 前的 closed-state 条件分支 | `verify_graph_search_repeated_state_handling_v1` | `single_choice` | `single_choice_v1` | 认为不同 search node 必然表示不同 problem state | 提示比较 STATE[node] 与 closed/explored；解释不覆盖 reopening 或 frontier duplicate | 8 chunks；已有 reviewed template | direct source；负责人已批准 | `current_human_verified` |
| P0 | `frontier_and_explored_set` | 边界队列与已探索集合 | Lec2 pp.20、27 | `tree_search_vs_graph_search` | 区分待扩展与已记录状态 | 在明确 graph-search 时间线中分类 frontier node 与 explored state | `verify_frontier_explored_membership_v1` | `multiple_choice` | `multiple_choice_v1` | 混淆 frontier 与 explored；忽略题面声明的加入时点 | 提示按时间线分别写出两集合；解释该时点是题面约定 | 4 chunks；已有 reviewed template | P2b scorer/evidence pipeline | `current_human_verified` |
| P0 | `depth_first_search` | 深度优先搜索 | Lec2 pp.37–46；stack support pp.1–2 | `frontier_and_explored_set` | 追踪 deepest-first 扩展 | 根据明确的 stack 与入栈顺序选择 DFS 的下一节点 | `verify_dfs_frontier_choice_v1` | `single_choice`（node selection） | `single_choice_v1` | 忽略 deepest-first 或同深度下的 LIFO | 提示读取栈顶；解释 LIFO/deepest-first | 10 chunks；已有 reviewed template | 现有 scorer；联合来源已审核 | `current_human_verified` |
| P1 | `depth_first_search` | 深度优先搜索 | Lec2 pp.37–46、p.48 | `frontier_and_explored_set` | 识别无限深分支下的风险 | 在题面给定无限先行分支时判断是否保证找到浅层目标 | `verify_dfs_infinite_branch_risk_v1` | `single_choice` | `single_choice_v1` | 认为 DFS 必找浅层目标或必最优 | 提示 deepest-first 与 non-complete；不说每次失败 | 10 chunks；已有 reviewed templates | production；supported inference；owner approved，已晋级 | `current_human_verified` |
| P0 | `iterative_deepening_search` | 迭代加深深度优先搜索 | Lec2 pp.53–57 | `depth_first_search`、`breadth_first_search` | 理解逐轮提高 depth limit 并重启受限 DFS | 在题面声明 0、1、2 调度后选择下一轮 limit 与重启动作 | `verify_iddfs_depth_limit_schedule_v1` | `single_choice` | `single_choice_v1` | 认为提高 limit 时延续上一轮，或改成无限深 DFS | 提示检查 limit 增长和重启；解释 DLS 是 IDDFS 能力切片 | 2 chunks；已有 reviewed template；DLS 无独立 concept | direct source；题面消除起始展示差异 | `current_human_verified` |
| P1 | `completeness_optimality_complexity` | 完备性、最优性与复杂度 | Lec2 pp.35、48、53–58、63 | BFS、DFS、IDDFS、UCS | 比较算法性质而不混淆术语 | 识别 IDDFS 完备且仅在等步代价下最优 | `verify_search_algorithm_properties_v1` | `single_choice` | `single_choice_v1` | 把等代价条件错放到 complete；把 DFS 说 complete | 提示逐项核对算法与条件；不测完整性质矩阵 | 9 chunks；已有 reviewed template | production；supported inference；owner approved，已晋级 | `current_human_verified` |
| P1 | `uniform_cost_search` | 一致代价搜索 | Lec2 pp.60–64 | `frontier_and_explored_set`、性质 concept | 处理发现更低代价路径时的 frontier 更新 | 在已有 A(g=4) 后发现 A(g=1)，选择正确更新 | `verify_ucs_frontier_update_v1` | `single_choice` | `single_choice_v1` | 保留较高代价记录；把 depth 当 priority | 仅在负责人提供 direct update/replacement 课件证据后起草 | 11 chunks；已有 min-g node-selection，但无更新能力证据 | P2f 缺 direct replacement/decrease-key 证据 | `blocked` |
| P0 | `informed_search_and_heuristics` | 有信息搜索与启发函数 | Lec3 pp.2–5、16–18、52–57 | `uniform_cost_search` | 区分已付代价与剩余估计 | 从情境中识别 `g(n)`、`h(n)` 的角色 | `verify_informed_search_g_h_roles_v1` | `multiple_choice` | `multiple_choice_v1` | 把 h 当真实已付成本；要求 heuristic 必须精确 | 提示区分 past cost 与 estimate-to-go；解释 heuristic 的信息作用 | 9 chunks；1 reviewed capability slice | P2e-b promoted；只覆盖 g/h 角色 | `current_human_verified` |
| P0 | `greedy_best_first_search` | 贪心最佳优先搜索 | Lec3 pp.7–13 | `informed_search_and_heuristics` | 按最小 `h(n)` 选择节点 | 给定 g/h，选择 Greedy 下一节点 | `verify_greedy_min_h_choice_v1` | `single_choice`（node selection） | `single_choice_v1` | 使用 `g+h`，把 Greedy 与 A* 混淆 | 提示 Greedy 只比较 h；解释为何忽略已付成本 | 2 chunks；1 reviewed capability slice | P2e-b promoted；只覆盖一次 min-h 选择 | `current_human_verified` |
| P1 | `greedy_best_first_search` | 贪心最佳优先搜索 | Lec3 p.14 | `informed_search_and_heuristics` | 识别 Greedy 不保证总代价最优 | 从课件 bad case 识别“可能非最优、依赖启发式” | `verify_greedy_suboptimality_v1` | `single_choice` | `single_choice_v1` | 局部 h 最小必然产生全局最低总代价 | 提示课件 bad case；不说 Greedy 总失败 | 2 chunks；已有 reviewed templates | production；owner approved，已晋级 | `current_human_verified` |
| P1 | `a_star_search` | A* 搜索 | Lec3 p.18 | UCS、有信息搜索 | 正确计算 `f(n)=g(n)+h(n)` | 给定一个节点的 g/h，选择正确 f 值 | `verify_astar_f_value_v1` | `single_choice` | `single_choice_v1` | 只用 h；把 g 或 h 当 f | 提示一次有限加法；不测 min-f、性质或最优性 | 13 chunks；已有 reviewed templates | production；owner approved，已晋级 | `current_human_verified` |
| P0 | `a_star_search` | A* 搜索 | Lec3 pp.18、21、40–41 | UCS、有信息搜索 | 按最小 f 扩展节点 | 给定多个 g/h，选择 f 最小节点 | `verify_astar_min_f_choice_v1` | `single_choice`（node selection） | `single_choice_v1` | 按最小 h（Greedy）或最小 g（UCS）选择 | 提示先为每个节点计算 f；解释 A*/Greedy/UCS 的 priority 差异 | 13 chunks；1 reviewed capability slice | P2e-b promoted；不覆盖最优性条件 | `current_human_verified` |
| P0 | `admissibility_and_consistency` | 可采纳性与一致性 | Lec3 pp.27–36 | `a_star_search` | 判断 heuristic 是否高估真实剩余代价 | 给定 h 与 h*，判断 admissibility | `verify_admissibility_no_overestimate_v1` | `single_choice`（true/false content） | `single_choice_v1` | 允许 `h(n)>h*(n)`；认为 heuristic 必须等于真实值 | 提示检查是否 overestimate；解释可低估但不可高估 | 5 chunks；1 reviewed admissibility slice | P2e-b promoted；不覆盖 consistency | `current_human_verified` |
| P1 | `admissibility_and_consistency` | 可采纳性与一致性 | Lec3 p.39 | `a_star_search` | 检查边上的 consistency inequality | 给定 `h(n)`、`cost(n,a,n')`、`h(n')` 判断单边不等式 | `verify_consistency_edge_check_v1` | `single_choice` | `single_choice_v1` | 把 ≤ 当 <；混淆 admissibility；单边外推全局 | 提示代入边不等式；解释只检查一条边 | 5 chunks；已有 reviewed templates | production；owner approved，已晋级 | `current_human_verified` |

## 3. Coverage summary

### 3.1 Material coverage

- v1 的 13 个 concept IDs 均有 `course_core` chunks。
- `prerequisite_support` 只补充容器和图结构理解，不作为模板定义的唯一证据。
- v1 不需要重新解析 PDF。

### 3.2 Current reviewed-template coverage

| Coverage class | Concepts |
| --- | --- |
| 至少一个 reviewed template | `search_problem_formulation`、`state_space_and_operators`、`tree_search_vs_graph_search`、`frontier_and_explored_set`、`breadth_first_search`、`depth_first_search`、`iterative_deepening_search`、`completeness_optimality_complexity`、`uniform_cost_search` |
| 有材料、只有 formative/open questions、无 reviewed verification | 其余 4 个 v1 concepts |
| v1.1 有材料、无 reviewed verification | 13 个 v1.1 concepts |

`breadth_first_search` 的两项能力目前是最完整的样板。`uniform_cost_search` 只有“从 frontier 选最小 g”能力。`completeness_optimality_complexity` 只有 BFS 等步代价条件这一狭窄证据；不能把它标记为完整 capability coverage。

### 3.3 Multi-concept evidence risk

当前 `verify_bfs_equal_cost_condition_v1` 的一次二元得分会同时写入 BFS 和 `completeness_optimality_complexity`。现有 summary 对 template 的每个 `concept_id` 复制同一 score，不能表达 per-concept score。

后续原则：

- 默认每个 template 只映射一个主要 concept；
- 只有一道题确实独立、同等强度地验证多个 concepts 时才多映射；
- 不通过增加 concept IDs 来提高表面覆盖率；
- 若未来必须 per-concept scoring，应单独版本化 scorer result 与 summary schema，不在 template 内容增量中顺带修改。

## 4. Scorer roadmap

| Question form | 是否新增 scorer | 教学用途 | 输入 / expected schema（拟） | Deterministic 规则与容错 | 对 evidence pipeline 的影响 | Priority / dependent templates |
| --- | --- | --- | --- | --- | --- | --- |
| `single_choice` | 否，复用 `single_choice_v1` | 节点选择、真假判断、唯一性质判断 | 现有 answer 为 choice ID；expected `{"choice_id": "..."}` | 必须为已展示 choice ID；唯一相等才通过 | 无 | 已有 7；另有 UCS update、Greedy、A* node、admissibility、consistency |
| `true_false` | 否，作为两选项 single choice | 有明确条件的性质判断 | choices 为 reviewed `true/false` 文本 | 不接受自由 bool；仍提交 choice ID | 无 | admissibility、consistency |
| `node_selection` | 否，作为 single-choice 内容形态 | BFS/DFS/UCS/Greedy/A* 下一节点 | 每个 node 是一个 choice | tie 必须在题面消除或显式允许多个，此时不能用当前 scorer | 无 | BFS、DFS、UCS、Greedy、A* |
| `multiple_choice` | 是，`multiple_choice_v1` | 组成部分、分类、性质集合 | expected `{"choice_ids":[...]}`；answer 为严格 choice-ID list/object | 集合完全相等才 1.0；拒绝重复、未知 ID、额外字段；v1 不给部分分 | scorer 结果仍保持 0/1；service/history 需向后兼容结构化 answer | P2b；problem components、frontier/explored、property matrix、g/h roles |
| `numeric_answer` | 是，`numeric_answer_v1` | path cost、f 值和简单代价计算 | expected `{"value": number, "tolerance": number}`；学生输入保留字符串 | strip 后解析有限十进制；拒绝 bool、NaN、Infinity、表达式执行；默认整数题 tolerance=0 | scorer result 可保持 0/1；history 需保存规范化数值和原始安全输入 | P2b；path-cost sum、A* f value |
| `ordering` | 是，`ordering_v1` | IDDFS limits、固定 expansion order | expected `{"ordered_choice_ids":[...]}`；answer 为严格 ID list/object | 顺序完全一致；拒绝重复、遗漏、未知 ID；不做模糊文本匹配 | scorer result可保持 0/1；UI/history 需支持列表答案 | P2b；IDDFS limit schedule |
| `small_graph_path` | v1 不新增 | 多步路径、reopening、多解图题 | 需要版本化 graph、start/goal、edge cost、tie/path policy | 必须处理多条等价最优路径和图合法性；当前风险过高 | 会扩大 UI、session、expected answer 与 benchmark | v1.1/P2；当前只用 single choice 或 numeric 拆分能力 |

### 4.1 统一 scorer contract

新 scorer 应保持现有输出边界：

```text
{
  "score": 0.0 | 1.0,
  "passed": bool,
  "misconception_ids": [...],
  "feedback": [...]
}
```

P2b 需要把 verification history 的 choice-specific 字段泛化为版本化 answer record，同时保留旧字段兼容现有三题。该改动不得触碰 P5B 的 observation、assistance 与 selected-signal 语义。

## 5. Misconception review rule

矩阵中的 proposed misconception 均为**待人工审核的教学语义描述**，不是已经存在的 learner-state misconception IDs。实施时：

1. 先检查现有 canonical misconception 白名单；
2. 只有错误选项能唯一支持该推断时才添加 reviewed ID；
3. 无法唯一判断的错误只返回 hint，不记录 misconception；
4. misconception ID、description、template mapping 和正负例必须在同一增量验收；
5. 不从选错一个节点推断学生使用了某算法，除非选项设计明确编码了该策略。
