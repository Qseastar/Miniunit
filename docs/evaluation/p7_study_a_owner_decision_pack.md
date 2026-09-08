# P7 Study A 负责人决策包

> 本文件是未来 Study A 的负责人决策材料，不是正式真人研究方案、知情说明、招募文案、参与者数据结构或真人研究授权。本文只汇总现有仓库事实、待决方案与决策依赖；`CODEX_RECOMMENDATION` 仅供负责人参考，绝不等于 `OWNER_DECISION`。

## 0. 当前边界与使用方式

当前正式状态不可改变：

```text
P7_READINESS_LEVEL = LEVEL_2
HUMAN_STUDY_AUTHORIZED = NO
CHECK_BEFORE_REAL_HUMAN_STUDY_RESOLVED = NO
READY_FOR_PARTICIPANT_RECRUITMENT = NO
READY_FOR_REAL_DATA_COLLECTION = NO
READY_FOR_STUDY_A_EXECUTION = NO
```

`LEVEL_2` 仅指 11 道研究专用外部测评题已完成负责人内容审核。它不表示伦理、备案、导师许可、参与者保护或真人研究已经完成。外部表现仅可称为“独立的课程依据表现标准”，不得称为真实掌握度、真实标准、校准、学习增益、成绩预测或推荐有效性。

项目级 `LEVEL_2` 与题库文件中的 `assessment_status=pending_owner_review`、逐题 `human_review_status=pending_owner_review` 不矛盾：前者是项目级负责人 readiness 决定；后者保留研究专用候选题库的生命周期字段。不得把这些候选题生命周期字段改写为生产状态，也不得以其推翻当前 `LEVEL_2` 记录。

Study A 的唯一核心问题保持为：

> 冻结的掌握度估计与独立的课程依据表现标准之间的排序／单调一致性。

Study B 的推荐干预与 Study A 分离。本文件不选择 P0/P2/P3 的胜出方案，不冻结任何真人研究设计，也不改变生产实现。

## 1. 已读取的研究基线

本决策包交叉核对以下已存在的材料：

- `data/evaluation/p7_readiness_status.json`：项目级 `LEVEL_2`、11 道启用题、6 个选定知识点与 `HUMAN_STUDY_AUTHORIZED = NO`；
- `data/evaluation/p7_external_assessment_candidates.json`：研究专用题库、题目独立性边界与候选题生命周期；
- `docs/evaluation/p6_learner_state_measurement_audit.md`：当前生产证据、帮助、重复作答与 P5B 行为；
- `docs/evaluation/p6b_aggregation_policy_comparison.md`：P0/P1/P2/P3 的稳定性—响应性取舍；
- `docs/evaluation/p7_human_grounded_evaluation_protocol.md`：Study A 的研究边界、冻结顺序、外部标准和未来分析候选；
- `docs/evaluation/p7_readiness_promotion_audit.md` 与 `docs/evaluation/p7a` 至 `p7d`：负责人审核沿革；
- `docs/evaluation/p7_pre_human_study_checkpoint_audit.md`：真人研究前的保护、治理、导师和机构缺口；
- `docs/evaluation/p7_study_a_synthetic_analysis_dryrun.md`、`tools/run_p7_study_a_synthetic_analysis.py` 与其固定样本：纯合成分析管线。

### 1.1 “5 个 blocked concepts”的字段语义

候选题验证器输出的 `external_criterion_blocked_concept_count = 5` **不是**“当前 11 道启用题中有 5 个被阻断”，也不是 Local Search 有 5 个被阻断位置。它来自 26 个生产知识点的能力映射：`adversarial_search`、`game_state_evaluation`、`monte_carlo_search`、`exploration_exploitation`、`llm_search_and_test_time_scaling` 目前没有直接主要生产证据机会，因而被标为 `DO_NOT_USE`／`EXTERNAL_CRITERION_BLOCKED`，不适合用于本轮估计器一致性研究。

这与本轮外部题库的 6 个已选知识点及其 11 道负责人审核题是两个不同的统计口径。Local Search 的已接受不对称则是另一个单独事实：在已选题库内仅有 1 道题，其第二表征位置为 `LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE`。

## 2. 已决定 / 未决定总表

