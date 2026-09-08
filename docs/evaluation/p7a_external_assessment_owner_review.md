# P7a External Assessment Owner Review Preparation

> 审核性质：P7 research-only candidate 的对抗性内容审核准备。本文是
> Codex 的建议，不是负责人决定。所有候选仍为
> `assessment_status=pending_owner_review`、
> `human_review_status=pending_owner_review`，不得进入 production、普通学生 UI、
> learner-state evidence、exposure 或 recommendation。

## 审核方法

本轮逐题对照 production template、其 capability boundary、`course_chunks.json`，并
用 `pdftotext -layout` 核对以下授权精简 PDF 的实际 physical pages：Lec2 pp.31–35、
60–62；Lec3 pp.16–25；Lec4 pp.9–11；Lec5 pp.16–19；Lec6 pp.20、32。

每题执行 12 项攻击：source entailment、production overlap、memorization leakage、
construct alignment、difficulty、第二合理答案、隐含假设、干扰项、guessing cues、
capability boundary、future form role 和 human-study usefulness。`APPROVE`/`REVISE`/
`REJECT` 在本文中均表示 **OWNER_*_RECOMMENDED**，而不是
`APPROVE_FOR_HUMAN_PILOT`。

## Production-to-external capability map

| Concept | Production evidence capability | External candidates | P7a judgment |
| --- | --- | --- | --- |
| BFS | FIFO frontier；相等行动代价时最少步数与最低总代价关系 | depth claim / queue trace | 有一个可用 FIFO 候选；最优性题需重做。 |
| UCS | 按累计 `g(n)` 最小扩展 | accumulated cost / equal depth | 累计代价计算可用；等深题过近。 |
| A* | 计算 `f=g+h`；按最小 f 选择 | f computation / same-h g effect | 同 h 下 g 的作用可保留；min-f 计算题过近。 |
| Local search | 当前候选状态/邻域，而非完整路径或 frontier | timetable class / board representation | 均有构念或干扰项修订需要。 |
| Minimax | MAX/MIN 的 minimax value propagation | MIN value / two-level tree | 可作为即时与探索性较完整推理；还没有等难 delayed form。 |
| MCTS | 四阶段顺序 | backpropagation role / expansion role | 扩展题可用；回传题需补充分明的 source ref。 |

## First-pass verdict summary

| Item | Concept | Source | Construct alignment | Production overlap | Second-answer risk | Difficulty risk | Suggested role | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `p7_ext_bfs_depth_claim_a` | BFS | STRONG | ALIGNED | INDEPENDENT_CAPABILITY_SAMPLE | Low | MEDIUM_RISK | IMMEDIATE_BACKUP after revision | OWNER_REVISE_RECOMMENDED |
| `p7_ext_bfs_queue_trace_b` | BFS | STRONG | ALIGNED | INDEPENDENT_CAPABILITY_SAMPLE | Low | MEDIUM_RISK | IMMEDIATE_PRIMARY | OWNER_APPROVE_RECOMMENDED |
| `p7_ext_ucs_cost_accumulation_a` | UCS | STRONG | ALIGNED | INDEPENDENT_CAPABILITY_SAMPLE | Low | MEDIUM_RISK | IMMEDIATE_PRIMARY | OWNER_APPROVE_RECOMMENDED |
| `p7_ext_ucs_equal_depth_cost_b` | UCS | STRONG | ALIGNED | TOO_SIMILAR | Low | LOW_RISK | DO_NOT_USE | OWNER_REJECT_RECOMMENDED |
| `p7_ext_astar_f_computation_a` | A* | STRONG | ALIGNED | TOO_SIMILAR | Low | LOW_RISK | DO_NOT_USE | OWNER_REJECT_RECOMMENDED |
| `p7_ext_astar_component_change_b` | A* | STRONG | ALIGNED | COMPLEMENTARY_CAPABILITY | Low | LOW_RISK | IMMEDIATE_PRIMARY | OWNER_APPROVE_RECOMMENDED |
| `p7_ext_local_search_neighbor_a` | Local search | STRONG | SLIGHTLY_BROADER | INDEPENDENT_CAPABILITY_SAMPLE | Low | MEDIUM_RISK | IMMEDIATE_BACKUP after revision | OWNER_REVISE_RECOMMENDED |
| `p7_ext_local_search_representation_b` | Local search | STRONG | ALIGNED | COMPLEMENTARY_CAPABILITY | Medium | LOW_RISK | IMMEDIATE_BACKUP after revision | OWNER_REVISE_RECOMMENDED |
| `p7_ext_minimax_min_node_a` | Minimax | STRONG | ALIGNED | COMPLEMENTARY_CAPABILITY | Low | LOW_RISK | IMMEDIATE_PRIMARY | OWNER_APPROVE_RECOMMENDED |
| `p7_ext_minimax_two_level_b` | Minimax | STRONG | SLIGHTLY_BROADER | INDEPENDENT_CAPABILITY_SAMPLE | Low | MEDIUM_RISK | TRANSFER_EXPLORATORY | OWNER_APPROVE_RECOMMENDED |
| `p7_ext_mcts_backpropagation_a` | MCTS | ADEQUATE | ALIGNED | COMPLEMENTARY_CAPABILITY | Low | LOW_RISK | DELAYED_PARALLEL after source revision | OWNER_REVISE_RECOMMENDED |
| `p7_ext_mcts_expand_untried_child_b` | MCTS | STRONG | ALIGNED | COMPLEMENTARY_CAPABILITY | Low | LOW_RISK | IMMEDIATE_PRIMARY | OWNER_APPROVE_RECOMMENDED |

