# P6b Learner-State Aggregation Policy Comparative Study

## Research motivation

P6 已经刻画当前 estimator：它是“固定步长、具有近期证据偏好的递推式聚合策略”，不是不聚合多条证据。本研究只在既有 formal evidence gate 之后，比较若干透明 aggregation policy 在相同、合格的独立二元信号上的数学行为。它是离线行为比较，不是对真实学生知识的心理测量验证，也不部署任何候选政策。

## What P6 established

- 生产入口为 `DiagnosticStateIntegrationService.apply()`；默认 observation weight 为 `0.35`。
- formal completed interaction 中，P5B 对每个 concept 选择最后一条 `assisted=False` 的 raw observation；没有未辅助 observation 时不更新。
- 同一 reviewed template 后续 exposure 为 `practice_only`，不产生第二个 formal mastery update；hint/reveal 不能把辅助正确作答变为独立正向 evidence。
- recommendation 使用真实 `recommend_next_concept()`，阈值为 mastery `< 0.6`，并沿真实 prerequisite 向上回溯。

## Current production policy

当前 inventory：production templates=28、active candidates=0、blocked slots=1、concepts=26、SQLite schema=3。生产 policy 记为 P0，起点 `M_0=0`：

```text
M_(t+1) = clamp((1 - 0.35) M_t + 0.35 s_t, 0, 1)
```

P6b 中的 P0 是 `REFERENCE_REIMPLEMENTATION_FOR_COMPARISON_ONLY`；测试通过连续真实 `DiagnosticStateIntegrationService.apply()` 事件验证其代表序列与 production 一致。生产代码、weight、threshold、P5B、evidence gate、repeat policy、templates、registry、recommendation 和 SQLite schema 均未修改。

## Comparison scope

研究问题为：证据排列是否改变估计、近期响应与稳定性如何权衡、弱 prior 如何影响稀疏证据，以及阈值附近的数值差异是否真的改变现有 recommendation。这里的 signal 仅为已经通过现有 gate 的独立 formal signal（当前实际为 `correct=1.0` / completed independent incorrect=`0.0`）。

## Evidence eligibility boundary

Layer A（reviewed template、assistance、repeat、completion、malformed/blocked rejection）保持生产行为；Layer B 才是本研究的 policy comparator；Layer C 仅把各 policy 生成的 synthetic mastery snapshot 交给未修改的 `recommend_next_concept()`。

这一区分尤为重要：第一次错误但仍处于 retry flow 不是 completed formal event；同 template repeat 为 practice-only；hint 后正确仍以先前 unassisted raw score 为 selected signal；reveal 不产生 positive observation；formative scaffold/clarification 从不进入 verification evidence。

## Candidate policies

| Policy | 角色 | 排列不变性 | 参数 |
| --- | --- | --- | --- |
| P0 `CURRENT_FIXED_STEP` | 当前生产 reference | 否 | fixed `alpha=0.35` |
| P1 `EQUAL_WEIGHT_EMPIRICAL_MEAN` | 透明均值 baseline | 是 | 无 |
| P2 `PRIOR_REGULARIZED_BERNOULLI` | 对称弱 prior accumulator | 是 | Beta(1,1)；另测 Beta(2,2) |
| P3 `COUNT_DECAYED_STEP` | 有界、递减但保留近期权重的 baseline | 否，但远弱于 P0 | base=0.35、floor=0.10 |

## Mathematical definitions

令 eligible independent formal signals 为 `s_1...s_n`，均在 `[0,1]`。

- P0：`M_n=(1-0.35)M_(n-1)+0.35s_n`，`M_0=0`。
- P1：`M_n=(sum_i s_i)/n`；初始显示值为 0，不是 evidence。
- P2：`M_n=(a+sum_i s_i)/(a+b+n)`，主比较 `a=b=1`；初始 posterior mean 为 0.5。
- P3：`M_n=(1-alpha_n)M_(n-1)+alpha_n s_n`，`M_0=0`，`alpha_n=max(0.10, 0.35/sqrt(n))`。它前期采用与 production 相同的第一步 alpha，随着独立 evidence 增多递减，约第 13 条起触及 floor。P3 不等于 running mean 或 P2；其递归权重仍保留 recency，只是比 P0 更快衰减。

这些是比较用的透明数学规则，不是拟合得到的教育参数，也不是 BKT、IRT 或校准模型。

## Experimental design