| 事项 | 当前状态 | 已确定事实或待处理原因 | 最终权限 |
| --- | --- | --- | --- |
| Study A 核心问题 | `ALREADY_DECIDED` | 仅检验冻结估计与独立课程标准的排序／单调一致性。 | 负责人保持边界 |
| Study B 分离 | `ALREADY_DECIDED` | 推荐干预不属于 Study A。 | 负责人 |
| 外部题库 | `ALREADY_DECIDED` | 启用题=11、选定知识点=6、研究专用。 | 负责人已作 Level 2 决定 |
| Local Search 不对称 | `ALREADY_DECIDED` | 仅 1 题；第二表征位置为 `LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE`。 | 负责人已决定 |
| Minimax two-level 角色 | `ALREADY_DECIDED` | `TRANSFER_EXPLORATORY_ONLY`，不得作为主要即时标准或严格平行题。 | 负责人已决定 |
| 严格即时／延迟平行题组 | `ALREADY_DECIDED` | 当前不存在；不得伪称存在。 | 事实记录 |
| P0 生产基线 | `ALREADY_DECIDED` | `alpha=0.35`，本轮不改生产实现。 | 生产基线 |
| P1 角色 | `ALREADY_DECIDED` | 仅为数学参考。 | P6b 已定边界 |
| P2/P3 数学定义 | `ALREADY_DECIDED` | 研究比较基线，不自动进入生产实现。 | P6b 已定边界 |
| Study A 主要估计器角色 | `OWNER_DECISION_PENDING` | P0 主分析、三者并列或仅 P0 都尚未冻结。 | 负责人，建议导师审阅 |
| 实际外部测评子集 | `OWNER_DECISION_PENDING` | 已有 11 题，但真人施测子集／组成未冻结。 | 负责人，建议导师审阅 |
| 主要即时标准组成 | `OWNER_DECISION_PENDING` | 合成组成只是演练，不是正式赋值。 | 负责人 |
| 分析单位 | `OWNER_DECISION_PENDING` | 参与者 × 知识点是当前协议起点；是否主用分层／汇总／学习者层级未冻结。 | 负责人，建议导师审阅 |
| 汇总分析角色 | `OWNER_DECISION_PENDING` | 不可默认独立同质或主要分析。 | 负责人，建议导师审阅 |
| 主要排序统计量 | `OWNER_DECISION_PENDING` | Spearman、Kendall tau-b、描述性排序的主次未冻结。 | 负责人，建议导师审阅 |
| missing 的核心语义 | `ALREADY_DECIDED` | `missing = null + missing_reason`，绝不写成 0。 | 已定边界 |
| 缺失值词表／分析 | `OWNER_DECISION_PENDING` | 合成词表不是正式真人研究词表。 | 负责人，部分需外部确认 |
| 题目／知识点顺序 | `OWNER_DECISION_PENDING` | 固定、预先随机或分块顺序尚未决定。 | 负责人，建议导师审阅 |
| 部分施测 | `OWNER_DECISION_PENDING` | 全题、平衡不完整或知识点特定方案未冻结。 | 负责人，建议导师审阅 |
| 重复作答／复测 | `OWNER_DECISION_PENDING` | 严格延迟平行题尚无；不得把立即重做当独立结果。 | 负责人，建议导师审阅 |
| 参与者范围 | `ADVISOR_CONFIRMATION_REQUIRED` | 可邀请人群尚未定义，存在关系压力风险。 | 郭老师与负责人 |
| 招募 | `ADVISOR_CONFIRMATION_REQUIRED` | 招募渠道和关系边界未定义，存在关系压力风险。 | 郭老师与负责人 |
| 知情说明 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 仓库无机构正式要求，也无最终参与者材料。 | 书院／学校／正式机构，郭老师协助 |
| 研究目的披露 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 参与者材料与制度要求未确认。 | 书院／学校／正式机构，郭老师协助 |
| 退出 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 未确认退出后数据处理要求。 | 书院／学校／正式机构，郭老师协助 |
| 补偿 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 未设计，可能涉及不当影响。 | 负责人，机构要求优先 |
| 真人研究数据结构 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 最小字段、链接、保存与访问尚未批准。 | 负责人 + 机构要求 |
| 身份链接 | `OWNER_DECISION_PENDING` | 不得使用 learner UUID、学号、邮箱；是否需要安全研究链接尚未定。 | 负责人，机构要求优先 |
| 保存期限 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 未规定期限与备份。 | 书院／学校／正式机构 |
| 删除 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 未规定删除时点、范围与例外。 | 书院／学校／正式机构 |
| 访问控制 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 未规定数据权限与访问者范围。 | 书院／学校／正式机构 |
| 发表／展示使用 | `ADVISOR_CONFIRMATION_REQUIRED` | 未来报告、论文、预印本要求未确认。 | 郭老师 + 机构要求 |
| 分析冻结 | `OWNER_DECISION_PENDING` | 当前只是候选分析。 | 负责人，建议导师审阅 |
| 版本冻结 | `OWNER_DECISION_PENDING` | 尚未固定生产实现、测评工具、脚本与流程。 | 负责人 |
| 真人研究授权 | `INSTITUTIONAL_VERIFICATION_REQUIRED` | 当前明确为 `NO`。 | 负责人、郭老师、书院／学校流程 |