汇总：**6 approve、4 revise、2 reject、0 blocked**。这里的 `blocked=0` 仅指
这 12 道题均有课程材料可追溯；不意味着 12 道都适合人体研究。

## Second-pass adversarial audit

第二轮以 skeptical reviewer 身份重新攻击 4 题：

| Item | First-pass | 最强反对理由 | Second-pass |
| --- | --- | --- | --- |
| `p7_ext_astar_f_computation_a` | REJECT | 与 production `verify_astar_min_f_choice_v1` 同为“代入 g+h 后选最小 f”；仅将四节点缩为两节点，解题路径更短。 | REJECT confirmed：`TOO_SIMILAR`。 |
| `p7_ext_local_search_representation_b` | REVISE | “最需要保留”可能被误读为实现上的唯一内存要求；有些 local-search variant 会保存额外信息。 | REVISE confirmed：应限定为课件的 candidate/neighborhood framing。 |
| `p7_ext_minimax_two_level_b` | APPROVE | 比 production 单层 MAX 多一层 MIN 推理，可能不再是等难平行 form。 | APPROVE only as `TRANSFER_EXPLORATORY`；不可冒充 delayed parallel。 |
| `p7_ext_mcts_backpropagation_a` | REVISE | 所列 p.32 主要是图示，文本恢复很弱；正确命题由 p.20 的阶段定义直接支持，但它未列为 source ref。 | REVISE confirmed：补 p.20 后再审核。 |

## Independence metric

自动 validator 已确认：identical stem collisions=0、identical full option-set
collisions=0、production template-ID collisions=0。人工审计补充发现：

- same closed-instance structure / cosmetic risk 高：UCS `equal_depth_cost_b`、A*
  `f_computation_a`；
- same answer-ID pattern（仅描述，不构成独立性证据）：候选正确选项为
  `a=6, b=4, c=2, d=0`，未来修订批次应顺便平衡位置；
- source locator 缺口：MCTS `backpropagation_a` 应加入 Lec6 p.20；
- 候选题不是自动形成 parallel form；“同 concept”并不等于“可在 immediate/delayed
  之间互换”。

## External Item 1 Owner Review Pack

**ID / concept / suggested role：** `p7_ext_bfs_depth_claim_a` / BFS /
`IMMEDIATE_BACKUP after revision`。

**Production capability compared：** `verify_bfs_equal_cost_condition_v1` 的“相等行动
代价时，最少步数路径也保证最低总代价”。