`tools/compare_mastery_policies.py` 是纯 offline、deterministic、research-only 工具：不读 `.env`、不读真实 learner DB、不调用模型/网络、不写 app state。它枚举长度 1–6 的全部二元 signal sequence（`2^1+...+2^6=126`），并将完整原始结果只写入 `/tmp/introai_p6b_policy_comparison.json`。仓库只保存工具、性质测试和本摘要；不提交 SQLite、CSV、图或 runtime artifacts。

## Integration-faithful trajectories

真实 templates、selector、exposure policy、verification scorer、P5B integration 和临时 SQLite 产生如下 policy 输入；随后才进入 isolated comparator：

| 场景 | 真实 formal signal sequence | 关键 gate 结论 |
| --- | --- | --- |
| 两道不同 BFS template 均正确 | `[1,1]` | 两次均 formal |
| correct → completed incorrect | `[1,0]` | 完成后的 independent incorrect 才形成 0 |
| completed incorrect → correct | `[0,1]` | 顺序真实可达，使用不同 template |
| 同 template correct 后 repeat correct | `[1]` | 第二次 practice-only，`state_update=None` |
| hint/reveal | `[0]` | hint 后正确不覆盖前一未辅助 0；reveal 无 signal |

因此 policy-isolated simulation 的输入不是把 raw clicks、hint/reveal 或重复答案粗暴当作普通 1。

## Exhaustive synthetic sequences

每个 126 条 sequence row 保存完整 trajectory、final mastery、max/mean absolute step delta、0.6 threshold crossings、长度和正确/错误计数。它们只是假设 signal 已合法进入 Layer B，不能被解读为 126 名真实学生或 end-to-end learning simulation。

## Order sensitivity

对于同一 `(n, successes, failures)` 的所有 unique permutation，计算 final mastery 的 max-min range（OSR）及其按 multiset 的 mean。P1/P2 在所有 `n=2..6` 严格为 0（由定义）；P0、P3 都保留顺序性。

| n | P0 max OSR / mean OSR | P1 | P2 | P3 max OSR / mean OSR |
| ---: | --- | --- | --- | --- |
| 2 | 0.122500 / 0.122500 | 0 / 0 | 0 / 0 | 0.015892 / 0.015892 |
| 3 | 0.202125 / 0.202125 | 0 / 0 | 0 / 0 | 0.012681 / 0.012681 |
| 4 | 0.333506 / 0.280423 | 0 / 0 | 0 / 0 | 0.018752 / 0.014305 |
| 5 | 0.418904 / 0.353213 | 0 / 0 | 0 / 0 | 0.026100 / 0.022603 |
| 6 | 0.526169 / 0.418755 | 0 / 0 | 0 / 0 | 0.039911 / 0.033520 |

例如 `[1,0]` 与 `[0,1]` 的 final mastery 依次为 P0 `0.227500 / 0.350000`、P1 `0.5 / 0.5`、P2 `0.5 / 0.5`、P3 `0.263379 / 0.247487`。这证实 P0 的 recency sensitivity 是 fixed-alpha family 的结构性数学性质，而不是实现缺陷的证据。

## Responsiveness

| History → new signal | P0 Δ | P1 Δ | P2 Δ | P3 Δ |
| --- | ---: | ---: | ---: | ---: |
| `[0,0,0] → 1` | +0.350000 | +0.250000 | +0.133333 | +0.175000 |
| `[1,1,1] → 0` | -0.253881 | -0.250000 | -0.133333 | -0.106699 |
| `[0,0,0,0,0] → 1` | +0.350000 | +0.166667 | +0.107143 | +0.142887 |
| `[1,1,1,1,1] → 0` | -0.309390 | -0.166667 | -0.107143 | -0.104080 |

P0 对任意晚到单条证据仍以 0.35 的固定混合系数响应；P1/P2 随 count 递减，P3 居中。响应快本身不代表测量更正确。

## Stability

在 contradiction-heavy sequences `[1,0,1,0,1,0]`、`[0,1,0,1,0,1]` 与 `[1,1,0,0,1,0]` 上，工具记录 mean/max absolute delta 与 threshold crossings。P0 的固定 recent weight 产生最大逐步摆动；P1/P2 的顺序不变 final state 更稳定；P3 仍可响应新证据，但其衰减 step 将 permutation range 限制在 P0 的小部分。该结果是确定性数值描述，不是 reliability coefficient。

## Sparse-data behavior