## 3. Owner Decision 1：external assessment composition

### 3.1 当前 11 题盘点

| Concept ID | Active item IDs | 当前 item role | Owner disposition | potential primary immediate criterion | 已知不对称 / 边界 | strict parallel pair |
| --- | --- | --- | --- | --- | --- | --- |
| `breadth_first_search` | `p7_ext_bfs_depth_claim_a`; `p7_ext_bfs_queue_trace_b` | 两题均 `INDEPENDENT_CAPABILITY_SAMPLE`；可作为不同 micro-capability 的 immediate/complementary 输入候选。 | `OWNER_APPROVE`; `OWNER_APPROVE_PRESERVE` | 可以，但正式组成尚未冻结。 | 两题不是 strict delayed pair。 | 无 |
| `uniform_cost_search` | `p7_ext_ucs_cost_accumulation_a`; `p7_ext_ucs_positive_cost_bound_d` | 前者 independent capability，后者 complementary capability。 | `OWNER_APPROVE_PRESERVE`; `OWNER_APPROVE` | 可以，但两题粒度不同。 | 不应把 complementary 自动等同 parallel。 | 无 |
| `a_star_search` | `p7_ext_astar_zero_heuristic_c`; `p7_ext_astar_component_change_b` | 两题均 complementary capability。 | `OWNER_APPROVE`; `OWNER_APPROVE_PRESERVE` | 可以，需明确是在同一 concept 的两个不同能力切片上合成。 | 非 strict pair。 | 无 |
| `local_search` | `p7_ext_local_search_neighbor_a` | `INDEPENDENT_CAPABILITY_SAMPLE`。 | `OWNER_APPROVE` | 可以，且只能如实按 `correct / 1`。 | 第二 representation slot 已被独立性阻断。 | 无 |
| `minimax_search` | `p7_ext_minimax_min_node_a`; `p7_ext_minimax_two_level_b` | 前者 complementary；后者 `TRANSFER_EXPLORATORY_ONLY`。 | `OWNER_APPROVE_PRESERVE`; `OWNER_APPROVE_TRANSFER_EXPLORATORY_ONLY` | 仅前者可进入 potential primary immediate。 | transfer 不可混入 primary。 | 无 |
| `monte_carlo_tree_search` | `p7_ext_mcts_backpropagation_a`; `p7_ext_mcts_expand_untried_child_b` | complementary + independent capability。 | `OWNER_APPROVE`; `OWNER_APPROVE_PRESERVE` | 可以，但正式组成尚未冻结。 | 不等同 delayed parallel。 | 无 |

### 3.2 可供负责人比较的组成方案

