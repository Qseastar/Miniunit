# P5b Owner Review Preparation：Adversarial Content Audit

本文件是独立的负责人决策材料，不是 promotion 记录。审核对象仍为
`data/candidate_templates/search_algorithms_p5b_candidates.json` 中的 8 个
`candidate_draft`，candidate JSON、production bank、scorer、mastery 和 evidence
pipeline 在本轮均未修改。

## Pre-review state

- Branch：`feature/p5b-reviewed-diagnostic-expansion`
- production：20
- P5b pending candidates：8
- blocked slots：1（既有 UCS lower-cost frontier update）
- concepts：26
- SQLite schema：3
- 工作区中已有上一轮 P5b 未提交修改；本轮未覆盖或清理这些修改。

## Review methodology

每题同时核对 candidate JSON、对应 chunk、授权 PDF physical pages，并执行：

1. source entailment；
2. 为每个错误选项寻找最强辩护；
3. 检查题面遗漏的角色、条件、数值和过程假设；
4. 核对课件术语；
5. 检查 single-choice 是否封闭；
6. 评估 distractor 是真实误解还是明显排除项；
7. 收窄答对后可支持的能力边界；
8. 与 20 道 production 做 overlap 比较；
9. 以学生刚学完课件的视角检查可读性；
10. 尝试用关键词、选项长度、排除法和常识猜中答案。

结论标签只使用 `OWNER_APPROVE_RECOMMENDED`、`OWNER_REVISE_RECOMMENDED`、
`OWNER_REJECT_RECOMMENDED` 和 `BLOCKED_BY_EVIDENCE`。

## 8-candidate owner review table

| Candidate | Primary | Source strength | Second answer risk | Missing-assumption risk | Terminology | Distractors | Readability | Boundary | Overlap | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| `verify_local_search_final_state_focus_v1` | `local_search` | STRONG | low | medium: “通常”仍较宽 | ACCEPTABLE | WEAK_DISTRACTOR | ACCEPTABLE | 窄但可再收窄 | NOVEL | OWNER_REVISE_RECOMMENDED |
| `verify_hill_climbing_stop_at_local_best_v1` | `hill_climbing` | STRONG | low | low | CLEAR | PLAUSIBLE_MISCONCEPTION | CLEAR | 窄 | NOVEL | OWNER_APPROVE_RECOMMENDED |
| `verify_simulated_annealing_worse_successor_v1` | `simulated_annealing` | STRONG | low | low | CLEAR | PLAUSIBLE_MISCONCEPTION | CLEAR | 窄 | NOVEL | OWNER_APPROVE_RECOMMENDED |
| `verify_evolutionary_search_parent_cycle_v1` | `evolutionary_search` | ADEQUATE | medium: variant 可能省略某阶段 | medium | ACCEPTABLE | PLAUSIBLE_MISCONCEPTION | ACCEPTABLE | 窄 | NOVEL | OWNER_REVISE_RECOMMENDED |
| `verify_minimax_max_min_value_choice_v1` | `minimax_search` | STRONG | none in closed instance | low | CLEAR | PLAUSIBLE_MISCONCEPTION | CLEAR | 很窄 | NOVEL | OWNER_APPROVE_RECOMMENDED |
| `verify_alpha_beta_prune_when_bounds_cross_v1` | `alpha_beta_pruning` | STRONG | low | low: 题面已给出 crossed bounds | CLEAR | PLAUSIBLE_MISCONCEPTION | ACCEPTABLE | 很窄 | NOVEL | OWNER_APPROVE_RECOMMENDED |
| `verify_mcts_four_stage_order_v1` | `monte_carlo_tree_search` | STRONG | none | low | CLEAR | PLAUSIBLE_MISCONCEPTION | CLEAR | 很窄 | NOVEL | OWNER_APPROVE_RECOMMENDED |
| `verify_ucb_upper_bound_selection_v1` | `upper_confidence_bound` | STRONG | low | medium: 不涉及未访问动作策略 | CLEAR | PLAUSIBLE_MISCONCEPTION | ACCEPTABLE | 窄 | NOVEL | OWNER_APPROVE_RECOMMENDED |

## Candidate 1 review pack

### `verify_local_search_final_state_focus_v1`

题干：