| Sequence | P0 | P1 | P2 Beta(1,1) | P3 |
| --- | ---: | ---: | ---: | ---: |
| `[1]` | 0.350000 | 1.000000 | 0.666667 | 0.350000 |
| `[0]` | 0.000000 | 0.000000 | 0.333333 | 0.000000 |
| `[1,1]` | 0.577500 | 1.000000 | 0.750000 | 0.510867 |
| `[0,0]` | 0.000000 | 0.000000 | 0.250000 | 0.000000 |
| `[1,0]` | 0.227500 | 0.500000 | 0.500000 | 0.263379 |
| `[0,1]` | 0.350000 | 0.500000 | 0.500000 | 0.247487 |

P1 给出最极端的 single-correct value（1.0）；这是“更极端的稀疏数据估计”，不构成真实学生 overconfidence 的心理测量结论。P2 的对称 prior 缓和单条 evidence 的极端性，P0/P3 从 0 起点保持更保守的数值更新。

## Long-run behavior

这只是理论 characterisation；当前一个 concept 不保证有十个独立 reviewed templates。

| 10 条 homogeneous signal | P0 | P1 | P2 Beta(1,1) | P3 |
| --- | ---: | ---: | ---: | ---: |
| ten correct | 0.986537 | 1.000000 | 0.916667 | 0.860958 |
| ten incorrect | 0.000000 | 0.000000 | 0.083333 | 0.000000 |

## Alpha sensitivity

只比较透明固定 alpha `0.2/0.35/0.5`，未调参。对 `[1,0]`，final 为 `0.160000/0.227500/0.250000`；对 `[0,1]`，为 `0.200000/0.350000/0.500000`。`[1,1,0,0]` 的 permutation range 分别为 `0.129600/0.333506/0.562500`。因此“固定 alpha 的顺序性”不是 0.35 特例，较大的 alpha 同时增加近期响应和 order sensitivity。

## Prior sensitivity

| Sequence | Beta(1,1) | Beta(2,2) |
| --- | ---: | ---: |
| `[1]` | 0.666667 | 0.600000 |
| `[0]` | 0.333333 | 0.400000 |
| `[1,1]` | 0.750000 | 0.666667 |
| `[0,0]` | 0.250000 | 0.333333 |
| `[1,0]` / `[0,1]` | 0.500000 | 0.500000 |
| ten correct | 0.916667 | 0.857143 |

更强对称 prior 只影响样本稀少时向 0.5 的收缩与收敛速度；两者都严格排列不变。本研究不能说明哪个 prior 更真实。

## Recommendation threshold sensitivity

在所有 126 条 binary sequences 上，将每项 policy final mastery 放入仅 `breadth_first_search` 处于 threshold 边界、其余 concepts 为 1 的 synthetic learner state，并调用真实 `recommend_next_concept()`。发现 44/126 条（34.9%）存在 policy threshold disagreement；这 44 条均实际使 recommendation 在 `breadth_first_search` 与 `None` 间改变。

最短 example 是 `[1]`：P0/P3=0.35（推荐 BFS），P1=1.0、P2=0.666667（均不再推荐 BFS）。这是有限、特意构造的 near-threshold deterministic test-set proportion，不是产品流量中的概率。

## Prerequisite-sensitive cases

对真实 prerequisite edge，令 dependent=0，其他 concepts=1，将 prerequisite 的 single-correct policy score 放入真实 recommender：

| edge | P0 / P3 recommendation | P1 / P2 recommendation |
| --- | --- | --- |
| `frontier_and_explored_set → breadth_first_search` | `frontier_and_explored_set` | `breadth_first_search` |
| `breadth_first_search → completeness_optimality_complexity` | `breadth_first_search` | `completeness_optimality_complexity` |
| `uniform_cost_search → informed_search_and_heuristics` | `uniform_cost_search` | `informed_search_and_heuristics` |

因此 estimator policy 在 threshold 附近可经 prerequisite backtracking 放大为不同学习路径；这并不表示其中一条路径更有效。

## Policy property matrix

| Policy | Order invariance | Recent responsiveness | Sparse-data conservatism | Long-run stability | Contradictory stability | Interpretability | Parameter dependence | Recommendation stability near threshold | Current implementation compatibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | LOW | HIGH | HIGH | MEDIUM | LOW | HIGH | one fixed alpha | LOW | exact current |
| P1 | HIGH | LOW after more evidence | LOW | HIGH | HIGH | HIGH | none | HIGH for permutations | research-only |
| P2 | HIGH | LOW after more evidence | MEDIUM | HIGH | HIGH | HIGH | explicit symmetric prior | HIGH for permutations | research-only |
| P3 | LOW but decaying | MEDIUM | HIGH | MEDIUM | MEDIUM | MEDIUM-HIGH | base alpha + floor | MEDIUM | research-only |