| 方案 | 组成 | 优点 | 风险 / 代价 | 仓库兼容性 | 是否新增代码 | 对研究主张的影响 |
| --- | --- | --- | --- | --- | --- | --- |
| A：全部诚实 primary 输入 | 使用除 `p7_ext_minimax_two_level_b` 外的 10 题；Local Search `correct / 1`，其余按 concept 内已选 item 的 `correct / total`。 | 课程覆盖最多；最大化已审核工具利用；与 synthetic dry-run 接近。 | concept granularity 不同；item 数量不均；pooled 比较易被误读。 | 高。 | 不一定；需 freeze manifest/analysis config。 | 仅可报告不等粒度的 course-grounded criterion。 |
| B：保守、结构更一致 subset | 每 concept 一题；Minimax 仅 `min_node_a`；Local Search 保持单题。 | participant burden 较低；每 concept 表面上更一致；解释较简单。 | 丢失已审核信息；一题测量更粗；必须由 owner 明确选择每 concept 哪一题。 | 高，但当前没有唯一推荐 subset。 | 不一定。 | 更适合窄的 feasibility 描述，不可声称更可靠。 |
| C：不作六 concept pooled primary | 保留每个 concept-specific criterion 与描述；不预设跨六 concept 汇总。 | 最诚实地面对不等题数和能力切片；降低伪独立/伪同质风险。 | 单 concept 样本可能很小；总结更复杂；不能给出单一全局数字。 | 高。 | 无或极小 reporting config。 | 重点变为 concept-stratified feasibility，不是总体系数。 |

`CODEX_RECOMMENDATION`：若导师和机构允许继续，优先把方案 C 作为 primary reporting 架构，再决定是否用方案 A 的 complete records 生成明确标为 exploratory 的 pooled 描述。原因是它不把 `correct/1` 与 `correct/2`、不同 capability slice 和 participant 内重复观测伪装为同质独立量。该建议不是 `OWNER_DECISION`。

## 4. Owner Decision 2：estimator roles

| 方案 | P0/P2/P3 角色 | 优点 | 风险 / 代价 | 与 P6/P6b 一致性 | 对 production 的影响 |
| --- | --- | --- | --- | --- | --- |
| A：P0 primary | P0 是 primary estimator；P2/P3 是 sensitivity / comparative secondary analyses；P1 仍为 mathematical reference。 | 对齐当前 production；主问题最容易向系统使用边界解释。 | 容易把 P2/P3 结果当事后竞争；需要预先写清 sensitivity 不选 winner。 | 高。 | 无；不能由结果倒推改 production。 |
| B：三者并列 | P0/P2/P3 都是 candidate estimators；不设预先 winner。 | 直接反映 P6b 的稳定性—响应性取舍。 | multiplicity 与 cherry-picking 风险最高；容易被误读为 policy competition。 | 高。 | 无；未来任何 production 决定需独立研究。 |
| C：仅 P0 主分析 | 只分析 production P0；P2/P3 仅作为完全 exploratory 附录或不报告。 | 研究范围最窄；解释简单。 | 少了已实现的敏感性信息；不能展示 estimator assumptions 对结果的影响。 | 可接受。 | 无。 |

P6b 已经说明：P0/P2/P3 代表不同稳定性—响应性取舍，不存在当前 winner。无论选择何方案，必须预先列明每个 estimator 的 primary / secondary / exploratory 角色、所有待报告结果和禁止事后参数调优的规则。

`CODEX_RECOMMENDATION`：方案 A 是最小且最贴近当前产品的问题表述；P2/P3 应作为预先指定的 sensitivity analyses，而非胜者竞赛。最终由 human owner 决定，并建议郭老师审阅。

## 5. Owner Decision 3：analysis unit 与 pooled-analysis 风险

当前协议的起点是 participant × concept，因为 mastery estimate 是 concept-specific；同一 participant 的多个 concept 不是天然独立。external criterion 又具有不一致粒度：有些 concept 是 `correct/2`，Local Search 是 `correct/1`，Minimax primary 可能为 `correct/1`。

| 方案 | 分析单位 / 方式 | 独立性与可比性 | 优点 | 风险 / 限制 | 是否需导师 / 统计意见 |
| --- | --- | --- | --- | --- | --- |
| A：concept-stratified | 每 concept 单独描述 valid N、missing、estimate 与 criterion ordering。 | 避免直接把不同 concept/题数混为同一尺度；participant 内重复仍需透明报告。 | 最贴合不同 criterion granularity；解释直接。 | 每 concept 小 N、ties 多，可能没有可用相关系数。 | 建议郭老师确认。 |
| B：pooled descriptive | 合并 participant × concept pairs，仅作探索性表格或可视化。 | 不能默认 pair 独立、同质或等权。 | 便于总览、发现明显数据质量问题。 | 可能被 concept difficulty、题数和 repeated measures 主导；不得默认作 primary inference。 | 是。 |
| C：learner-level aggregation | 先在每 learner 内汇总 selected concepts，再分析 learner-level relation。 | 降低 participant 内重复，但引入跨 concept 权重与缺失聚合决定。 | 每 participant 一个单位，直观。 | 必须决定 Local Search `correct/1` 的权重、概念缺失处理和 aggregation 规则；当前仓库未支持唯一规则。 | 是。 |
| D：仅描述性对照 | 不报告单一 correlation；列出 concept-stratified ordering、tie、missing 与 policy estimates。 | 不依赖强独立性假设。 | 对 feasibility 阶段最稳健、可审计。 | 不能回答强关联问题；仍需预先定义表格。 | 建议郭老师确认。 |

