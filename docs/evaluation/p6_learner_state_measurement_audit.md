# P6 Learner-State Measurement Audit

本报告是离线、合成学习者轨迹审计，不是对真实学习者掌握度的心理测量验证。
所有轨迹通过当前 reviewed-template、exposure policy、verification scorer、P5B
integration、SQLite persistence 和 recommendation 生产组件运行；没有复制第二套
mastery 引擎，也没有读取 `.env` 或调用网络。

## Research questions

本轮关注同一 learner 在受控证据轨迹下的：

- 正确、错误、受帮助和重复作答是否被区分；
- 同一 concept 的不同 reviewed template 是否能产生新的正式证据；
- evidence 顺序、先修关系和 recommendation 边界的实际行为；
- deterministic replay、隔离、reset 与 fail-closed 语义。

## Current estimator semantics

真实 mastery 入口是 `DiagnosticStateIntegrationService.apply()`。对每个
`concept_observations[concept_id]`，它从同一 concept 的 observation 中筛选
`assisted == False`，选择最后一个未辅助 raw score；若没有未辅助 observation，
不更新该 concept。默认权重为 `0.35`，公式为：

```text
new_mastery = clamp((1 - 0.35) * old_mastery + 0.35 * selected_signal, 0, 1)
```

`selected_signal` 可以是 `0.0`，因此已完成的未辅助错误证据会把已有掌握度向下更新；
但未完成的第一次错误提交尚未形成 completed summary，也不会越过 integration gate。

真实 recommendation 入口是 `recommend_next_concept()`。它使用 mastery `< 0.6`
作为薄弱判定，按 knowledge registry 顺序选择第一个薄弱 concept，再沿
`prerequisites` 向上回溯到第一个仍薄弱的先修概念。该逻辑是确定性的，且没有
额外的 evidence 聚合或平滑层。

## Evidence taxonomy

| 类型 | 当前生产行为 | 是否可更新 mastery |
| --- | --- | --- |
| 首次 reviewed template formal | 首次 exposure claim 后保持 formal | 是（仅未辅助 observation） |
| 同 template 后续 exposure | `practice_only`，不调用 P5B | 否 |
| formal + hint retry | history 保留 raw score 与 `hint` provenance；P5B 忽略 assisted score | 仅使用此前未辅助 observation |
| reveal | reveal 只推进步骤，不创建 observation；完成 summary 可为空 observations | 不产生正向独立 signal |
| formative scaffold/clarification | 只存在于 formative 轨道 | 否 |
| malformed/unknown/unsupported | 在 scorer、selector 或 persistence 边界拒绝 | 否 |

## Synthetic trajectory design

`tools/audit_learner_state.py` 提供 `run_session()` 和
`run_representative_audit()`。默认输出到 `/tmp/introai_p6_learner_state_audit.json`，
只包含 synthetic learner 和结构化数值。

每个 snapshot 包含 trajectory、step、template、primary concept、正确性、
assistance provenance、formal/practice classification、selected signal、weight、
前后 mastery、delta、formal evidence/exposure count、recommendation 前后和
`state_update_present`。

## Representative concepts selected

基于当前真实 registry/template inventory 选择：

1. `breadth_first_search`：有两个 direct production templates，适合独立证据数量和顺序比较；
2. `uniform_cost_search`：有 reviewed UCS frontier template，且依赖
   `frontier_and_explored_set` 与 `completeness_optimality_complexity`；
3. `a_star_search`：有 reviewed A* template，并依赖 UCS/informed-search。

当前核实 inventory：production reviewed templates=28，active candidates=0，blocked
slots=1，concepts=26。

## Single-step counterfactuals

审计脚本为三个 representative concepts 各运行 independent correct、第一次错误、
hint-assisted correct 和 reveal。代表性结果：

| 轨迹 | formal/practice | selected signal | mastery（0 起点） |
| --- | --- | ---: | ---: |
| independent correct | formal | 1.0 | 0.35 |
| first incorrect (retry_ready，尚未完成) | formal session，未产生 summary | — | 0.0 |
| wrong → hint → correct | formal | 0.0 | 0.0 |
| reveal before answer | formal summary，无 observation | — | 0.0 |