**Question and choices：** 每条边代价为 1，BFS 首次到达 G 使用 3 条边。a 最少边数且
该条件下总代价最低；b BFS 总按累计代价；c 单位代价也不能推出总代价；d 无环才可到达。
**Correct answer：** a。

**Course source / basis：** Lec2 p.35 明示 BFS 最优性为 Yes，条件是所有行动代价相同；
pp.31–34 明示逐层扩展，故 source entailment 为 **STRONG**。

**Why correct；distractors：** a 同时使用单位代价与最浅层结论。b 把 UCS 规则加给 BFS，
是 `PLAUSIBLE_MISCONCEPTION`；c 否认给定条件，是 `MISLEADING`；d 将可达性归因于无环，
是 `WEAK`。

**Construct / independence：** 与 production 对齐，但 production 的正确选项“所有动作或边
代价相同”几乎直接指向 a；新题只是把该条件放入单位代价实例。overlap 可称 independent
instance，但 memorization leakage 为 **HIGH**，而非充分独立 criterion。

**Assumptions / difficulty / guessing：** 假定常规 BFS 的首次到达按层、边均为 1；题面已
足够。两步推理，比 production 略宽，`MEDIUM_RISK`。a 最长且唯一完整保留条件，guessing
risk 为 **HIGH**。

**Correct answer supports / does not support：** 支持该实例下的条件性 BFS 最优结论；不支持
任意边权、UCS 规则或 BFS 的完整性能性质。**Second answer：** 无合理第二答案。**Serious
risk：** 记住 production 的 equal-cost 选项即可作答。**Terra recommendation：REVISE**。

## External Item 2 Owner Review Pack

**ID / concept / role：** `p7_ext_bfs_queue_trace_b` / BFS / `IMMEDIATE_PRIMARY`。

**Production capability：** `verify_bfs_frontier_choice_v1` 的 FIFO frontier 选择。
**Question and choices：** P、Q 依序入空 frontier；扩展 P 后依序加入 R、S，Q 未扩展；下一步
选 Q/R/S/P。**Correct answer：** a，Q。

**Source / basis：** Lec2 pp.31–34 直接说明本层节点在下一层前均先扩展，图示 search tiers
支持队列式层序追踪；**STRONG**。

**Distractors：** R、S 忽略 Q 的先入队顺序，均为 `PLAUSIBLE_MISCONCEPTION`；P 已扩展，
为 `WEAK`。无 tie-breaking 或 graph-search 前提。**Second answer：** 无。

**Construct / overlap：** 仍测 FIFO，但须处理一次扩展后的 queue state；不是仅改 A/B/C 名称，
`INDEPENDENT_CAPABILITY_SAMPLE`。记忆 production 的“先入先出”会帮助，但那正是构念，
leakage 为 **MEDIUM**。比单步 production 多一个队列更新，难度 `MEDIUM_RISK`。

**Boundary：** 支持按 FIFO 追踪 BFS frontier；不支持 BFS 最优性、visited set 或 DFS 的所有
性质。**Guessing：** 中低；选项标签短且平行。**Immediate/delayed：** 可以 immediate，但与
Item 1 不是同一 micro-capability 的 delayed parallel。**Terra recommendation：APPROVE**。

## External Item 3 Owner Review Pack

**ID / concept / role：** `p7_ext_ucs_cost_accumulation_a` / UCS / `IMMEDIATE_PRIMARY`。

**Production capability：** `verify_ucs_min_g_choice_v1` 的已给 g 值的 min-g expansion。
**Question and choices：** X=2+4，Y=5，Z=1+7；选 X/Y/Z 或按步数选 X。**Correct answer：** b，Y。

**Source / basis：** Lec2 pp.60–62 直接说明 UCS 扩展路径消耗最小的节点，并给出多段边代价
搜索图；**STRONG**。