Synthetic dry-run 的 pooled rho 只是工具能力示范，绝不是默认 primary outcome。`n>=3` 仅是工具拒绝伪相关的安全门槛，不是样本量建议、可行性阈值或 power analysis。

`CODEX_RECOMMENDATION`：优先 A + D，必要时把 B 标为 exploratory visualization；C 只有在负责人明确认可概念权重和缺失聚合后才可采用。该建议不替代导师或统计咨询。

## 6. Owner Decision 4：Spearman、Kendall tau-b 与 descriptive ordering

| 方法 | 回答的问题 | tie 影响 | 小样本边界 | 合适角色 |
| --- | --- | --- | --- | --- |
| Spearman rho | 两个排序/单调趋势是否同向。 | 工具使用 average ranks；大量 ties 会降低可辨识变化。 | 少量 pair 数值很不稳定；不能把 n>=3 解释为充分样本。 | 候选 primary descriptive statistic 或预先指定 sensitivity。 |
| Kendall tau-b | 成对排序的一致/不一致方向。 | 显式校正 tie；报告 concordant/discordant/tie 更直观。 | pair 数少时很粗糙；常量值时不可用。 | 候选 primary descriptive statistic 或与 Spearman 并列 sensitivity。 |
| descriptive ordering | 直接列出 concordant、discordant、mastery tie、external tie、joint tie。 | 不隐藏 ties。 | 无法替代强统计结论，但最容易审计。 | 所有方案都应保留。 |

可选组合：

- 方案 A：预先指定一种为 primary descriptive rank statistic，另一种为 sensitivity，并永久附 descriptive ordering；
- 方案 B：Spearman 与 Kendall tau-b 并列 descriptive，不对差异做 winner 声明；
- 方案 C：只用 descriptive ordering，延后任何 correlation 解释。

`CODEX_RECOMMENDATION`：若必须选一项，优先明确 Kendall tau-b 的 tie-aware 角色，并把 Spearman 与完整 ordering 一并报告；但这仍需 owner freeze 与导师确认。不得做 p-value fishing、多重比较优化、样本量推断或未经批准的 power analysis。

## 7. Owner Decision 5：missing-data policy

已确定的硬边界：

```text
missing = null + missing_reason
missing != 0
```

当前 synthetic-only vocabulary 仅含 `synthetic_external_not_administered`；它绝不是正式真人研究 vocabulary。现有 P7 synthetic runner 还演练过 `participant_stopped_before_external_assessment`、`delayed_session_missing` 与 `concept_assessment_not_administered`，但它们也尚未构成完整已批准清单。

| 待决定的类别 | 可能需要的区分 | 当前处理原则 | 影响参与者权益 / 外部流程 |
| --- | --- | --- | --- |
| participant non-response | 未开始、跳过、未完成、延迟未返场。 | 保留 `null + reason`，不改为 incorrect。 | 是；退出与不参与权需导师/机构确认。 |
| instrument not administered | 预先未分配、临时取消、概念不在 selected subset。 | 不产生该 criterion pair；原始数量透明报告。 | 一般由 owner freeze。 |
| technical failure | 客户端、服务、导出或题目显示失败。 | fail closed；不得补写分数。 | 需 procedure 与 complaint 处理规则。 |
| policy estimate unavailable | 无 frozen eligible evidence、冻结失败或版本不匹配。 | estimate=`null`，不得伪造 0 或借用其他 policy。 | 可由 owner 决定 technical handling。 |
| withdrawal | 参与者撤回前、过程中或外部测评前后。 | 不可自行决定已收集数据如何处理。 | 是；必须等待机构/导师与 owner 的正式规则。 |
| protocol deviation / other | 题序错误、重复作答、非预定支持、未知原因。 | fail closed，记录受控原因并从对应 primary analysis 排除，不能事后重分类。 | 可能需要导师/机构确认。 |

