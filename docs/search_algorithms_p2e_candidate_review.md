# P2e：Informed Search 候选审核与生产晋级记录

## 批次边界

- 批次：`search_algorithms_p2e_a`
- 候选状态：`promoted_to_production`
- 候选文件：`data/candidate_templates/search_algorithms_p2e_candidates.json`
- 本批四道候选已晋级；在后续 P2f 晋级后 production `human_verified` 模板总数为 20，active P2e candidates 为 0。
- 课件页码均为 `ai_lec3_informed_search.pdf` 当前精简 PDF 的 1-based 物理页码。
- 工程自审、独立内容审核与负责人最终决定是三个不同层级；本轮只因负责人正式批准而晋级。代码修改仍待用户 Git commit。

## 原始 PDF 复核

使用 `pdfinfo` 确认 Lec3 当前精简 PDF 共 65 页，使用 `pdftotext -layout` 核验文本层，并对下列关键公式/图示页做了视觉复核：

| 页码 | 可直接读取的课件事实 | 用途 |
| --- | --- | --- |
| p.9 | 图中以 `h(x)` 表示到 Bucharest 的直线距离，并写明“每次均选择离目标状态最近的节点”。 | 贪婪搜索 min-h 选择 |
| p.18 | `f(n)=g(n)+h(n)`；`g(n)` 是起始结点到 n 的开销代价值；`h(n)` 是 n 到目标结点路径中所估算的最小开销代价值。 | g/h 角色与 A* min-f |
| p.21 | A* 展开过程把 Sibiu=393、Timisoara=447、Zerind=449 并列，并标示继续选择 Sibiu。 | A* 按当前最小 f 值选择 frontier 节点 |
| p.30 | 可采纳性：任意 n 有 `h(n) ≤ h*(n)`；启发函数不高估，估计代价小于等于实际代价。 | 可采纳性边界与等号允许 |
| p.39 | 一致性使用独立不等式，且可推出可采纳性。 | 明确本批可采纳性题不测试 consistency |

无 OCR、网络或 API 调用。本批候选只引用课程主课件；没有以数据结构 support 材料代替 AI 搜索定义。

## 候选题独立内容审核

### 1. `verify_informed_search_g_h_roles_v1`

- 主 concept：`informed_search_and_heuristics`
- 题型：`multiple_choice_v1`
- 来源：`lec3_a_star_f_g_h`，p.18（直接证据）
- 测量边界：仅区分已付路径开销 `g(n)` 和到目标的估计 `h(n)`；不测量 min-f 选择、可采纳性或 A* 最优性。
- 正确项：第 1、3 个视觉位置；干扰项交换 g/h 的方向，未引入课件之外的断言。
- eligible intents：`diagnostic_request`、`definition`、`explanation`、`comparison`。不含 `algorithm_trace`，因为题目不要求选择 frontier 节点。
- 工程自审：`APPROVE_FOR_HUMAN_REVIEW`。
- 负责人决定：`approve`。

### 2. `verify_greedy_min_h_choice_v1`

- 主 concept：`greedy_best_first_search`
- 题型：`single_choice_v1`
- 来源：`lec3_greedy_search`，p.9（直接证据）
- 测量边界：题面指定 h 是到目标的估计距离并消除并列，只验证 min-h 的一次节点选择。D 的 `g+h` 更小，专门区分 Greedy 与 A*；题目不把选择结果外推为最优性或完备性结论。
- 正确项：第 2 个视觉位置（B）。
- eligible intents：`diagnostic_request`、`definition`、`explanation`、`algorithm_trace`；不因“Greedy/A* 比较”问题而自动覆盖比较类诊断。
- 工程自审：`APPROVE_FOR_HUMAN_REVIEW`。
- 负责人决定：`approve`。

### 3. `verify_astar_min_f_choice_v1`

- 主 concept：`a_star_search`
- 题型：`single_choice_v1`
- 来源：`lec3_a_star_f_g_h`，p.18 与 p.21（直接证据链）
- 测量边界：p.18 直接定义 `f(n)=g(n)+h(n)`；p.21 的展开过程直接展示按当前最小 f 值继续选择 frontier 节点。题面中的四个 f 值为 6、7、4、5，唯一答案为 C。它不测量可采纳性、一致性，亦不宣称因此已验证 A* 的完整最优性条件。
- 正确项：第 3 个视觉位置（C）。
- eligible intents：`diagnostic_request`、`definition`、`explanation`、`algorithm_trace`。晋级后，只有这些直接匹配的 intent 才可选择该模板；其他 intent 仍安全 unavailable。
- 工程自审：`APPROVE_FOR_HUMAN_REVIEW`。
- 负责人决定：`approve`。

### 4. `verify_admissibility_no_overestimate_v1`