**Distractors：** a 正确计算 6 但未选最小，`PLAUSIBLE_MISCONCEPTION`；c 只看最后一步，
`PLAUSIBLE_MISCONCEPTION`；d 只看步数，`PLAUSIBLE_MISCONCEPTION`。无并列，故无第二答案。

**Construct / overlap：** 同一 UCS capability，但先累加再比较，production 不要求该算术步骤；
`INDEPENDENT_CAPABILITY_SAMPLE`，memorization leakage **MEDIUM**。增加一次小算术，难度
`MEDIUM_RISK`，没有超出 source-supported construct。

**Boundary：** 支持该 frontier 的累计代价比较；不支持 UCS 完备性或复杂度。**Guessing：**
低至中，所有错误项均有明确误解。**Immediate/delayed：** 当前可作 immediate；Item 4 不适合
作其 delayed parallel。**Terra recommendation：APPROVE**。

## External Item 4 Owner Review Pack

**ID / concept / role：** `p7_ext_ucs_equal_depth_cost_b` / UCS / `DO_NOT_USE`。

**Production capability：** production 直接在 A/B/C 的既给 g 值中选择最小 g。**Question and
choices：** 两路径均两条边，M g=9，N g=4；选 M/N/先生成/需 h。**Correct answer：** b，N。

**Source / basis：** Lec2 pp.60–62 是 **STRONG**。a 是深度/任意选择误解，c 是生成顺序误解，
d 是将 A* heuristic 加给 UCS；均无第二答案。

**Construct / overlap：** 虽然题面加了“相同边数”，实质仍是“两个既给 g，选择较小者”，与
production 的 answer inference path 相同，且更少节点。是 `TOO_SIMILAR`，memorization leakage
**HIGH**，difficulty `LOW_RISK`（过易）。

**Boundary / guessing：** 支持 min-g，不支持 BFS/UCS 一般比较；b 唯一具有课程术语，其他项
弱，guessing **HIGH**。**Immediate/delayed：** 不可使用。**Most serious risk：** cosmetic
numeric rewrite。**Terra recommendation：REJECT**。

## External Item 5 Owner Review Pack

**ID / concept / role：** `p7_ext_astar_f_computation_a` / A* / `DO_NOT_USE`。

**Production capability：** `verify_astar_min_f_choice_v1` 已要求多个节点代入 `f=g+h` 后选择
最小 f；`verify_astar_f_value_v1` 已要求单节点相加。**Question and choices：** R g=3,h=4；S
g=5,h=1；选择 R/S 的不同理由。**Correct answer：** c，S（6 小于 7）。

**Source / basis：** Lec3 p.18 定义 f、g、h，pp.16–17 给出 A* 图例，故 **STRONG**。a 含自相
矛盾不等式，b 只看 h，d 只看 g；无第二答案。

**Construct / overlap：** 解题过程完整复用 production：相加后选最小 f；只把四个节点缩为两个。
`TOO_SIMILAR`，memorization leakage **HIGH**，且难度比 production 更低（`LOW_RISK` 但过易）。

**Boundary / guessing：** 支持计算并比较 f；不支持 admissibility/optimality。a 的错误算式与其余
明显单指标 distractors 使 c 成为显著正确项，guessing **HIGH**。**Immediate/delayed：** 不可
使用。**Terra recommendation：REJECT**。

## External Item 6 Owner Review Pack

**ID / concept / role：** `p7_ext_astar_component_change_b` / A* / `IMMEDIATE_PRIMARY`。

**Production capability：** f 计算与 min-f selection。**Question and choices：** h 都为 3，T
g=2，U g=6；为什么优先 T？a f=5<9；b 随机；c T h 更小；d 只比较 g。**Correct answer：** a。

**Source / basis：** Lec3 p.18 直接定义 `f=g+h`、g 的路径开销含义；**STRONG**。b、c、d 分别是
`WEAK`、`PLAUSIBLE_MISCONCEPTION`、`PLAUSIBLE_MISCONCEPTION`；无第二答案。