需要 owner freeze：受控 reason vocabulary、每类的纳入/排除方式、partial concept result 的规则、原始 missing summary 的输出方式。任何涉及退出、删除、保留与联系的规则，都不能只由代码决定。

## 8. Owner Decision 6：item administration

以下均只是待比较方案，不能直接变成可执行真人 session：

| 决策 | 可选方案 | 优点 | 风险 / 代价 | 当前兼容性 |
| --- | --- | --- | --- | --- |
| instrument coverage | 全部 primary items；每 concept 单题 subset；平衡不完整 block。 | 前者信息多；后两者负担低。 | 全部题目增加疲劳；subset 增加 assignment/可比性决定。 | 11 题 bank 可支持，actual subset 未冻结。 |
| participant item set | 所有人同一套；预先固定 block；预先分配不同 block。 | 同一套最易比较；block 可降负担。 | block 需要处理缺失/不完全比较，不能临时换题。 | 需要 owner 设计 freeze。 |
| item / concept order | 全固定；预先决定的顺序轮换；预先随机但保留 assignment。 | 固定最易复现；轮换/随机可平衡顺序。 | 后两者需记录 assignment 与版本，不能临时决定。 | 当前无正式 session allocator。 |
| immediate timing | formal evidence freeze 后立即；预先定义的短窗口。 | 贴近 current primary alignment。 | timing 会影响短期记忆与解释。 | 需 owner/advisor freeze。 |
| transfer item | 不施测；单独 exploratory；未来另行设计。 | 不施测最窄；单独施测可保留探索价值。 | 当前仅 Minimax two-level，非 strict parallel，不可改变 primary。 | 只能保留 exploratory。 |
| repeated answer | 不允许 primary immediate 重复；仅按已批准的独立 form/retest policy。 | 防止记忆答案污染。 | 当前没有 strict delayed form。 | 不得把 immediate replay 当 independent evidence。 |

`CODEX_RECOMMENDATION`：先在 human owner 决策层比较“全 primary items”与“每 concept 单题的预先固定 subset”，而不在此刻选择；无论选择哪种，Minimax transfer 都应独立于 primary，Local Search 的单题性质应透明保留。

## 9. Owner Decision 7：version freeze 与可重复性

第一位真人参与者进入前，至少应冻结以下对象及其关系：

| 要冻结的对象 | 为什么必须冻结 | 可选证据方式 |
| --- | --- | --- |
| production commit / release | 中途 scorer、evidence 或 mastery 变化会改变 frozen estimate 的含义。 | commit hash + read-only snapshot。 |
| production diagnostic registry | template 数量、答题规则、exposure/repeat 行为变化会造成 cohort 不可比。 | manifest + checksum。 |
| mastery policy implementation | P0/P2/P3 参数或实现变化会改变 estimator。 | commit hash + policy parameter record。 |
| external item IDs 与 exact wording | stem/choice 改动会改变 external criterion。 | approved item manifest + checksum。 |
| selected instrument subset | 不同 participant 用不同未记录子集会改变 score denominator。 | frozen assignment manifest。 |
| item / concept order 与 administration rules | 顺序、timing、partial/repeat 规则可改变行为与 missing。 | procedure version。 |
| analysis script | 后验改统计或 exclusion 规则会造成 analysis drift。 | commit hash + script checksum。 |
| analysis-plan document | 明确 primary/secondary/exploratory、ties、missing 与 limitations。 | versioned read-only document。 |
| missing-data semantics | 中途重分类 missing 可产生选择性结果。 | controlled vocabulary + decision log。 |
| study procedure version | 冻结 profile、evidence window、external criterion 和 export 边界。 | dated internal freeze record。 |

可选的仓库 freeze 策略包括 commit hash、manifest、checksum 与 read-only snapshot；tag 只是可选机制，当前不得执行 `git tag`。任何 freeze 只在导师/机构允许继续后才有实际施测意义，不能替代真人研究批准。

## 10. Owner Decision 8：output / reporting plan