> 按照课件对局部搜索的介绍，局部搜索通常主要关心什么？

选项：

- A：从初始状态出发搜索并保留每一条完整路径
- B：为所有候选节点选择一种固定的 frontier 容器
- C：证明从初始状态到目标的完整路径一定是全局最优
- D：最终返回的状态是否达到目标，而不是完整路径本身

当前正确答案：D。

核心课程证据：Lec4 pp.9–11，`lec4_local_search_state_neighbors`。课件直接对比：局部搜索在很多问题中只关心最终返回状态是否达到目标，不关心从初始状态出发的完整路径；它评价当前状态的邻域。

为什么正确：D 与 p.11 的关注点直接一致。它只描述目标判定与路径是否为主要对象，不声称局部搜索一定全局最优。

为什么其他三个错误：

- A 把局部搜索误说成系统保存完整路径的路径搜索。
- B 把实现容器混成局部搜索的定义。
- C 把“关注最终状态”过度升级为“证明全局最优”。

最危险的歧义：课件说的是“很多问题中”而非所有局部方法都不保存路径；题目使用“通常”是合理缓冲，但仍可能让学生把整个 `local_search` 概念概括成“只保留一个状态”。此外 A–C 过于明显，D 的最长解释和“而不是”结构会让题目可被排除法猜中。

答对最多证明：理解本课程中局部搜索与完整路径搜索的关注点区别。

答对不能证明：掌握爬山、模拟退火、演化搜索、全局最优、收敛性或任何具体邻域策略。

最终建议：`OWNER_REVISE_RECOMMENDED`。

建议修订（不在本轮执行）：把题干绑定到“Lec4 所描述的局部搜索问题”，并把干扰项改为相邻但可区分的表述，例如“每一步都必须保存完整路径”“必须按 frontier 的固定顺序扩展”“停止时即可证明全局最优”，避免三个明显的非定义选项。

## Candidate 2 review pack

### `verify_hill_climbing_stop_at_local_best_v1`

题干：

> 在课件描述的基本爬山法循环中，如果当前状态的邻域里没有更好的解，下一步应怎样处理？

选项：

- A：移动到一个更差的邻居，直到找到目标
- B：把所有邻居的完整路径加入 frontier
- C：停止搜索
- D：无条件随机重启并把它当作基本循环的一部分

当前正确答案：C。

核心课程证据：Lec4 p.12（chunk 覆盖 pp.12–16）直接列出“移动到邻域内最好的解；如果没有更好的解，则停止搜索”。

为什么正确：C 是课件基本循环的直接停止条件。

为什么其他三个错误：A 把基本爬山法改成接受较差移动；B 把局部搜索改成完整路径 frontier；D 把课件随后讨论的随机重启变体误当基本规则。

最危险的歧义：题目不要求学生判断停止点是不是全局最优，也没有把 plateau/shoulder 说成“算法能识别的全局性质”。题干明确“基本循环”，因此随机重启不能构成第二答案。

答对最多证明：能识别基本 hill-climbing 的停止条件。

答对不能证明：全局最优、收敛性、随机重启效果或模拟退火。

最终建议：`OWNER_APPROVE_RECOMMENDED`。

## Candidate 3 review pack

### `verify_simulated_annealing_worse_successor_v1`

题干：

> 按照课件对模拟退火的描述，当候选后继状态比当前状态更差时，算法通常怎样处理？

选项：

- A：永远拒绝较差后继
- B：永远接受较差后继
- C：只接受邻域中评价最高的后继
- D：按概率决定是否接受；温度降低后随机性通常减弱

当前正确答案：D。

核心课程证据：Lec4 pp.17–19，`lec4_simulated_annealing`。p.19 直接区分更优后继的直接跳转、较差后继的概率决定，以及随温度降低而减弱的随机性。

为什么正确：D 同时保留了“较差也可能接受”和“温度调节随机性”两个课件事实。

为什么其他三个错误：A 排除了模拟退火缓解局部最优的随机性；B 把概率接受夸大为无条件接受；C 描述的是贪心式只取最优邻居而不是模拟退火规则。

最危险的歧义：温度和能量差的具体概率公式未给出，但题目只问定性规则，未把“按概率”误写成固定概率或必然接受。