- 主 concept：`admissibility_and_consistency`
- 题型：`single_choice_v1`
- 来源：`lec3_admissibility`，p.30（直接证据）
- 测量边界：P 的 `h*=4`、Q 的 `h*=7`；正确选项使 P 取等号、Q 低估，验证 `h≤h*` 和等号允许。每个其他选项至少有一处高估。它不测量 consistency，也不将可采纳性写成 graph-search A* 的完整最优性通则。
- 正确项：第 4 个视觉位置（D）。
- eligible intents：`diagnostic_request`、`definition`、`explanation`；不含 `algorithm_trace` 或 `comparison`，避免把单一性质检查扩大为算法过程/性质对比题。
- 工程自审：`APPROVE_FOR_HUMAN_REVIEW`。
- 负责人决定：`approve`。

## 题库与证据隔离检查

1. 历史候选均已以 `human_verified`、`mastery_verification` 状态进入 production bank。
2. candidate staging 顶层为 `promoted_to_production`，`templates=[]`、`acceptance_cases={}`；它仍不是 production loader 的两字段 document。
3. active candidate 与 production 不存在同 ID；`TemplateSelectionService` 和 `VerificationDiagnosticService` 只读取 production reviewed bank。
4. 四题各自只映射一个 primary concept；没有借由增加 `concept_ids` 制造表面覆盖。
5. 四题的 `misconception_rules=[]`。错误选择只触发 reviewed hint，不创建未经负责人确认的 learner-state misconception。
6. 四个 source reference 均可解析为真实 course chunk、文件和当前 PDF 页码。

## 答案位置与意图风险

| template | 题型 | 正确项视觉位置 | 审计结论 |
| --- | --- | ---: | --- |
| g/h roles | multiple choice | 1、3 | 多选不套用单选位置配额；正确项分散，错误项夹在中间。 |
| Greedy min-h | single choice | 2 / B | 符合 P2e-0 建议的 B 位置。 |
| A* min-f | single choice | 3 / C | 符合 P2e-0 建议的 C 位置。 |
| admissibility | single choice | 4 / D | 符合 P2e-0 建议的 D 位置。 |

`eligible_intents` 只标记题目确实能验证的理解场景；本次没有更改 production selector 或任一既有 production template 的 intent gate。批准后的四题按其已有 intent 进入 QA handoff。

## 独立内容审核准备状态

本轮独立课程内容审核已完成，结论如下：

| template | independent review verdict | 审核结论摘要 |
| --- | --- | --- |
| `verify_informed_search_g_h_roles_v1` | `APPROVE` | Lec3 p.18 直接支持 g/h 定义；正确项唯一，未将 g/h 与 f 混淆。 |
| `verify_greedy_min_h_choice_v1` | `APPROVE` | Lec3 p.9 直接支持按 h 选择离目标最近节点；B 是唯一最小 h，D 有效区分 A* 的 g+h。 |
| `verify_astar_min_f_choice_v1` | `APPROVE` | Lec3 p.18 支持 f=g+h，p.21 直接展示按当前最小 f 值继续选择 frontier 节点；C 唯一。 |
| `verify_admissibility_no_overestimate_v1` | `APPROVE` | Lec3 p.30 直接支持 h≤h* 与等号允许；D 唯一，未混淆 consistency。 |

**重要边界：独立内容审核 `APPROVE` 不等于课程负责人 `human approval`。**

负责人最终决定已单独记录如下：

| template | owner final decision | promotion result |
| --- | --- | --- |
| `verify_informed_search_g_h_roles_v1` | `approve` | `human_verified` production template |
| `verify_greedy_min_h_choice_v1` | `approve` | `human_verified` production template |
| `verify_astar_min_f_choice_v1` | `approve` | `human_verified` production template |
| `verify_admissibility_no_overestimate_v1` | `approve` | `human_verified` production template |

Promotion status：`promoted_to_production`，code changes pending user commit。
原 candidate staging 已清空；四题现由 `data/diagnostic_templates.json` 的 reviewed bank
提供，因此可在既有验证流程中生成 evidence。没有单独新增 selector、scorer 或 evidence pipeline。

## 人工审核清单

本清单已用于负责人审核与本次 promotion；后续增量仍应沿用：

1. 题干、中文术语、每个选项与 p.9 / p.18 / p.30 是否一致；
2. 每题唯一正确答案是否仍成立，尤其 Greedy 的 min-h 与 A* 的 min-f 是否清楚区分；
3. g/h 题是否保留“估算”而未误称 h 为已知真实值；
4. 可采纳性题的等号、低估与高估边界是否足够清楚；
5. 四题的 hint / explanation 是否不超出测量边界；
6. `eligible_intents` 是否适合实际诊断 handoff；
7. 决定 `approve`、`revise` 或 `reject`，并记录签署者与日期。

本次四题已经批准并晋级。仍需保持能力边界：A* 只因直接匹配且 intent 合法时可被
handoff 选择；不存在模板、unsupported intent、unknown concept 或仅 supporting topic 的情形继续安全 unavailable。