以下是候选 reporting structure，不是已填入虚假结果的真人报告模板：

| 输出 | 建议角色 | 当前限制 |
| --- | --- | --- |
| participant-flow summary | 必需候选描述 | 要先有机构允许的定义与最小数据。 |
| concept-level valid N / missing summary | 必需候选描述 | 不得把 missing 当 0，必须保留 reason。 |
| mastery vs criterion descriptive table | primary 候选 | 仅 frozen estimate 与 independent criterion，不称 true mastery。 |
| concept-stratified rank summaries | primary 或 secondary 候选 | 小 N/ties 时可明确 unavailable。 |
| pooled exploratory visualization / table | exploratory | 不得默认 pair 独立、同质或作为唯一结论。 |
| P0/P2/P3 sensitivity table | secondary / sensitivity 候选 | 不能挑选最有利 policy 后才报告。 |
| limitations / deviations | 必需候选描述 | 明示 bank 不对称、无 strict delayed pair、missing、ties 与小样本。 |
| delayed retention / transfer | exploratory 或不报告 | 没有 strict delayed pair；Minimax transfer 不进 primary。 |

禁止主张包括：mastery 已验证、estimator calibrated、某 policy 赢得 production、系统改善学习、recommendation 有效、课程成绩提高或因果效果成立。

## 11. 最小 owner decision set

若郭老师与书院/学校流程确认允许继续，human owner 至少仍须亲自拍板以下 10 项；未决即阻断正式 Study A：

| DECISION_ID | 决策问题 | 可选方案 | 下游后果 | 未决是否阻断 | CODEX_RECOMMENDATION | 最终权限 |
| --- | --- | --- | --- | --- | --- |
| OD-01 | primary external composition 是什么？ | 全部 10 个可 primary item；每 concept 单题 subset；仅 concept-specific reporting。 | 决定 denominator、负担、可比性。 | 是 | 先选 concept-specific primary reporting，再决定 subset。 | human owner |
| OD-02 | Local Search 单题如何处理？ | `correct/1` 且透明报告；从主汇总排除；不施测该 concept。 | 决定不对称的可解释性。 | 是 | 不补题；保留 `correct/1` 或排除并说明。 | human owner |
| OD-03 | Minimax transfer 是否施测？ | 不施测；单独 exploratory；未来另行审核。 | 防止 transfer 污染 primary。 | 是 | primary 排除；如施测仅 exploratory。 | human owner |
| OD-04 | estimator 角色是什么？ | P0 primary+P2/P3 sensitivity；三者并列；仅 P0。 | 决定 multiplicity 与表述。 | 是 | P0 primary，P2/P3 预先指定 sensitivity。 | human owner |
| OD-05 | primary analysis unit 是什么？ | concept-stratified；pooled exploratory；learner-level aggregation；纯描述性。 | 决定独立性与可比性假设。 | 是 | concept-stratified + descriptive ordering。 | human owner，建议导师审阅 |
| OD-06 | rank statistics 如何定位？ | Spearman primary；Kendall tau-b primary；二者并列；仅 ordering。 | 决定 ties 和小样本的呈现。 | 是 | Kendall tau-b tie-aware + Spearman sensitivity + ordering。 | human owner，建议导师审阅 |
| OD-07 | missing vocabulary 与处理如何冻结？ | 受控 reason list + exclusion/summary；暂停不完整 concept；其他预注册规则。 | 决定 valid N、偏差与权利边界。 | 是 | `null + reason`、fail closed、保留原始 missing summary。 | human owner；退出相关部分需机构规则 |
| OD-08 | administration / partial / order 是什么？ | 全部题；固定 subset；预先分块；固定/预先随机顺序。 | 决定 burden、assignment、procedure。 | 是 | 先由 owner 比较负担和可比性，不能临时变更。 | human owner，建议导师审阅 |
| OD-09 | version freeze evidence 是什么？ | commit+manifest+checksum；read-only snapshot；其他可审计组合。 | 防止 instrument/policy/analysis drift。 | 是 | commit hash + item manifest checksum + analysis script checksum。 | human owner |
| OD-10 | reporting hierarchy 是什么？ | concept-level primary；pooled exploratory；P0/P2/P3 sensitivity；不报告 delayed。 | 决定可支持主张边界。 | 是 | concept-level primary、pooled exploratory、delayed omitted until forms exist。 | human owner，建议导师审阅 |