答对最多证明：理解较差后继的定性接受规则和温度—随机性关系。

答对不能证明：会计算接受概率、选择冷却函数、保证全局最优或调参。

最终建议：`OWNER_APPROVE_RECOMMENDED`。

## Candidate 4 review pack

### `verify_evolutionary_search_parent_cycle_v1`

题干：

> 课件描述的演化算法搜索循环通常如何从当前种群产生后代？

选项：

- A：按适应度选择亲本，再通过杂交和随机突变产生后代
- B：只保留一个当前状态，并移动到它最好的邻居
- C：完全随机生成后代，不评价适应度
- D：复制适应度最低的个体，且不改变其表示

当前正确答案：A。

核心课程证据：Lec4 pp.20–25，`lec4_evolutionary_search_cycle`。课件展示种群、适应度相关选择、杂交、随机突变和下一代循环。

为什么正确：A 概括了本课件示例的选择—杂交—突变循环。

为什么其他三个错误：B 是单状态邻域移动；C 删除适应度评价；D 与课件“适应度越高，产生后代概率越大”相反。

最危险的歧义：不同 evolutionary algorithm variant 可能不使用相同的交叉/突变组合；题干“通常”比“本课件所示循环”更宽。A 同时塞入三个术语，学生也可能靠术语密度猜中。

答对最多证明：能复述本课程演化搜索示例的基本循环。

答对不能证明：掌握所有演化算法变体、参数选择、收敛或最优性。

最终建议：`OWNER_REVISE_RECOMMENDED`。

建议修订（不在本轮执行）：题干改为“按照 Lec4 pp.20–25 展示的循环”，明确这是课程实例而非所有 evolutionary algorithms 的定义；可把一个干扰项改为“选择后直接复制亲本、不发生杂交或突变”，使区分更贴近真实流程。

## Candidate 5 review pack

### `verify_minimax_max_min_value_choice_v1`

题干：

> 在一个 MAX 节点，两个后继的 minimax 值分别为 3 和 5。按照课件中的 minimax 规则，MAX 节点应选择哪个后继？

选项：

- A：minimax 值为 3 的后继
- B：minimax 值为 5 的后继
- C：两个值的平均数 4
- D：总是选择数值更小的后继

当前正确答案：B。

核心课程证据：Lec5 pp.16–19，`lec5_minimax_search`。课件递归定义明确：MAX 取后继 minimax 值最大者，MIN 取最小者。

为什么正确：MAX 需要在 3 和 5 中取最大值 5。

为什么其他三个错误：A 是把 MAX/MIN 角色反转；C 不是 minimax 递归；D 是无条件取 MIN 值。

最危险的歧义：题面已给出“MAX”和“minimax 值”，没有 terminal utility 推导、平局或 tie-breaking 问题；这是封闭实例，不把 evaluation function 混成 terminal utility。

答对最多证明：能在给定 minimax 值的 MAX 节点做一次最大化选择。

答对不能证明：能从终局递归计算 minimax、处理深度截断或制定完整对抗策略。

最终建议：`OWNER_APPROVE_RECOMMENDED`。

## Candidate 6 review pack

### `verify_alpha_beta_prune_when_bounds_cross_v1`

题干：

> Alpha-Beta 搜索到某节点时已有 alpha=5、beta=4，且该节点尚有未访问后继。按照课件的剪枝条件，下一步应怎样处理？

选项：

- A：继续访问所有未访问后继，因为剪枝只能发生在叶节点
- B：把 alpha 和 beta 重置为负无穷和正无穷
- C：剪去该节点尚未访问的后继
- D：交换 alpha 与 beta 后再访问后继

当前正确答案：C。

核心课程证据：Lec5 pp.20–31，`lec5_alpha_beta_pruning`。p.30 直接写出 alpha>beta 时未访问后继可以剪枝，p.31 给出递归伪代码。

为什么正确：5>4，满足课件给出的 crossed-bound cutoff 条件。

为什么其他三个错误：A 否认 cutoff；B/D 虚构了课件没有的状态重置或交换操作。

最危险的歧义：标准实现中常见的局部条件也会写成 MAX 的 `v≥β` 或 MIN 的 `v≤α`；本题使用的是课件明确的节点 `alpha>beta` 表述，因此不依赖未给出的 MAX/MIN 角色。题面不测具体剪枝数量。