第一次错误只有在用户完成 retry/reveal 状态机后才会进入 completed summary；这不是
错误吞分，而是当前 workflow 的完成边界。

## Repeat vs independent evidence

同一 learner 对 `verify_bfs_frontier_choice_v1` 首次正确后再次正确，第二次被
`practice_only` 分类，`state_update` 为 `None`，formal mastery 保持 `0.35`。
同一首次正确后再次错误也保持 `practice_only`，不会反向污染 formal mastery；
首次错误后在同一 formal session 进入 hint retry 的轨迹则保留 raw 错误并由
未辅助 signal 决定后续 mastery。

同一 concept 改用第二个 production template
`verify_bfs_equal_cost_condition_v1`，第二次仍为 formal，mastery 从 `0.35`
更新为 `0.5775`，formal evidence count 从 1 变为 2。当前 P5B 不是平均多个证据，
而是对该次 summary 选择最后一个未辅助 signal；两个模板提供了第二个正式机会，
但不会形成独立的累计统计量。

## Assistance counterfactuals

- independent correct：`assistance_level=none`，selected signal=1.0；
- hint-assisted correct：history 同时保存未辅助错误和 hint 正确，selected signal=0.0；
- reveal：无答题 observation，selected signal=None，mastery 不增加；
- scaffold/clarification：当前只属于 formative 反馈，不能注入 verification evidence，
  审计工具明确将其标记为 `formative_only`，没有伪造验证 observation。

## Correct vs incorrect

未辅助正确完成的 formal template 将 mastery 从 0 更新到 0.35。一次错误提交本身
停留在 `retry_ready`，不会提前写入 formal evidence；完成两次错误并确认 reveal 后，
summary 的未辅助 signal 为 0.0，已有 mastery 会按既有公式下降。

## Evidence-order audit

使用 BFS 的两个不同 template，避免同 template repeat policy 污染：

| 顺序 | 第一步后 | 第二步后 |
| --- | ---: | ---: |
| correct → incorrect | 0.35 | 0.2275 |
| incorrect → correct | 0.0 | 0.35 |

这是 `last_unassisted_observation` 和递推公式导致的 `ORDER_SENSITIVE_BY_DESIGN`，
不是已证实的实现 bug；应进入 P6b 的 estimator sensitivity 研究。

## Prerequisite/recommendation results

在其余概念设为高 mastery 的受控状态中：

- `frontier_and_explored_set` 弱、BFS 弱 → 推荐 `frontier_and_explored_set`；
- 该前置强、BFS 弱 → 推荐 `breadth_first_search`；
- BFS 强但 frontier 弱 → 仍优先推荐 `frontier_and_explored_set`。

这确认 recommendation 会沿真实 prerequisite graph 回溯，但不会因为 dependent
看起来较强而跳过薄弱前置。

## Recommendation sensitivity

fresh empty state 推荐 `search_problem_formulation`。当 registry 中最前面的基础
概念被置为高 mastery 后，推荐可切换到 `breadth_first_search`；这是阈值/registry
decision region 的直接结果。也观察到 mastery 发生变化但 recommendation 保持不变，
例如单个 BFS 证据从 0 到 0.35 仍未跨越推荐路径的前置边界。

## Monotonicity audit

| 期望 | 观察 | 结论 |
| --- | --- | --- |
| 首次 independent correct 不降低该 concept | 0 → 0.35 | PASS |
| same-template practice-only 不改变 formal mastery | 0.35 → 0.35 | PASS |
| reveal 不产生独立正向 signal | signal=None，mastery=0 | PASS |
| 新 learner 不受其他 learner 影响 | B 为空且无 exposure | PASS |
| reset 清除 mastery/evidence/exposure | 全部恢复空状态 | PASS |
| malformed/unknown 不写 formal evidence | 在边界抛出异常、history 为空 | PASS |

这些是当前代码已承诺的有限 invariant；并不等价于 mastery 的心理测量单调性。

