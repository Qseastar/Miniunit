# Search Algorithms v1 实施路线

## 1. 路线原则

本路线把 21 个 reviewed templates 的目标拆成可独立测试、可独立回滚的增量。顺序遵循：

1. 先稳定 scorer 与 answer/history contract；
2. 再补“问题表示 → 通用搜索”；
3. 再补无信息搜索；
4. 再补有信息搜索；
5. 最后做跨 concept 回归、人工验收与贡献规范。

原有 3 个 BFS/UCS templates 始终作为兼容基线；P2c-b 晋级 3 个通用搜索
templates，P2d-c 又晋级 3 个无信息搜索 templates，P2e-b 已晋级 4 个有信息搜索
templates；P2f 晋级后共有 20 个生产模板。任何
增量都不得让开放式 formative evidence 跨过 learner-state gate。

## 2. 当前架构约束

### 2.1 可原样复用

- `TemplateSelectionService` 的 concept 白名单、intent gate、稳定 priority/id 排序；
- `VerificationDiagnosticService` 的两次尝试、hint/reveal、session 深拷贝和 assistance provenance；
- `DualTrackDiagnosticWorkflowService` 的 formative / verification phase 与 evidence gate；
- `DiagnosticStateIntegrationService` 的 last-unassisted selection、mastery 公式和 recommendation 边界；
- QA handoff 的 reviewed-only、主动启动和 unsupported-topic abstain；
- 现有 41-case formative benchmark 与 semantic containment；
- 当前 20 道 human-reviewed templates 及其回归测试。

### 2.2 当前通用 contract 与剩余限制

- P2b 已让 template validator 支持 `single_choice_v1`、`multiple_choice_v1`、`numeric_answer_v1` 和 `ordering_v1`；
- verification `submit()` 已支持由 scorer contract 严格验证的字符串或结构化 answer；
- history 和 observation records 已增加通用 answer record，同时保留旧 single-choice 字段兼容；
- scorer result 虽然通用，但 validator 当前强制二元 0/1，这与 v1 的二元 evidence 目标一致；
- misconception 白名单由 `diagnostic_questions.json` 的 blocking misconceptions 派生，形成性问题数据与 verification misconception registry 存在耦合；
- `benchmark_case_ids` 目前是模板内的追踪标签，没有独立、机器可运行的 verification benchmark 数据集；
- 一个 template 的同一分数会复制给所有 `concept_ids`，没有 per-concept score。

P2b 只处理了新增题型所必需的 contract，没有重写 learner-state 或 recommendation。

## 3. P2b：Deterministic scorer foundation

**状态：implemented（`feature/p2b-deterministic-scorers`）**

### 目标

在保持 `single_choice_v1` 完全兼容的前提下，增加：

- `multiple_choice_v1`；
- `numeric_answer_v1`；
- `ordering_v1`。

`true_false` 和 `node_selection` 继续复用 `single_choice_v1`。`small_graph_path` 延后。

### 预计修改文件

- `src/introai_tutor/template_selection.py`
- `src/introai_tutor/verification_diagnostics.py`
- `src/introai_tutor/ui_state.py`（仅新增题型需要的稳定 widget state）
- `src/introai_tutor/ui_formatting.py`（仅学生答案/选项展示）
- `app.py`（只增加受控 widget，不改 workflow）
- `tests/test_template_selection.py`
- `tests/test_verification_diagnostics.py`
- `tests/test_ui_state.py`
- `tests/test_ui_formatting.py`
- `tests/test_streamlit_app.py`

必要时新增：

- `src/introai_tutor/verification_scorers.py`
- `tests/test_verification_scorers.py`

### 新增 templates

无生产模板。P2b 使用测试 fixtures 验证 scorer contract，避免 foundation 和课程内容审核混在一次提交。

### Scorer contract