答对最多证明：能应用课程明确的 alpha>beta 剪枝条件。

答对不能证明：掌握 alpha/beta 更新、后继排序、剪枝效率或完整 minimax。

最终建议：`OWNER_APPROVE_RECOMMENDED`。

## Candidate 7 review pack

### `verify_mcts_four_stage_order_v1`

题干：

> 按照课件对蒙特卡洛树搜索（MCTS）的四阶段描述，哪个顺序正确？

选项：

- A：扩展 → 模拟 → 选择 → 回溯
- B：选择 → 扩展 → 模拟 → 回溯
- C：模拟 → 选择 → 扩展 → 回溯
- D：选择 → 模拟 → 回溯 → 扩展

当前正确答案：B。

核心课程证据：Lec6 p.20，`lec6_mcts_four_stages`，直接列出 selection、expansion、simulation、backpropagation。

为什么正确：B 与课件四阶段顺序完全一致。

为什么其他三个错误：A 把扩展置于选择前；C 从模拟开始；D 将回溯和扩展顺序颠倒。

最危险的歧义：题目确实是窄的顺序记忆题，但四个选项是同一组阶段的排列，不是无关胡说；不存在第二正确顺序。

答对最多证明：记住本课程 MCTS 的四阶段顺序。

答对不能证明：会实现 UCB、设计 rollout、解释对抗统计或判断策略质量。

最终建议：`OWNER_APPROVE_RECOMMENDED`。

## Candidate 8 review pack

### `verify_ucb_upper_bound_selection_v1`

题干：

> 按照课件对 UCB 的描述，下一步应优先选择哪类动作？

选项：

- A：估计上限 Q_k+δ(k) 最高的动作
- B：只看经验平均收益 Q_k 最高的动作
- C：估计上限最低的动作
- D：无论收益如何都只选访问次数最少的动作

当前正确答案：A。

核心课程证据：Lec6 p.19，`lec6_upper_confidence_bound`。课件以 Q_k+δ(k) 表示估计范围上限，并说明优先选择上限较高的动作。

为什么正确：A 同时包含利用项和探索项的上限方向。

为什么其他三个错误：B 删除探索项；C 反转最大化方向；D 把探索项误化为“永远选择最少访问”。

最危险的歧义：课件没有在该题中展开未访问动作的初始化/无穷上限处理；但题目只问已定义 UCB 上限的选择方向，不声称覆盖该实现细节。

答对最多证明：理解 UCB 的上限选择规则。

答对不能证明：掌握完整 exploration/exploitation 政策、置信项计算或未访问动作初始化。

最终建议：`OWNER_APPROVE_RECOMMENDED`。

## Cross-candidate issues

1. **局部搜索题的干扰项质量**：A–C 大多是明显的“不是定义”选项，且 D 文字最长、包含“而不是”，存在排除法和长度线索。建议修订后再进入 owner approval。
2. **演化搜索题的范围**：Lec4 直接支持本课件展示的选择—杂交—突变流程，但“通常”可能被理解成所有演化算法的统一必需步骤。建议把题干锁定到 Lec4 示例。
3. **Alpha-Beta 术语差异**：课件明确使用 `alpha > beta`，而其他教材常见 `alpha >= beta` 或 MAX/MIN 局部 cutoff。当前数值为 5 和 4，避免了等号边界；若未来改成等号实例，必须重新审核。
4. **UCB 未访问动作**：本候选没有声称覆盖该实现细节，能力边界已明确；不构成当前 blocker。
5. 其余五题没有发现 source、唯一答案或题面必要条件的阻塞问题。

## Pre-revision answer-position audit

当前 8 题正确答案位置为 1–4 各两次。该分布不是审核依据，也不应阻止修订。题目质量优先于位置平衡；本轮未修改位置或 JSON。

## Source-evidence concerns

没有 `INSUFFICIENT` source。最强证据是 MCTS p.20、UCB p.19、hill-climbing p.12 和 Alpha-Beta p.30–31 的直接规则。Local search 和 evolutionary 的证据足够支持当前窄能力，但题干范围需更精确。

## Capability-boundary concerns

