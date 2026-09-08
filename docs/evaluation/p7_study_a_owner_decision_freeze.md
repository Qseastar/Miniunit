# P7 Study A 负责人技术设计冻结记录

> 本文件记录负责人已经明确确认的 OD-01 至 OD-10 技术研究设计决定。它不是真人研究方案、参与者材料、招募文案、伦理结论或真人研究授权。`OWNER_TECHNICAL_DESIGN_FROZEN` 只表示 Study A 的仓库内技术设计已冻结；它不改变 `HUMAN_STUDY_AUTHORIZED = NO`。

## 1. 冻结范围与仍然有效的边界

本冻结仅限 `STUDY_A_TECHNICAL_DESIGN_ONLY`。Study A 只讨论冻结的掌握度估计与独立课程依据表现标准之间的排序／单调一致性。Study B 推荐干预继续完全分离。

下列状态保持不变：

```text
P7_READINESS_LEVEL = LEVEL_2
HUMAN_STUDY_AUTHORIZED = NO
CHECK_BEFORE_REAL_HUMAN_STUDY_RESOLVED = NO
READY_FOR_PARTICIPANT_RECRUITMENT = NO
READY_FOR_REAL_DATA_COLLECTION = NO
READY_FOR_STUDY_A_EXECUTION = NO
```

`LEVEL_2` 的含义仍仅为 11 道研究专用外部测评题已完成负责人内容审核。它不验证真实掌握度、不证明估计器已校准，也不允许招募、采集真人数据或运行 Study A。

机器可验证记录位于 [p7_study_a_owner_design_decisions.json](../../data/evaluation/p7_study_a_owner_design_decisions.json)。它与 [p7_study_a_owner_decision_pack.md](p7_study_a_owner_decision_pack.md) 的关系如下：前者是负责人决定后的冻结记录；后者保留决定前的方案比较和待决历史，二者均不得覆盖。

## 2. OD-01：外部测评组成

负责人冻结当前 10 道可作为主要标准的题目，按知识点组成如下：

| 知识点 | 主要题目 |
| --- | --- |
| `breadth_first_search` | `p7_ext_bfs_depth_claim_a`；`p7_ext_bfs_queue_trace_b` |
| `uniform_cost_search` | `p7_ext_ucs_cost_accumulation_a`；`p7_ext_ucs_positive_cost_bound_d` |
| `a_star_search` | `p7_ext_astar_zero_heuristic_c`；`p7_ext_astar_component_change_b` |
| `local_search` | `p7_ext_local_search_neighbor_a` |
| `minimax_search` | `p7_ext_minimax_min_node_a` |
| `monte_carlo_tree_search` | `p7_ext_mcts_backpropagation_a`；`p7_ext_mcts_expand_untried_child_b` |

主要报告结构为 `CONCEPT_SPECIFIC_CONCEPT_STRATIFIED`。不得建立跨六个知识点的单一主要外部总分；跨知识点汇总仅为 `EXPLORATORY_ONLY`。不增加第 12 题，也不新建题目。

## 3. OD-02：Local Search 不对称边界

`local_search` 保留 `p7_ext_local_search_neighbor_a` 作为唯一主要题目，外部知识点表现透明写为 `CORRECT_OVER_1`。第二表征位置继续为 `LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE`。

不得补题、复制题、调整权重伪装为 `correct/2`、因不对称而静默排除 Local Search，或恢复被阻断的位置。较低测量分辨率必须作为限制进入未来报告。

## 4. OD-03：Minimax transfer 边界

`p7_ext_minimax_two_level_b` 的历史角色保持 `TRANSFER_EXPLORATORY_ONLY`，但在当前 Study A 中为 `NOT_ADMINISTERED_IN_PRIMARY_STUDY_A`。它不属于主要即时标准、延迟平行题或主要外部分数成分。

Minimax 的主要外部标准仅使用 `p7_ext_minimax_min_node_a`。transfer 题仍留在研究专用题库，不删除、不改题、也不改变既有负责人处置记录。

## 5. OD-04：估计器角色

| 估计器 | 已冻结角色 |
| --- | --- |
| P0 | `PRIMARY_ESTIMATOR` |
| P1 | `MATHEMATICAL_REFERENCE_ONLY` |
| P2 | `PRESPECIFIED_SENSITIVITY_ESTIMATOR` |
| P3 | `PRESPECIFIED_SENSITIVITY_ESTIMATOR` |

P0 生产定义仍为 `M_new = 0.65 * M_old + 0.35 * selected_signal`；P2 为 `Beta(1,1)` 先验正则化 Bernoulli；P3 为 `alpha_n=max(0.10, 0.35/sqrt(n))`。本冻结不宣布 P0 最好，禁止事后选择胜出估计器、据此修改生产策略或把敏感性结果写成胜者竞赛。

## 6. OD-05 与 OD-06：分析单位和排序统计量

主要分析为 `CONCEPT_STRATIFIED`，且 `DESCRIPTIVE_ORDERING` 是主要支持性描述。学习者 × 知识点汇总仅为 `EXPLORATORY_ONLY`；当前不采用跨知识点的学习者层级聚合，也没有负责人批准的跨知识点权重规则。

此决定保留了以下事实：Local Search 为 `correct/1`，Minimax 主要标准为 `correct/1`，其他部分知识点为 `correct/2`；同一参与者的多知识点观测具有重复结构。因此不得默认这些观测独立、同质或等权。