- single choice：现有字符串 choice ID；
- multiple choice：严格的 choice-ID list/object，集合 exact match；
- numeric：学生输入字符串，规范化为有限数值；expected 为 value/tolerance；
- ordering：严格 choice-ID list/object，序列 exact match；
- 输出继续为 `score`、`passed`、`misconception_ids`、`feedback`；
- v1 不做部分分；
- history 增加由版本化 scorer 名称判别的 generic answer record，并为现有三个模板保留旧 choice 字段；
- 不把 expected answer 放入学生可见 question；
- 不改变 summary 中 concept observations、assistance 和 P5B 字段。

### 测试要求

- 每个 scorer 的 correct / incorrect / unknown ID / duplicate / missing / extra-field；
- numeric 的空白、负数、decimal、NaN、Infinity、bool、表达式字符串；
- ordering 的 duplicate、missing、extra、wrong order；
- template/scorer/question-type 不匹配严格拒绝；
- input template、answer、session 不被修改；
- 每次 submit 只调用一个 scorer 一次；
- current three templates 的 history、reveal、hint、P5B tests 不变；
- Streamlit 每种 answer widget 不串题、不串 attempt。

### 人工验收

- 单选题显示 choice text、提交 choice ID；
- 多选题重试后不保留旧选择；
- numeric 输入错误有学生可理解提示，不显示内部异常；
- ordering 在 rerun 后顺序稳定；
- reveal 不制造 observation。

### 明确禁止修改

- `diagnostic_questions.json` 及 41-case formative benchmark；
- mastery 公式、observation weight、recommendation；
- QuestionUnderstanding、retrieval、grounded QA；
- course chunks、knowledge graph。

### 依赖

- 无前置实施增量；
- P2c、P2d、P2e 依赖此增量。

## 4. P2c：Problem formulation 与通用 search

### P2c-a / P2c-b：模板验收基础与首批晋级

**状态：P2c first batch implemented / promoted**

已实现的 P2c-a 范围：

- 通用、数据驱动的 production template acceptance harness；
- `multiple_choice_v1` 的最小 Streamlit UI 与离线 AppTest；
- 固定的 `smoke` 测试标记；
- 三道 P2c 首批 production templates 及其自动 contract 测试；
- 候选题课程内容审核卡与生产晋级流程。

负责人已批准首批三道题；批准版本已加入
`data/diagnostic_templates.json`，状态为 `human_verified`。原 staging 批次已
清空，避免同一 template ID 同时存在于 active candidate bank 和 production bank。
三个新模板分别为 `search_problem_formulation`、
`state_space_and_operators` 和 `frontier_and_explored_set` 提供一条正式
verification capability。

首批晋级不代表整个 P2c 已完成。path cost 与 search node/state 两个规划模板仍待
后续增量；repeated-state handling 已在 P2d-c 作为单 concept 模板晋级。

### 目标

新增 6 个 reviewed templates，覆盖：

- 搜索问题组成；
- path cost；
- successor/operator；
- state 与 search-tree node；
- repeated-state/cycle handling；
- frontier 与 explored set。

### 新增 templates

1. `verify_search_problem_components_v1`
2. `verify_path_cost_sum_v1`
3. `verify_successor_operator_v1`
4. `verify_search_node_vs_state_v1`
5. `verify_graph_search_repeated_state_handling_v1`
6. `verify_frontier_explored_membership_v1`

### 使用 scorers

- `single_choice_v1`
- `multiple_choice_v1`
- `numeric_answer_v1`

### 预计修改文件

- `data/diagnostic_templates.json`
- 建议新增 `data/diagnostic_template_benchmark.json`
- `tests/test_template_selection.py`
- `tests/test_verification_diagnostics.py`
- `tests/test_diagnostic_handoff.py`
- `tests/test_app_services.py`
- `tests/test_streamlit_app.py`
- 若新增独立 benchmark runner：对应一个小模块和测试

如果需要新的 learner-state misconception IDs，应先做一个明确决策：

- **优先方案**：建立 reviewed verification misconception registry，由 formative 和 verification 共同引用；
- **保守方案**：首轮新模板的 `misconception_rules=[]`，错误只触发 hint，待 registry 独立增量完成后再记录。