所有 candidate 都把能力边界限制到一次规则识别或封闭实例，不声称完整掌握算法。需要修订的两题分别是：local search 的整体概括范围、evolutionary cycle 对变体的约束。

## Which candidates should be promoted now?

在负责人最终审核前，不建议立即 promotion。若仅按本次 adversarial audit 排序，5 个直接规则题和 3 个封闭/阶段题中，除第 1、4 题外的 6 题达到 `OWNER_APPROVE_RECOMMENDED`，但仍须负责人批准、保留现有 promotion gate 和新增 integration/repeat-policy 测试。

## Which candidates need revision?

- `verify_local_search_final_state_focus_v1`：修订干扰项和题干范围。
- `verify_evolutionary_search_parent_cycle_v1`：锁定 Lec4 示例循环，避免暗示所有演化变体都必须相同。

## Which candidates should be rejected?

没有题目达到 `OWNER_REJECT_RECOMMENDED`。没有新增 `BLOCKED_BY_EVIDENCE`；既有 UCS blocked slot 不变。

## Is the previous 8/8 approval still credible?

**PARTIALLY。**

前一轮的 8/8 `APPROVE pending owner review` 对 source 和 deterministic closure 基本成立，但在更严格的 owner-review 攻击下，第 1 题的 distractor/猜题风险和第 4 题的 variant scope 风险足以要求修订。因此不能再把 8/8 作为“现在全部可晋级”的结论；更准确的状态是 6 个 `OWNER_APPROVE_RECOMMENDED`、2 个 `OWNER_REVISE_RECOMMENDED`。

## Recommended owner decisions

1. 先不要 promotion 全部 8 题。
2. 负责人可优先审核并批准 6 个低风险候选。
3. 要求第 1、4 题完成建议修订后重新进行独立内容审核。
4. 不改变 production templates、mastery、recommendation、P5B、evidence gate、scorer semantics 或 repeat policy。

## Pre-revision Git diff/status

本轮只新增本审计文档；candidate JSON、production JSON、代码和测试均未修改。本轮未执行任何 Git 写操作。

## Blocking issues

没有工程阻塞。内容发布阻塞为：两题需要修订，且全部候选仍需负责人批准。

## Pre-revision final answers

1. 推荐立即 APPROVE：6 道（仅为 owner review recommendation，未 promotion）。
2. 推荐 REVISE：2 道。
3. 推荐 REJECT：0 道。
4. BLOCKED：0 道新增；既有 blocked slot 为1。
5. 风险最高：`verify_local_search_final_state_focus_v1`，因为干扰项弱且“通常”范围较宽。
6. 证据最强：`verify_mcts_four_stage_order_v1`，Lec6 p.20 直接列出完整四阶段顺序。
7. 最容易仅靠选项猜中：`verify_local_search_final_state_focus_v1`。
8. capability boundary 最窄：`verify_minimax_max_min_value_choice_v1`，只验证给定值的 MAX 选择。
9. 是否仍建议 8 道全部 promotion：否；先修订第1、4题并重新审核。
10. 是否修改 candidate JSON：否。
11. 是否修改 production：否。

## Revision Round

本节记录本轮仅针对两道候选的修订，保留上文作为修订前的审计历史。候选
`candidate_status` 仍为 `pending_human_review`，两道题以及其余六道题的
`review_status` 仍为 `candidate_draft`；没有执行 promotion。

### Local Search：修订前 → 修订后

- 修订前结论：`OWNER_REVISE_RECOMMENDED`。主要问题是题干“通常主要关心”范围偏宽，A–C 干扰项过于容易排除，正确项较长且带有“而不是”线索。
- 本轮修订：题干明确限定为“Lec4 对局部搜索的 framing”，把考查目标改为“评价当前状态的邻域，并移动到一个更好的近邻状态”；四个选项统一为过程描述，移除全局最优、完整路径和固定 frontier 等过度/明显表述。验收元数据同步改为 `neighbor_improvement`，并明确不推广到所有局部或种群方法。
- 新证据边界：Lec4 pp.9–10 支持当前状态—邻域评价—改进移动；p.11 仅作为最终状态/完整路径的上下文，不再作为题目唯一答案的主张。
- 修订后结论：`OWNER_APPROVE_RECOMMENDED`。题干和选项只支持一个答案；不声称路径最优、全局最优或收敛，也不存在第二个合理答案。