**Construct / overlap：** 固定 h，隔离“g 的改变通过 f 改变选择”的 capability，未复用四节点
min-f 实例；`COMPLEMENTARY_CAPABILITY`，memorization leakage **MEDIUM**。一步计算，难度
`LOW_RISK`，但正好补 production 没有单独暴露的 component role。

**Boundary：** 支持在相同 h 下比较 f；不支持 A* 只按 g、启发式可采纳性或最优性。**Guessing：**
中等，a 含数值但其余错误各对应典型混淆。**Immediate/delayed：** 可以 immediate；缺少可互换的
delayed parallel。**Terra recommendation：APPROVE**。

## External Item 7 Owner Review Pack

**ID / concept / role：** `p7_ext_local_search_neighbor_a` / Local search /
`IMMEDIATE_BACKUP after revision`。

**Production capability：** 当前 candidate solution/最终状态质量，而非完整路径或 systematic
frontier。**Question and choices：** 课程表每次移动一门课、比较邻居冲突数、保留当前安排；
识别局部搜索/树搜索/图搜索/UCS。**Correct answer：** a。

**Source / basis：** Lec4 pp.9–11 直接用当前状态、neighborhood、评价近邻和移动获取更好解；
**STRONG**。b、c、d 分别把树路径、全 explored set、累计路径代价错误归入 local search，均为
`PLAUSIBLE_MISCONCEPTION`，无第二答案。

**Construct / overlap：** 新课程表情境需从行为识别 algorithm family，比 production 定义对比
略宽，`SLIGHTLY_BROADER`；不是 Hill Climbing，因为题面不说只接受更优且整体问的是上位
Local Search。overlap 为 independent applied sample，memorization leakage **MEDIUM**，难度
`MEDIUM_RISK`。

**Risk / revision：** “保留一个当前安排”及三个使用“必须/必然”的错误项过度提示 a；应让干扰项
更接近真实 search-family 混淆，同时继续不把 Local Search 等同 Hill Climbing。**Boundary：**
支持识别 candidate/neighborhood framing；不支持所有 local-search 变体的接受规则。**Terra
recommendation：REVISE**。

## External Item 8 Owner Review Pack

**ID / concept / role：** `p7_ext_local_search_representation_b` / Local search /
`IMMEDIATE_BACKUP after revision`。

**Production capability：** candidate-state focus versus full path/frontier. **Question and
choices：** 低冲突棋盘局部搜索，从当前布局生成移动一个棋子的邻居；核心对象是当前布局及
邻域/完整历史/frontier/全部 explored。**Correct answer：** a。

**Source / basis：** Lec4 pp.9–11 **STRONG**。b、c、d 是完整路径、系统 frontier、全状态枚举
的 `PLAUSIBLE_MISCONCEPTION`，无其它列出项可合理正确。

**Construct / overlap：** 对齐 production 的表示边界，采用独立棋盘实例；
`COMPLEMENTARY_CAPABILITY`，leakage **MEDIUM**，difficulty `LOW_RISK`。

**Missing assumption / second-answer risk：** 题干“最需要保留”可被理解为所有实现都只保存一份
当前状态；实际 local-search variant 可额外保存 tabu list、temperature 或评价信息。尽管这些
不在列出的错误项中，措辞使 second-answer/construct-boundary risk 为 **MEDIUM**。修订时应明确
“按课件的总体 framing，最核心的搜索表示”。

**Boundary：** 支持 candidate/neighborhood focus；不支持关于所有 local-search 实现内存的绝对
断言。**Immediate/delayed：** 当前不宜与 Item 7 当作严格平行 form。**Terra recommendation：REVISE**。

## External Item 9 Owner Review Pack

**ID / concept / role：** `p7_ext_minimax_min_node_a` / Minimax / `IMMEDIATE_PRIMARY`。

**Production capability：** production 对 MAX 在两个已给 minimax 值中取最大；本题测互补的
MIN return value。**Question and choices：** MIN 的终局子值为 6、2、5，返回 6/5/2/需 alpha-beta。
**Correct answer：** c，2。