不得为了通过当前 validator，把无关 blocking misconception 塞入开放题数据。

### 测试要求

- 每个模板至少 correct、reviewed misconception/错误、非法 answer；
- concept/page mapping 与矩阵一致；
- selector 对 problem/general-search topics 稳定；
- QA handoff 对这些 concepts 从 unavailable 变为 available；
- supporting topic 不抢占 primary diagnostic concept；
- 多选题 exact-match，不给部分分；
- multi-concept evidence 默认禁止，除非测试证明。

### 人工验收问题

- 学生能否区分问题定义和搜索算法？
- 同一 state 经不同路径出现时，题面是否仍有唯一答案？
- frontier/explored 的选项是否描述状态时点，而非依赖实现细节？
- path-cost 题是否避免把 prerequisite Dijkstra 当作 AI 主课件定义？

### 明确禁止修改

- P5B、recommendation、formative matcher/semantic；
- v1.1 concept 数据；
- PDF/chunks。

### 依赖

- P2b。

## 5. P2d：DFS、DLS/IDDFS 与搜索性质

### P2d-a / P2d-b / P2d-c：第二批候选题与首批晋级

**状态：P2d first batch implemented / promoted**

本批次先建立并修订 candidate staging、课程审核卡和自动 contract 验收；负责人
最终批准后，P2d-c 已将以下三题晋级 production：

1. `verify_graph_search_repeated_state_handling_v1`
2. `verify_dfs_frontier_choice_v1`
3. `verify_iddfs_depth_limit_schedule_v1`

三题均采用现有 `single_choice_v1`，每题只映射一个主要 mastery concept。IDDFS
题用题面明确的下一轮调度验证 limit 增长和从根重启，没有引入 ordering UI。
三题现在位于 `data/diagnostic_templates.json`，状态为 `human_verified`；原 P2d
active candidate staging 已清空。

P2d-b 已根据独立课程审核修订 repeated-state 题的区分力，并把 Lec2 p.27 的
graph-search 伪代码以及 IDDFS 文字页/动画页的起始 limit 差异写入证据记录。
独立审核之后，负责人最终决定为三题全部 `approve`。本次晋级不表示整个 P2d 或
Search Algorithms v1 已完成。

### 目标

新增 4 个 reviewed templates，补齐无信息搜索的第二条主线和跨算法性质：

1. `verify_dfs_frontier_choice_v1`
2. `verify_dfs_infinite_branch_risk_v1`
3. `verify_iddfs_depth_limit_schedule_v1`
4. `verify_search_properties_matrix_v1`

同时不修改现有 BFS/UCS 三题，并把 DLS 明确作为 IDDFS 能力切片而非新 concept。

### 使用 scorers

- `single_choice_v1`
- `ordering_v1`
- `multiple_choice_v1`

### 预计修改文件

- `data/diagnostic_templates.json`
- `data/diagnostic_template_benchmark.json`
- `tests/test_template_selection.py`
- `tests/test_verification_diagnostics.py`
- `tests/test_diagnostic_handoff.py`
- `tests/test_streamlit_app.py`

### 测试要求

- DFS next-node tie 在题面中消除；
- 无限深/循环场景的 assumptions 明确；
- IDDFS ordering answer 唯一，cutoff 与 failure 不混淆；
- completeness / optimality / complexity 的每项结论都带适用条件；
- BFS equal-cost 现有 misconception 不回归；
- 不把 DFS memory 优势误判为 completeness/optimality；
- 新模板完成后 evidence 只写对应 concept。

### 人工验收问题

- 学生能否看出 IDDFS 每一轮重新从根开始？
- “complete/optimal”是否明确是条件性陈述？
- 是否用过于复杂的符号让题目测成阅读能力而不是搜索概念？

### 明确禁止修改

- 不新增 `depth_limited_search` concept；
- 不改知识图谱 prerequisite；
- 不改 mastery 或 recommendation。

### 依赖

- P2b；建议在 P2c 后，以复用 benchmark/贡献格式。