### Evolutionary Search：修订前 → 修订后

- 修订前结论：`OWNER_REVISE_RECOMMENDED`。主要问题是“通常”可能被理解为所有演化算法变体都必须采用同一流程。
- 本轮修订：题干明确限定为“Lec4 pp.20–25 展示的演化算法循环”，四个选项改为同一组四阶段的不同排列，正确顺序为“选择亲本 → 杂交 → 随机突变 → 形成下一代”。验收元数据将错误答案固定为现有选项 `mutation_before_crossover`，并明确不推广到所有变体。
- 新证据边界：Lec4 pp.20–25 支持该课件示例的阶段顺序；不声称所有演化算法、收敛性或全局最优性。
- 修订后结论：`OWNER_APPROVE_RECOMMENDED`。四个排列只有一个与课件示例一致，没有第二个合理答案；由于选项结构相同，长度/术语密度猜题风险降低。

### 两道修订题的十项对抗复核

复核顺序固定为：source entailment、alternate answer、distractor defense、scope、terminology、stem ambiguity、answer-length cue、guessing path、question-to-capability alignment、scorer/acceptance consistency。

| Attack | Local Search | Evolutionary Search |
|---|---|---|
| source entailment | PASS：pp.9–10 直接支持邻域评价与改进移动 | PASS：pp.20–25 直接支持四阶段循环 |
| alternate reasonable answer | NONE：其余选项不是该基本过程的等价表述 | NONE：只有正确阶段排列与课件示例一致 |
| strongest distractor | `frontier_systematic` 是可辩护的路径搜索混淆，但不描述局部邻域改进 | `mutation_before_crossover` 是真实阶段顺序误解 |
| scope overclaim | PASS：明确不推广到所有局部/种群方法 | PASS：明确只限 Lec4 示例，不推广所有变体 |
| terminology | PASS：current state、neighborhood、better neighbor 与课件一致 | PASS：parent、crossover、mutation、next generation 与课件一致 |
| stem ambiguity | PASS：Lec4 framing 约束了问题范围 | PASS：页码与“课件示例”约束了问题范围 |
| answer-length cue | PASS：四项均为相近长度的动作描述 | PASS：四项均为相同四阶段结构，长度接近 |
| guessing path | LOW：仍可凭算法类别常识猜，但没有“而不是/全局最优”唯一线索 | LOW：必须区分阶段顺序，不能只选术语最多项 |
| capability alignment | PASS：只测过程识别，不测路径/最优性/收敛 | PASS：只测示例顺序，不测变体/收敛/最优性 |
| scorer/acceptance consistency | PASS：`neighbor_improvement` 与 acceptance case 同步，single_choice_v1 | PASS：`fitness_parent_cycle` 与 acceptance case 同步，single_choice_v1 |

## Revision-round owner decision table

| Candidate | Revision-round verdict |
|---|---|
| `verify_local_search_final_state_focus_v1` | `OWNER_APPROVE_RECOMMENDED` |
| `verify_hill_climbing_stop_at_local_best_v1` | `OWNER_APPROVE_RECOMMENDED` |
| `verify_simulated_annealing_worse_successor_v1` | `OWNER_APPROVE_RECOMMENDED` |
| `verify_evolutionary_search_parent_cycle_v1` | `OWNER_APPROVE_RECOMMENDED` |
| `verify_minimax_max_min_value_choice_v1` | `OWNER_APPROVE_RECOMMENDED` |
| `verify_alpha_beta_prune_when_bounds_cross_v1` | `OWNER_APPROVE_RECOMMENDED` |
| `verify_mcts_four_stage_order_v1` | `OWNER_APPROVE_RECOMMENDED` |
| `verify_ucb_upper_bound_selection_v1` | `OWNER_APPROVE_RECOMMENDED` |

该表仍只是独立审计建议，不等于负责人批准；8 道题仍不可进入 production，
必须继续经过 owner approval 和既有 promotion gate。

## Current revision-round status

