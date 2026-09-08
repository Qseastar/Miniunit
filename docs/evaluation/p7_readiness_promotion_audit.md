# P7 Readiness Promotion Audit

> 本文件只审计 P7 external assessment instrument 是否可提交给 human owner 作 Level 2
> readiness decision。不执行 status promotion，不启动人体研究，也不将 external result 解释为
> true mastery、ground truth、校准概率或 production evidence。

## A. Git / repository baseline

- 审计分支：`feature/p7-readiness-promotion-audit`。
- 审计基线：`81a390a research: finalize external assessment owner review (#36)`；历史包含
  P7 (`a95783f`)、P7b (`0054526`) 及 P7c/P7d 的 merged finalization。
- candidate bank、P7a–P7d 文档、validator、synthetic runner 和 P7/P7b/P7c/P7d 测试均存在。
- 本审计不改 production、mastery、evidence gate、repeat policy、recommendation、study UI 或
  candidate status。

## B. P7a–P7d owner-decision lineage

P7a 是 review preparation，不是 owner approval。P7b 记录首轮 preserve/revise/reject 方向；
P7c 记录第二轮 owner decisions；P7d 记录第三轮 decisions 与 Local Search blocking。当前
human-owner baseline 下，11 个 active item 的可追溯 disposition 如下：

| Active item | Concept | Current role | Human-owner disposition / basis |
| --- | --- | --- | --- |
| `p7_ext_bfs_queue_trace_b` | BFS | preserve-direction external criterion | owner-confirmed preserve；current owner baseline、P7b preserve list |
| `p7_ext_ucs_cost_accumulation_a` | UCS | preserve-direction external criterion | owner-confirmed preserve；current owner baseline、P7b preserve list |
| `p7_ext_astar_component_change_b` | A* | preserve-direction external criterion | owner-confirmed preserve；current owner baseline、P7b preserve list |
| `p7_ext_minimax_min_node_a` | Minimax | preserve-direction external criterion | owner-confirmed preserve；current owner baseline、P7b preserve list |
| `p7_ext_minimax_two_level_b` | Minimax | `TRANSFER_EXPLORATORY_ONLY` | owner-confirmed preserve；current owner baseline、P7b parallel audit |
| `p7_ext_mcts_expand_untried_child_b` | MCTS | preserve-direction external criterion | owner-confirmed preserve；current owner baseline、P7b preserve list |
| `p7_ext_bfs_depth_claim_a` | BFS | revised external criterion | `OWNER_APPROVE`；P7c second-owner decision table |
| `p7_ext_local_search_neighbor_a` | Local Search | revised neighbor-process criterion | `OWNER_APPROVE`；P7c second-owner decision table |
| `p7_ext_mcts_backpropagation_a` | MCTS | revised stage-function criterion | `OWNER_APPROVE`；P7c second-owner decision table |
| `p7_ext_astar_zero_heuristic_c` | A* | revised heuristic-extreme criterion | `OWNER_APPROVE`；P7c second-owner decision table |
| `p7_ext_ucs_positive_cost_bound_d` | UCS | complementary positive-cost-bound criterion | `OWNER_APPROVE`；P7d third-owner decision table |

没有 active item 仅有 Terra recommendation、没有 current human-owner decision。P7a/P7b 内的
`OWNER_*_RECOMMENDED` 仅是历史建议；本表 preserve 项依据当前 human-owner baseline，revised
项依据 P7c/P7d decision records。

## C. Current external bank map

| Selected concept | Active external items | Count |
| --- | --- | ---: |
| `breadth_first_search` | `p7_ext_bfs_depth_claim_a`, `p7_ext_bfs_queue_trace_b` | 2 |
| `uniform_cost_search` | `p7_ext_ucs_cost_accumulation_a`, `p7_ext_ucs_positive_cost_bound_d` | 2 |
| `a_star_search` | `p7_ext_astar_zero_heuristic_c`, `p7_ext_astar_component_change_b` | 2 |
| `local_search` | `p7_ext_local_search_neighbor_a` | 1 |
| `minimax_search` | `p7_ext_minimax_min_node_a`, `p7_ext_minimax_two_level_b` | 2 |
| `monte_carlo_tree_search` | `p7_ext_mcts_backpropagation_a`, `p7_ext_mcts_expand_untried_child_b` | 2 |

当前为 11 个 active、closed、deterministically gradable、research-only item，覆盖 6 个 selected
concept。validator 实测无 duplicate ID、exact stem collision、internal duplicate option set、
production ID/stem/full option-set collision；11 项均为 `INDEPENDENT_CAPABILITY_SAMPLE` 或
`COMPLEMENTARY_CAPABILITY`，无 `TOO_SIMILAR` / `CIRCULAR`。

旧项均只留历史：`p7_ext_ucs_equal_depth_cost_b`、`p7_ext_astar_f_computation_a`、
`p7_ext_ucs_depth_cost_tradeoff_c` 和 `p7_ext_local_search_representation_b` 均不在 active pool。

## D. Asymmetric-bank / Local Search blocked audit

`LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE` 可在 P7d 完整追溯；P7c proposal 没有
被抹去或伪称通过。Lec4 的直接证据只能形成 production 已测的 final-state definition 或 approved
sibling 已测的 candidate/neighborhood process；继续强造第二题将重叠或泄露答案规则。

故 Local Search 仅保留一项是 intentional scientific design，不是漏数据。validator 从“每个
selected concept 至少两题”改为“至少一题”，仍要求 selected concept 集合与实际项目集合一致、
每个 concept 至少一项、closed answer、source ref、production comparison 与完整 pending schema。
P7d 测试还锁定 Local Search 恰有一项。因此允许 owner-accepted blocked slot，不允许任意
concept 静默消失。

## E. Owner-status representation audit