## 6. P2e：Informed search、Greedy、A* 与 heuristic properties

### P2e-a：首批有信息搜索候选题

**状态：P2e-b implemented / promoted。**

负责人已批准四道候选；它们现位于 `data/diagnostic_templates.json`，均为
`human_verified`。原 `data/candidate_templates/search_algorithms_p2e_candidates.json`
顶层状态为 `promoted_to_production`，active candidates 为 0：

1. `verify_informed_search_g_h_roles_v1`（`multiple_choice_v1`）；
2. `verify_greedy_min_h_choice_v1`（单选，正确项 B）；
3. `verify_astar_min_f_choice_v1`（单选，正确项 C）；
4. `verify_admissibility_no_overestimate_v1`（单选，正确项 D）。

四题均有 `direct` course-core source reference、production acceptance case 和
工程 contract 测试；详见 `docs/search_algorithms_p2e_candidate_review.md`。本批没有
修改生产 selector、verification service、mastery 或 recommendation。A* 仅在
直接匹配 `a_star_search` 且 intent 合法时从 safe abstention 变为 available；其他
intent、unknown concept 和 supporting-only topic 仍安全 unavailable。

本次 promotion 不表示整个 P2e 或 Search Algorithms v1 完成；其余四项 P2e
计划能力仍须独立候选、审核和晋级。

### 目标

新增 8 个 reviewed templates：

1. `verify_ucs_frontier_update_v1`
2. `verify_informed_search_g_h_roles_v1`
3. `verify_greedy_min_h_choice_v1`
4. `verify_greedy_suboptimality_v1`
5. `verify_astar_f_value_v1`
6. `verify_astar_min_f_choice_v1`
7. `verify_admissibility_no_overestimate_v1`
8. `verify_consistency_edge_check_v1`

完成后模板总数达到 21。

### 使用 scorers

- `single_choice_v1`
- `multiple_choice_v1`
- `numeric_answer_v1`

### 预计修改文件

- candidate 阶段：`data/candidate_templates/search_algorithms_p2e_candidates.json`、
  `tests/test_template_acceptance.py`、候选审核卡与矩阵/路线文档；
- 仅在负责人批准后的 promotion 阶段，才考虑
  `data/diagnostic_templates.json`、`tests/test_template_selection.py`、
  `tests/test_verification_diagnostics.py`、`tests/test_diagnostic_handoff.py`、
  `tests/test_app_services.py` 和 `tests/test_streamlit_app.py`。

### 测试要求

- Greedy、UCS、A* 在相同 g/h 数据上的选择标准分别锁定；
- A* numeric 和 node-selection 两题不能互相替代；
- admissibility 负例必须包含真正 overestimate；
- consistency 按一条边的不等式判断，不能只测 h 非负；
- tree-search / graph-search 的 optimality 文案与 Lec3 pp.37–39 一致；
- heuristic dominance 先作为 explanation/扩展测试，不伪装成独立 concept；
- A* QA handoff 从安全 abstain 转为 available 只发生在模板 human review 完成后；
- unsupported v1.1 concepts 仍不可产生虚假模板。

### 人工验收问题

- 同一组节点下 Greedy、UCS、A* 是否各有唯一选择？
- g/h/f 的数字是否足够小，避免算术错误主导测量？
- admissibility 与 consistency 的解释是否清楚区分？
- 是否错误宣称 admissibility 对任意 graph-search A* 已经足够？

### 明确禁止修改

- 不恢复 semantic 对 mastery 的权限；
- 不修改 grounded answer/retrieval；
- 不加入 local search、Minimax、MCTS/UCB；
- 不实现 small graph path scorer。

### 依赖

- P2b；建议在 P2c/P2d 后实施，以便复用稳定贡献流程。

## 7. P2f：完整回归、用户验收与贡献规范

### P2f：七道 owner-approved candidate promotion