`KENDALL_TAU_B` 是主要描述性排序统计量，`SPEARMAN_RHO` 是预先指定的敏感性统计量。未来输出必须同时报告一致对、相反对、掌握度并列、外部表现并列、共同并列、有效配对数和缺失数。`n >= 3` 仅保留为程序计算安全门槛，不是样本量建议、充分样本或统计功效阈值；不引入显著性阈值、p 值搜寻或功效分析。

## 7. OD-07：缺失值技术语义

硬边界冻结为：

```text
missing = null + missing_reason
missing != 0
```

可用的纯技术原因集合为：`instrument_not_administered`、`participant_nonresponse`、`technical_failure`、`estimate_unavailable_no_eligible_evidence`、`protocol_deviation`、`other_controlled_reason`。这些原因对应的结果值均为 `null`，不得转换为错误、零分或负向证据；未知或不可用结果应失败关闭。

有关退出后已收集数据、去标识聚合、保留期限、删除、截止时间与联系程序，仍是 `ADVISOR_CONFIRMATION_REQUIRED`／`INSTITUTIONAL_VERIFICATION_REQUIRED`，本冻结没有作出任何决定。

## 8. OD-08：施测技术设计与题序边界

负责人冻结的技术原则为：所有参与者使用同一套 10 道主要题；不采用部分施测、参与者特定子集或平衡不完整区组；每道主要即时题只作答一次；立即重做不视为新的独立标准。

题序策略已冻结为 `OWNER_APPROVED_FIXED_PREGENERATED_CONSISTENT_ORDER`，原则上避免同一知识点的两题紧邻，以减少直接提示风险。但是 `EXACT_ITEM_ORDER = PENDING_PRE_STUDY_FREEZE`：本轮不生成最终真人施测顺序、不创建会话分配器，也不创建参与者界面流程。题序仍须等待导师和机构要求后，作为 pre-study freeze 的一部分完成。

## 9. OD-09：版本冻结契约

未来如外部流程允许继续，技术冻结至少采用：提交哈希、清单、SHA-256 校验和、流程版本及分析版本。第一位真人参与者进入前，至少要固定：

1. 生产提交或发布版本；
2. 生产诊断注册表；
3. 掌握度策略实现；
4. 外部题目 ID 与精确措辞；
5. 当前 10 题工具清单；
6. 题序与施测策略版本；
7. 分析脚本版本；
8. 分析计划版本；
9. 缺失值语义版本；
10. 流程版本。

该契约的状态是 `TECHNICAL_DESIGN_FREEZE`，并明确为 `NOT_HUMAN_STUDY_RELEASE`。本轮不创建 Git tag、正式真人研究发布或真人研究批准声明。

## 10. OD-10：报告层级

| 层级 | 已冻结内容 |
| --- | --- |
| 主要 | 知识点层级／分层报告、P0 掌握度估计、`KENDALL_TAU_B`、描述性排序、并列、有效样本数和缺失摘要。 |
| 敏感性 | P2、P3、`SPEARMAN_RHO`。 |
| 探索性 | 学习者 × 知识点汇总的可视化与描述性摘要。 |
| 当前不报告 | 延迟保持主张、Minimax transfer 结果。 |

未来限制说明必须包含 Local Search 与 Minimax 的 `correct/1`、知识点粒度不一致、严格延迟平行题不可用、并列、缺失、小样本风险、参与者重复结构及汇总分析仅探索性。

禁止主张真实掌握度已验证、估计器已校准、P0/P2/P3 存在胜出者、学习增益、推荐有效性、课程成绩改善或因果效果。

## 11. synthetic dry-run 的定位

synthetic dry-run 继续只使用固定合成数据，且必须保留 `SYNTHETIC_ONLY`、`NOT_APPROVED_FOR_REAL_HUMAN_DATA` 与 `HUMAN_STUDY_AUTHORIZED = NO` 的边界。其 10 道主要题组成、Local Search `correct/1`、Minimax transfer 排除、P0/P2/P3、分层主要分析、汇总探索性分析、Kendall tau-b、Spearman 与缺失值 `null` 语义已与本冻结记录一致。

dry-run 用于检验离线分析管线与边界情况，绝不是实际参与者数据结构、正式分析计划、真人研究批准或估计器优劣证据。

## 12. 尚待外部确认的真人研究阻断项

以下问题未被本冻结解决：

- 郭老师：研究范围是否适当、参与者关系压力防护、任何邀请前的流程与分析审阅、未来展示或发表要求；
- 书院／学校／正式机构：伦理、备案或豁免判断；知情说明；招募与补偿；数据最小化、身份链接、保存、删除与访问；退出和投诉处理；
- 真人研究前的精确题序、参与者材料、真实流程、机构要求下的数据治理与最终 pre-study freeze。

在这些真实外部信息出现并被单独记录前，禁止招募、创建参与者 ID、采集或导出真人数据、运行 Study A 或把本技术冻结解释为授权。

```text
OWNER_TECHNICAL_DESIGN_FROZEN = YES
SYNTHETIC_DRYRUN_ALIGNED_WITH_OWNER_DESIGN = YES
HUMAN_STUDY_AUTHORIZED = NO
READY_FOR_PARTICIPANT_RECRUITMENT = NO
READY_FOR_REAL_DATA_COLLECTION = NO
READY_FOR_STUDY_A_EXECUTION = NO
```