**Source / basis：** Lec5 pp.16–19 明示 terminal utility、MAX 取 max、MIN 取 min；
**STRONG**。a、b 为 `PLAUSIBLE_MISCONCEPTION`（MAX 或任意挑值），d 为 `MISLEADING`
（将 alpha-beta 前提错误加入 minimax）；无第二答案。

**Construct / overlap：** 与 production 同一 minimax propagation 但切换 MIN 角色，
`COMPLEMENTARY_CAPABILITY`；不是数值换皮。memorization leakage **LOW–MEDIUM**，难度
`LOW_RISK`。**Guessing：** 中等，数值排序可能让学生只猜最小，但这就是需测的规则。

**Boundary：** 支持单一 MIN 层的值回传；不支持完整树、alpha-beta 或游戏策略的广泛 mastery。
**Immediate/delayed：** 可 immediate；Item 10 更适合 transfer 而非同难 delayed。**Terra
recommendation：APPROVE**。

## External Item 10 Owner Review Pack

**ID / concept / role：** `p7_ext_minimax_two_level_b` / Minimax / `TRANSFER_EXPLORATORY`。

**Production capability：** 单层 MAX 从 3/5 中取 5。**Question and choices：** root MAX；左 MIN
终局 3、8，右 MIN 终局 4、5；选左最大叶/右（左返3右返4）/错误 MIN rule/UCB。**Correct answer：** b。

**Source / basis：** Lec5 pp.16–19 的 minimax recursion、MAX/MIN 定义直接支持；**STRONG**。
a 是 `PLAUSIBLE_MISCONCEPTION`（贪心最大叶），c 是 `PLAUSIBLE_MISCONCEPTION`，d 是
`WEAK`；无第二答案，也无 tie。

**Construct / overlap：** 先做两个 MIN 再 root MAX，是独立两层 inference；
`INDEPENDENT_CAPABILITY_SAMPLE`。它比 production 多一层递归，`SLIGHTLY_BROADER`、
`MEDIUM_RISK`，但仍是直接课件 minimax，不能声称与单层 production 同难。

**Boundary / role：** 支持这个两层 closed tree 的 minimax propagation；不支持复杂 game-state
evaluation 或 alpha-beta。memorization leakage **LOW**；guessing 中低。应作为 transfer/exploratory
或 backup，不应伪装 delayed parallel。**Terra recommendation：APPROVE**。

## External Item 11 Owner Review Pack

**ID / concept / role：** `p7_ext_mcts_backpropagation_a` / MCTS /
`DELAYED_PARALLEL after source revision`。

**Production capability：** 四阶段顺序。**Question and choices：** rollout 结束后，如何让此前
选择路径的树节点利用结果：回传更新/重新随机且不更新/删除未访问子节点/最小 g 选择。
**Correct answer：** a。

**Source / basis：** Lec6 p.20 明确回溯会自底向上更新路径节点奖励均值和访问次数；p.32 是
对抗树图示且文本恢复弱。现有 JSON 仅列 p.32，故登记 source entailment 为 **ADEQUATE** 而非
STRONG：正确命题有课程依据，但 candidate 的 page-level citation 应补 p.20。

**Distractors：** b、c、d 分别是否定学习、无关删除、UCS 混淆，均 `PLAUSIBLE_MISCONCEPTION`
或 `WEAK`；无第二答案。**Construct / overlap：** 测阶段功能而非顺序，
`COMPLEMENTARY_CAPABILITY`，leakage **MEDIUM**，难度 `LOW_RISK`。

**Boundary：** 支持识别回传统计更新；不支持 UCB 公式或固定胜负统计解释。**Immediate/delayed：**
可与 expansion role 组成 concept-level complementary bundle，但非严格同 micro-capability 的
parallel form。**Terra recommendation：REVISE**（仅先修复 source ref，再做 owner review）。

## External Item 12 Owner Review Pack

**ID / concept / role：** `p7_ext_mcts_expand_untried_child_b` / MCTS / `IMMEDIATE_PRIMARY`。