所有 policy 都是 deterministic、bounded `[0,1]`，且在同一 history 下追加 1 不会降低、追加 0 不会上升。P0 是唯一与当前实现完全兼容的 production baseline；其余均为 research-only。

## Counterfactual cases

工具固定 20 组高信息量、单因素 counterfactual pairs：4 组 order reversal、3 组 evidence count、4 组 latest evidence、5 组 additional/outcome balance、4 组 contradiction/equal-count order。每组保存左右 mastery、delta、threshold side 和由真实 recommender 得到的 recommendation。重点 pair 包括 `[1,0]↔[0,1]`、`[1,1,0,0]↔[0,0,1,1]`、`[0,0,0]→1` 与 `[0,0,0]→0`。

## Findings

1. 当前 P0 的 order sensitivity 随可比较 sequence 长度显著累积：n=6 最大 OSR 为 0.526169。
2. P1/P2 通过定义消除 permutation effect，但 P1 对单条正确证据给出 1.0；P2 以 prior 提供中等收缩。
3. P3 不是均值/P2 的改名：保留小幅 recency，但 n=6 最大 OSR 仅 0.039911，同时对晚到 signal 的响应低于 P0。
4. policy 差异会在 0.6 当前阈值附近实际改变 recommendation，并可被 prerequisite 规则进一步放大。

## Current-policy interpretation

展开 P0 递推可见，第 `k` 条过去 signal 的权重按 `0.35 × 0.65^k` 衰减，起始 state 的残余权重为 `0.65^n`。因此近期 evidence 固有地拥有较大权重；连续正确从 `0 → 0.35 → 0.5775 → 0.725375`，连续错误从零起保持零，而已有正 mastery 遇到后续错误会以同一 fixed alpha 向下移动。该解释描述 formula，不把 mastery 当作概率。

## Trade-offs

- P0：较高近期响应 ↔ 较高排列/近期依赖。
- P1：严格排列不变 ↔ 稀疏证据更极端、晚期响应更慢。
- P2：prior 收缩与稳定性 ↔ sparse behavior 对显式 prior 强度敏感。
- P3：降低 P0 顺序性 ↔ 仍有参数（base/floor）且牺牲一部分 recent responsiveness。

## Unexpected findings

在这个刻意 near-threshold 的有限序列集上，44/126 条 sequence 的 policy difference 都实际改变了真实 recommendation 输出；这比“数值不同但下游相同”的情形更强，但不能外推为真实学生使用比例。P3 的 n=3 最大 OSR 低于 n=2 是该递减 step 的有限长度现象，不应误读为全局单调定律。

## Implementation bugs found

0。没有发现违反 P6 已记录 production invariant 的 implementation bug，也没有修改生产逻辑。

## Valid claims

- 当前 fixed-step estimator 在 exhaustive deterministic sequences 上表现出可量化的 order sensitivity。
- P1/P2 通过其数学定义消除同 multiset permutation effect。
- aggregation policy 会改变稀疏证据数值与 threshold 侧；在受控 synthetic state 中这会改变真实 recommendation 输出。
- 本比较展示了 responsiveness-stability trade-off，并成功用 real workflow 证明 repeat/assistance gate 位于 policy 之前。

## Claims not supported

本研究不能证明任何 policy 估计真实知识、已校准、可预测考试、会改善学习、具备 psychometric validity，或应替换 production。它也不能证明 order invariance 天生优于 recency sensitivity，或 P0 的顺序性本身错误。

## Candidate hypotheses for P6c

H1：在真实 independent concept assessment、延迟保持与教师判断的约束下，prior-regularized、order-invariant accumulator 值得作为 future controlled human-validation candidate。

H2：在有真实“近期学习变化”外部标签时，P3-style decayed recency policy 可能是 P0/P1/P2 间可解释的折中基线。

二者都要求人本验证后才能成为 production decision。

## Human-validation requirements

未来需要独立 concept assessment、跨时间 repeated diagnostic observations、delayed retention、教师/专家判断、考试或任务表现、recommendation usefulness 与真实学习轨迹。应在预注册或至少事先固定的评估协议中比较，不得从本 synthetic audit 推断答案。