**状态：已完成。** `search_algorithms_p2f_a` 的七道题已按既有 promotion 流程进入 production，
production reviewed templates 从 13 增至 20，candidate staging 为 promoted/empty，active
candidate 为 0。`verify_ucs_frontier_update_v1` 继续 blocked；没有创建证据不足的第 21 道题。

本次只迁移 reviewed data、验收契约、报告和文档；没有修改 selector、verification service、
mastery、recommendation、P5B、evidence gate、assistance policy 或 production Python。IDDFS
的 p.53 context-only / p.58 primary-evidence 链继续由 source-role gate fail closed。

### 目标

- 冻结 21-template v1 bank；
- 建立可运行的 verification benchmark；
- 完成 coverage report、端到端测试和人工课程审核；
- 更新 README/architecture/evaluation 文档；
- 形成组员可执行的最小交付格式。

### 预计修改文件

- `data/diagnostic_template_benchmark.json`
- verification benchmark runner 与 tests（若前序未创建）
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/EVALUATION.md`
- 本次三个 v1 规划文档的 final status
- 相关全链测试

### 测试要求

- 21 templates 全部能 loader/selector/start/submit/complete；
- 按 concept 和 scorer 输出 exact-match 指标；
- 每题至少一正一负，misconception 有独立负例；
- assistance/reveal/evidence/P5B/recommendation 全链；
- 快速诊断、QA handoff 和 optional formative 都不回归；
- 未支持的 v1.1 topic 继续返回 reviewed-template unavailable；
- 41-case formative benchmark 独立通过，不计入 verification accuracy；
- 所有测试离线，不读 `.env`、不访问网络。

### 人工验收

- 课程负责人逐题签署 source page、correct answer、misconception、hint、explanation；
- 从空 learner state 分别走一次全对、全错、hint 后对、reveal；
- 检查 student UI 不泄露 expected answer/internal IDs；
- 检查开发者 trace 能追溯 template、answer、assistance、observation、selected signal；
- 检查 13 个 v1 concepts 的 material/template/capability coverage 表。

### 明确禁止修改

- 不在 release hardening 中临时扩大 v1.1；
- 不为提高指标改 benchmark 真值；
- 不顺带改变 mastery/recommendation；
- 不使用 live LLM 作为 release gate。

### 依赖

- P2b–P2e 完成。

## 8. P0 / P1 template slices

### P0：先形成完整教学主线

保留原有 3 个模板，并优先新增 11 个；其中以下 3 个已在 P2c-b 晋级生产：

- `verify_search_problem_components_v1`
- `verify_successor_operator_v1`
- `verify_graph_search_repeated_state_handling_v1`
- `verify_frontier_explored_membership_v1`
- `verify_dfs_frontier_choice_v1`
- `verify_iddfs_depth_limit_schedule_v1`
- `verify_informed_search_g_h_roles_v1`
- `verify_greedy_min_h_choice_v1`
- `verify_astar_f_value_v1`
- `verify_astar_min_f_choice_v1`
- `verify_admissibility_no_overestimate_v1`

这里有 11 个 proposed P0 条目；实施时 P2c/P2d/P2e 仍按有限增量提交，不一次性合并。它们优先解决“课程问答已经支持、但完全没有 verification”的主线断点。

### P1：补性质、比较与第二能力

新增 7 个：

- `verify_path_cost_sum_v1`
- `verify_search_node_vs_state_v1`
- `verify_dfs_infinite_branch_risk_v1`
- `verify_search_properties_matrix_v1`
- `verify_ucs_frontier_update_v1`
- `verify_greedy_suboptimality_v1`
- `verify_consistency_edge_check_v1`

P1 重点降低“一个 concept 只有一道表面题”的风险，并覆盖复杂度、风险和 graph-search 条件。

## 9. 团队协作边界

### 9.1 用户本人继续负责

- scorer contract 与 versioning；
- template loader、selector 和 service architecture；
- evidence gate、P5B 与 learner state；
- session state、rerun、assistance/reveal；
- recommendation；
- 最终集成、release branch 和发布决定。

### 9.2 未来组员可负责

- concept 与现有 chunk/page 的映射复核；
- reviewed template 的 prompt、choices 和 expected answer；
- misconception 候选与唯一性论证；
- hint 与 explanation；
- verification benchmark 正负例；
- 页面人工验收和课程内容勘误。

组员不得自行：

- 新增 concept ID 或 scorer；
- 改 evidence/mastery/recommendation；
- 让 LLM 生成或评分 verification；
- 放宽 template validator；
- 修改 benchmark 真值以适配实现。

### 9.3 最小交付包

每个 template slice 的 PR/交付目录中至少提供一份短表：

| 字段 | 必填内容 |
| --- | --- |
| Template ID | 稳定、版本化 ID |
| Concept | 主要 concept ID；多 concept 需单独论证 |
| Source | chunk ID、文件名、物理页码 |
| Learning objective | 一句话 |
| Verification claim | 本题能证明什么、不能证明什么 |
| Scorer | 已支持的版本化 scorer |
| Correct answer | 唯一答案与理由 |
| Negative cases | 至少一个典型错误、一个边界/非法输入 |
| Misconception | ID 或“仅 hint、不记录”的理由 |
| Support | reviewed hint、explanation |
| Evidence | 是否 eligible、辅助后如何处理 |
| Manual check | 审核人、日期、结论 |

### 9.4 检查节奏

- **每周轻检查（15–30 分钟）**：核对 source、唯一答案、schema、至少一正一负；不要求集成发布。
- **每两周正式验收**：运行全量测试与 benchmark，人工走 UI，检查 learner-state trace，决定是否从 draft 升为 `human_verified`。
- 不引入复杂项目管理系统；使用上述交付表、普通 issue/PR checklist 和现有测试即可。

## 10. 风险与开放决策

1. **Misconception registry 耦合**：当前 verification 可用 misconception IDs 来自 formative question data。P2c 前需决定独立 registry 还是保守空 mapping。
2. **多 concept 同分**：当前一个 template 的 score 会复制到所有 mapped concepts。新增模板默认单 concept。
3. **Answer/history compatibility**：multiple choice 和 ordering 使用由 scorer 名称判别的结构化 answer；旧 single-choice session/tests 必须保持兼容。
4. **模板总量与诊断长度**：21 是 bank 总量，不表示一次 session 全部出题。handoff 默认最多 3 题；后续 selection policy 应按目标 concept 取最小集合。
5. **Binary evidence**：v1 新 scorer 保持 0/1，简单可审计，但不表达部分能力。不要在 scorer foundation 中加入任意部分分。
6. **Recommendation 顺序**：扩大 evidence 后，现有“第一个弱 concept + prerequisite 回溯”可能频繁推荐早期 concept。先收集真实 trace，再单独评审，不与 template 扩展合并。
7. **内容审核容量**：21 道题的瓶颈是课程审核，不是编码。先完成 P0 主线再补 P1，不用数量替代质量。
8. **A* graph-search 条件**：admissibility/consistency 的题面必须明确 tree vs graph assumptions，避免教材表述压缩成错误通则。

## 11. 推荐的下一增量

## P2g verification hardening (implemented; production content unchanged)

P2g adds offline quality-gate tooling, derived benchmark inventory, exhaustive
controlled-answer regression, source/capability reporting, review-packet
generation, candidate lint, and CI/local parity documentation. It does not
change the reviewed production bank, selection semantics, evidence gate,
mastery, recommendation, or candidate status.

**已完成：** P2b deterministic scorer foundation，以及 P2c 的前 3 个低风险模板晋级：

1. `verify_search_problem_components_v1`
2. `verify_successor_operator_v1`
3. `verify_frontier_explored_membership_v1`

这三个模板已证明架构可以从 BFS/UCS 扩展到“问题表示与通用搜索”，同时没有引入复杂图路径判定或改变 mastery 公式。下一增量应回到矩阵中尚未覆盖的 P0 条目，并继续采用 candidate review → human approval → production promotion 的流程。