**Production capability：** MCTS 四阶段顺序。**Question and choices：** 到达仍有未加入树的
合法子动作的节点，将新子节点加入树属于 selection/expansion/simulation/backpropagation。
**Correct answer：** b，expansion。

**Source / basis：** Lec6 p.20 明示 expansion 为所选节点生成新子节点，并说明实现可随机生成
一个或生成全部后继；p.32 另有过程图示。**STRONG**。

**Distractors：** a 是选择路径，c 是从新节点模拟，d 是沿路径更新，均为
`PLAUSIBLE_MISCONCEPTION`。题面已给“尚未加入树”，无第二答案。

**Construct / overlap：** 测 stage operational cue，不是重排四阶段；
`COMPLEMENTARY_CAPABILITY`，leakage **MEDIUM**，difficulty `LOW_RISK`。**Guessing：**
中等，英文阶段词可为提示，但每项均为课程术语且行为描述区分清楚。

**Boundary：** 支持 expansion 的定义；不支持 MCTS 全流程熟练、UCB selection 或 AlphaGo。
**Immediate/delayed：** 可 immediate；Item 11 修复后是概念级补充，但尚非严格 parallel pair。
**Terra recommendation：APPROVE**。

## Concept-pair assessment

| Concept | 两题独立性 | Immediate/delayed 结论 | 是否需要第三题 / 建议 |
| --- | --- | --- | --- |
| BFS | 一个 FIFO trace、一个 equal-cost 应用；不同 micro-capability。 | `PAIR_NOT_READY`。 | 修订 Item 1 后再设计与 FIFO 或最优性之一等难的真正 parallel form。 |
| UCS | Item 3 累计计算；Item 4 是 near-copy。 | `PAIR_NOT_READY`。 | 淘汰 Item 4，设计非 min-g list 的独立构念实例。 |
| A* | Item 6 为 component-role；Item 5 near-copy。 | `PAIR_NOT_READY`。 | 淘汰 Item 5，设计非直接 min-f 计算的等难 form。 |
| Local search | 两题均围绕 candidate/neighborhood，但分别是分类与表示。 | `PAIR_NOT_READY`。 | 先修措辞/干扰项；再决定是否保留两题作为同次 bundle。 |
| Minimax | MIN 单层与两层 MIN→MAX。 | immediate/transfer 可用，非 delayed parallel。 | 需要一题与 Item 9 等难的 delayed MIN/MAX form。 |
| MCTS | expansion 与 backpropagation 为不同阶段作用。 | `PAIR_NOT_READY`。 | Item 11 先补 source；再设计同一阶段或等效复杂度的 delayed form。 |

没有 concept 目前拥有可以无保留用于 immediate / delayed 的严格平行对。P7 未来的
external score 可以是透明的多题 `correct/total` concept bundle，但若只施测一题则只是 0/1
独立 course-grounded performance，信息量有限，不是 ground-truth mastery。

## Study A concept subset recommendation

保留原有六 concept 作为 **候选研究范围**，但不建议以当前 bank 直接开展 Study A。Minimax
具有最干净的 immediate+exploratory coverage；BFS/UCS/A*/Local/MCTS 需要先处理上述
revision/replacement。不要新增 concept 来掩盖当前 parallel-form 缺口。

## Human-study readiness assessment

P7 的 **LEVEL 1（synthetic pipeline validated）仍成立**。P7a 不能升至 LEVEL 2：外部题未
获负责人 final owner decision，且 6 个 concept 均未形成经过审核的 immediate/delayed parallel
pair。P7a 的恰当产物是一个能让负责人逐题拍板的审查包，而不是 human-study ready 声明。

## Required owner decisions

1. 对 6 个 `OWNER_APPROVE_RECOMMENDED` 逐题作最终决定；
2. 决定 4 个 `OWNER_REVISE_RECOMMENDED` 是否值得小修；
3. 确认拒绝 UCS Item 4 与 A* Item 5，或要求重设计；
4. 决定 Study A 是否采用同次 concept bundle，或等待真正 immediate/delayed forms；
5. 在任何真人研究前完成实际的 consent、teacher/institution approval 检查。