- 本轮修改候选：仅 `verify_local_search_final_state_focus_v1` 与 `verify_evolutionary_search_parent_cycle_v1`。
- 未修改的候选：其余六道保持原 JSON 内容。
- production templates：20；active candidates：0；新增 blocked：0；既有 blocked slot：1；concepts：26。
- 未修改 production templates、selector、scorer、mastery、recommendation、P5B、evidence pipeline 或课程数据。
- 未执行 Git 写操作。

## Final Local Search revision

本节继续保留完整决策链：initial 8/8 → adversarial audit 的 6 approve + 2 revise
→ first revision 的 8 个 `OWNER_APPROVE_RECOMMENDED` → 负责人审核后 7 个通过、
Local Search 仍需修订 → 本次最终 Local Search revision。

### Previous revision was insufficient

上一版虽然已经把题目从“最终状态关注”改成了“当前状态邻域评价并移动到更好近邻”，
但该表述仍接近 Hill Climbing 的具体更新规则，不能稳定代表 `local_search` 上位概念；
它也可能让人误以为 Local Search 的所有变体都采用单一 current-state neighbor move。

### Final revision

- 题干改为：与需要维护完整搜索路径的系统搜索相比，局部搜索更关注什么。
- 正确选项改为：`candidate_solution_quality`，即评价当前候选状态或解的质量。
- 干扰项改为完整动作序列、frontier 系统顺序、可达状态空间枚举，形成 state/path/frontier/exhaustive 的相邻区分。
- 题干和解释不再声称所有 Local Search 只维护一个状态、只移动到更好邻居、不产生路径或保证全局最优。
- acceptance case、正确答案位置和 benchmark case ID 已同步；scorer 仍为 `single_choice_v1`。

### Final adversarial verdict

1. source entailment：`OWNER_APPROVE_RECOMMENDED`；Lec4 p.11 直接支持最终状态/完整路径区别，并描述近邻解评价。
2. second reasonable answer：未发现；B 是唯一表达候选状态/解质量 focus 的选项。
3. missing assumptions：题干限定为 Lec4 总体介绍，未引入具体变体规则。
4. terminology fidelity：通过；`candidate state`、`solution quality`、`path`、`frontier` 均服务于课件中的对比。
5. scorer closure：四个 choice ID 唯一，`single_choice_v1` 可确定评分。
6. distractor quality：错误项分别代表路径维护、frontier 系统搜索和穷举状态空间的相邻误区。
7. capability boundary：明确排除 Hill Climbing、Simulated Annealing、Evolutionary Search、global optimality、convergence、path reconstruction 及所有变体。
8. production overlap：未发现与 Hill Climbing candidate 或 production 题的 formal capability 重叠。
9. student readability：四项均为简洁中文动作/关注点描述，保留必要的 `frontier` 术语。
10. adversarial guessing：没有最长正确项或唯一变体术语线索；仍不能完全排除学生凭课程常识作答。

最终 verdict：`OWNER_APPROVE_RECOMMENDED`。该 verdict 仍不是负责人批准，candidate
仍保持 `candidate_draft`，不可进入 production。

## Final Local Search status

- 本次最终修订只修改 `verify_local_search_final_state_focus_v1`。
- 其余 7 道 candidate 未修改。
- `candidate_status=pending_human_review`，8 道仍为 `candidate_draft`。
- production templates：20；production selector active candidates：0；blocked slots：1；concepts：26。
- 未执行 promotion 或任何 Git 写操作。

## Final owner approval and promotion record

上述内容审核与多轮 adversarial review 是晋级前的独立准备材料。负责人随后在 Local Search
额外完成一次题面修订复核后，对八道候选全部作出最终批准（`OWNER_APPROVED`），并按受控
流程完成 promotion；该批准不等同于独立复核结论，也不改变本文件此前对风险和能力边界的记录。

- 当前 production：28 个 `human_verified` templates。
- 当前 active candidates：0；blocked slots：1；concepts：26。
- 本批八个模板均保留原 ID、primary concept、确定性 scorer、choice IDs、source refs、
  capability boundary 和 assistance 语义；仅 review 状态从 candidate draft 晋级为 production。
- Local Search 最终题干版本为负责人批准版本；未恢复旧题干或改写其他七题。
- 未修改 mastery 公式、recommendation、P5B、evidence gate、SQLite schema 或 repeat policy。