这些决策只在外部流程允许 Study A 后才可能生效；任何 `CODEX_RECOMMENDATION` 都不是授权或 owner approval。

## 12. 必须先与郭老师确认的问题

以下问题只供确认，本文不提供答案：

1. `ADVISOR_TO_CONFIRM`：当前窄范围 Study A 问题是否适合作为项目的后续研究，而不扩展为学习效果或 recommendation intervention？
2. `ADVISOR_TO_CONFIRM`：在邀请少量学生参与前，是否应由郭老师审阅完整 procedure、instrument subset、数据最小化与 participant-facing explanation？
3. `ADVISOR_TO_CONFIRM`：若潜在参与者是同学、组员、课程相关学生或存在评价/机会关系的人，应采取哪些反 pressure / coercion safeguards？
4. `ADVISOR_TO_CONFIRM`：是否允许邀请课程相关学生，是否需要避开本人或导师存在直接影响的群体？
5. `ADVISOR_TO_CONFIRM`：哪些 owner technical freeze（analysis unit、item composition、statistics）需要导师确认或统计方法意见？
6. `ADVISOR_TO_CONFIRM`：未来科研汇报、论文、预印本或结项中使用匿名聚合结果，有哪些导师层面的限制？

## 13. 必须由书院 / 学校 / 正式机构核实的问题

以下全部保持 `UNKNOWN_REQUIRES_EXTERNAL_VERIFICATION`：

1. 是否需要伦理审查、exemption determination、备案或其他正式审批？
2. 匿名或 pseudonymous 的最小学习表现数据是否仍需特定流程？
3. 是否必须提供书面 participant information / consent，具体内容和保存方式是什么？
4. 数据保存期限、存储位置、备份、删除和访问控制有哪些制度要求？
5. participant withdrawal 后，对已收集、已导出、已聚合数据应如何处理？
6. participant complaint / adverse event 的正式渠道和责任人要求是什么？
7. compensation、gift、course credit 或其他激励是否受限制？
8. 未来报告、展示、论文、预印本使用数据时有哪些披露、审核或再同意要求？

没有官方依据时，不得从一般伦理常识推断南京大学、健雄书院或学院“需要”或“不需要”某项流程。

## 14. 推荐的决策顺序

这是一条已知项目依赖顺序，不是对未知 institutional procedure 的推断。

1. **Phase 0：外部确认等待。** 先向郭老师说明研究范围，并向适当书院/学校渠道核实是否需要伦理、备案、consent、数据治理或其他流程。
2. **Phase 1：human owner 技术设计 freeze。** 只有外部流程允许继续后，完成 OD-01 至 OD-10 的决策草案。
3. **Phase 2：郭老师审阅。** 审阅研究问题、participant relationship safeguards、技术主次分析与可主张边界。
4. **Phase 3：institutional requirement satisfied。** 按真实机构要求完成必要程序；若要求不允许或需修改，回到 Phase 1。
5. **Phase 4：participant-facing materials freeze。** 仅在获准后准备参与说明、退出、投诉、隐私和联系材料；本仓库当前尚未创建这些材料。
6. **Phase 5：final pre-study reproducibility checkpoint。** 固定 release、instrument、procedure、analysis script、missing semantics 与版本证据，再由 human owner 明确确认是否可开始。

未知的学校流程可能改变 Phase 1–4 的实际顺序；不得把上述次序写成学校既定制度。

## 15. 结论

当前系统内部准备已足以让负责人看清：何处是已决定的工程边界，何处是 owner design freeze，何处必须等待郭老师，何处必须向书院/学校核实。它不足以允许任何招募、participant ID、真人数据或 Study A execution。

```text
DOCUMENTATION_ONLY = YES
HUMAN_OWNER_DECISIONS_MADE_BY_CODEX = NO
HUMAN_STUDY_AUTHORIZED = NO
READY_FOR_PARTICIPANT_RECRUITMENT = NO
READY_FOR_REAL_DATA_COLLECTION = NO
READY_FOR_STUDY_A_EXECUTION = NO
READY_FOR_OWNER_DECISION_REVIEW = YES
READY_TO_COMMIT = YES
```