JSON 的 `assessment_status` 与每个 `human_review_status` 都为 `pending_owner_review`，且
validator 明确拒绝其他值。其当前语义是 research-only candidate-bank lifecycle：未注册到
production、未暴露、未产生 production evidence。实际人类 disposition 保留在 P7b–P7d 的
owner-review/revision history documents。

这是一种双层表示，而不是本审计发现的内容审批缺失：JSON `pending` 不等于“没有 owner
decision”。字段名称仍可能造成误读；若 owner 作出正式 Level 2 decision，推荐后续单独设计
非-production、可追溯的 status-promotion record。该表示改进不是本轮 Level 2 instrument-review
blocker，也不应被本审计擅自修改。

## F. Production-isolation audit

P7 bank 位于 `data/evaluation/`，不在 `data/diagnostic_templates.json`。`app.py` 与
`src/introai_tutor/` 不导入 P7 validator 或 synthetic runner。production manifest 保持：

- production templates：28；
- active production candidates：0；
- blocked slots：1；
- knowledge concepts：26。

P7 external items不进入 selector、普通学生 UI、production exposure、learner state、mastery、
recommendation 或 LLM primary grading。P7/P6/repeat/verification/P5b 回归未发现 P7c/P7d 改变
production semantics。

## G. Research-claims audit

允许解释仍是 **independent course-grounded performance criterion**。未来 Study A 的 primary
analysis 是 frozen policy estimate 与该 criterion 的 rank/monotonic alignment。扫描没有发现把
external result 积极声称为 true mastery、ground-truth knowledge、calibrated probability、
validated mastery、psychometric validation、learning effectiveness、improved grades 或 proven
learning gains 的文本；出现这些词的地方均是否定、风险或边界说明。

## H. Level-definition consistency audit

正式 P7 protocol 主定义为：Level 1 = synthetic pipeline validated；Level 2 = external candidates
owner-reviewed；Level 3 = small feasibility pilot ready。

`CHECK_BEFORE_REAL_HUMAN_STUDY`（voluntary participation、research purpose、no grade
consequence、withdrawal、data minimization、retention/deletion、teacher/institutional requirements）
是 protocol 中独立的真人研究前 checkpoint。P7a–P7d 所说“仍为 Level 1”是当时 owner decisions
未完整或尚未完成 promotion audit 的历史状态，不是把 ethics/institutional checkpoint 定义为
Level 2 前置条件。

P7a/P7b 对 strict parallel forms 的担忧是 future study-design 限制；protocol 未将 strict pair
列为 Level 2 定义条件。当前没有需要 owner 先解决的 Level 定义冲突；owner decision 应采用
protocol 的 Level 2 定义，并同时重申真人研究前的独立 checkpoint。

## I. Parallel-form audit

当前没有 owner-reviewed strict immediate/delayed parallel pair。不同 micro-capability、concept
bundle 与 `p7_ext_minimax_two_level_b` 均不得伪称 strict parallel；后者仍为
`TRANSFER_EXPLORATORY_ONLY`。这不阻止“external candidates owner-reviewed”的 Level 2 eligibility，
但限制未来 delayed-retention 或较强 Study A design，需在实际研究设计前由 owner 决定。

## J. Synthetic-pipeline audit

`tools/run_p7_synthetic_study.py` 仍为 synthetic-only：使用固定可见 synthetic participant code
和 P6b temporary traces，离线生成 8 个 scenario；不写 production mastery、exposure、recommendation、
learner state 或数据库，不调用网络，也不用真实 participant。P7d 后 S4 使用 active 的
`p7_ext_local_search_neighbor_a`，没有把 blocked slot 伪造成 0 或 missing result。S7/S8 保持
`null + missing_reason`。

## K. Privacy / missing-data audit

P7 export 与测试排除姓名、学号、邮箱、IP、user-agent、learner UUID、QA 原文、题干/答案、PDF
内容与 secret。未施测或失访保持 `null + missing_reason`，不被写成错误。未新增真人 participant
schema 或数据字段。

## L. Remaining blockers and readiness judgment

**Instrument-review blockers：无。** 11 个 active item 均有 traceable human-owner disposition；
Local Search blocking 已被接受；bank、validator、synthetic pipeline 与 production isolation 一致。

**非阻塞、但真人研究前仍需单独处理：**

1. human owner 必须亲自作出 Level 2 readiness decision；
2. 若真正招募/施测，先完成 `CHECK_BEFORE_REAL_HUMAN_STUDY`；
3. delayed strict parallel forms 尚未建立，不能假装已有 delayed-retention design；
4. 若希望 machine-readable approval，单独设计 research-only status-promotion record，不能混入
   production evidence schema。

```text
LEVEL_2_ELIGIBLE_RECOMMENDED = YES
READY_FOR_OWNER_READINESS_DECISION = YES
READY_TO_COMMIT = YES
```

**LEVEL 2 DOES NOT AUTHORIZE HUMAN STUDY.**

**HUMAN-STUDY ETHICS / INSTITUTIONAL / PARTICIPANT-PROTECTION CHECKPOINT REMAINS SEPARATE AND UNRESOLVED.**

## M. Verification record

- candidate validator：`valid=true`；11 items、6 selected concepts、0 production collision；
- synthetic runner：8 synthetic scenarios、2 controlled missing external results；
- P7/P7b/P7c/P7d targeted：25 passed；
- P6/P6b/repeat/verification/P5b regressions：143 passed；
- P5a grounding/citation/release regressions：54 passed；
- quick gate：acceptance 393 passed；smoke 121 passed、1628 deselected；
- strict gate：passed；其 full suite 为 1747 passed、2 skipped；
- collection inventory：1749 tests collected；
- `git diff --check` 与 `git diff --cached --check`：passed。