## Determinism audit

相同 registry、template、answer 和空 learner state 在两个临时 SQLite 中 replay，
snapshot 的 correctness、signal、mastery、formal count 和 recommendation 完全一致。
未调用 LLM。

## Learner isolation/reset audit

两个 synthetic learner 共用临时 SQLite 时，A 的 mastery/evidence/exposure 不会出现在 B。
对 A 调用 `LearnerStatePersistenceService.clear(learner_id=...)` 后，mastery、
learning evidence 和 template exposure 均清除；profile 恢复为空状态，transient UI
状态不在 persistence schema 中。

## Failure-case audit

离线测试覆盖：无效 choice、malformed response、未知/blocked template、unsupported
scorer payload、duplicate event ID 和 already-exposed template。selector/scorer/persistence
均 fail closed；相同 event ID + 相同 payload 是幂等 no-op，冲突 payload 被拒绝。

## Unexpected findings

没有发现违反已有设计 invariant 的 implementation bug。两个需要注意但不应在 P6
调参的问题是：

1. completed summary 选择最后未辅助 raw score，而不是对多个 formal evidence 求平均；
2. correct→incorrect 与 incorrect→correct 明显 order-sensitive；
3. recommendation 受 registry 顺序和 0.6 threshold 的 decision region 影响，
   mastery 变化不一定立即改变推荐。

## Implementation bugs found

0。没有修改生产逻辑。

## Measurement-design questions

这些现象符合当前实现，但需要未来研究决定是否更适合学习测量：

- 多个不同模板的 evidence 是否应聚合而不是只取最后一次；
- 近期错误是否应覆盖早期正确，或应使用更稳健的时间/证据聚合；
- registry order 与单一阈值是否会造成推荐优先级偏差；
- reveal 后的空 observation summary 是否需要在分析层与正式 event 分开计数。

## Valid claims

本轮数据支持的表述：

- reviewed evidence 在固定轨迹下产生确定性的 learner-state 更新；
- 同一 reviewed template 的重复 exposure 不会生成第二次 formal mastery update；
- assisted observation 与 unassisted observation 在 P5B 中可区分；
- recommendation 会对受控 mastery/prerequisite 状态变化作出确定性响应。

## Claims not supported

本轮不能支持：

- mastery 等于真实学生知识；
- mastery 是 calibrated probability；
- 更高 mastery 能预测考试表现；
- recommendation 一定改善学习；
- 系统已经具备 psychometric validity。

## P6b hypotheses

H1：当前 recency/last-unassisted policy 可能导致显著 order sensitivity。

H2：同一 concept 的多模板证据若仅取最后一次，可能丢失部分测量信息。

H3：单一 0.6 threshold 加 registry 顺序可能让 recommendation 对不同 concept 的
边界不对称。

## Future human-evaluation questions

下一阶段真人研究应分别测量：诊断相关性、与独立测评的一致性、mastery calibration、
学生对 assistance/feedback 的信任、recommendation usefulness，以及重复题和提示
对后续独立表现的影响；本报告不实施招募或比赛问卷。

## Sensitive-data audit

只使用 `synthetic_p6_*` learner ID 和临时 SQLite。报告不保存真实 learner UUID、
问题回答、课程正文、API key、Authorization 或模型输出。

## Repository-pollution audit

结构化结果默认写入 `/tmp/introai_p6_learner_state_audit.json`；仓库只新增本工具、
离线测试和本报告。没有新增 SQLite、PDF、日志、PNG 或缓存。

## Git diff/status

本轮不执行 `git add`、`commit`、`push`、`merge`、`reset`、`stash`、`checkout` 或
`tag`。最终以命令输出为准。

## Blocking issues

没有发现阻塞当前 P6 审计交付的问题。order sensitivity、多证据聚合和 recommendation
边界属于 P6b measurement-design questions，而不是本轮应擅自修改的实现 bug。

## READY_TO_COMMIT

YES（仅表示 P6 审计工具、测试和文档已完成，仍需人工审阅 diff 后再决定是否提交）。
