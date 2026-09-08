# P7d 第三轮负责人审核：Local Search 外部评估条目最终处置

## 决定记录与边界

第三轮负责人决定覆盖 P7c 中两个发生变化的 research-only 条目：

| 条目 | 第三轮负责人决定 | P7d 处置 |
| --- | --- | --- |
| `p7_ext_ucs_positive_cost_bound_d` | `OWNER_APPROVE` | 冻结其 canonical representation；继续仅作为 pending research bank 的外部课程标准。 |
| `p7_ext_local_search_representation_b` | `OWNER_REVISE` | 经本轮 source 与构念审计后，未找到同时满足独立性和无提示要求的授权替代表述；从 active bank 移除并记录为 `LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE`。 |

`OWNER_APPROVE` 在此仅指研究工具内容已获负责人认可；不表示 production approval、Level 2、人体研究授权、true mastery、ground truth 或校准概率。所有 active item 仍处于 research-only 的 `pending_owner_review` bank schema 中。

P7c 是历史记录：其中的 Local Search proposal 没有被改写为已获批准。P7d 也不改动任何 production template、learner-state evidence、recommendation 或研究参与者流程。

## 冻结的 owner-approved canonical representations

下列五项的 canonical JSON 哈希由 P7d 回归测试锁定：

| ID | SHA-256 |
| --- | --- |
| `p7_ext_bfs_depth_claim_a` | `802dc213cd9a13bd2d624bd57b723f94acc0c891cd4d1aae5e8cc9997fd1b231` |
| `p7_ext_local_search_neighbor_a` | `2243b54a80e834ad19675fc4f608db5981c2c7dc8b790b946905ef7009f96092` |
| `p7_ext_mcts_backpropagation_a` | `67583fdf6b125d0d331a54f2724478e7b53f3b0b8c8bba6f3470c83b7f8ae1c5` |
| `p7_ext_astar_zero_heuristic_c` | `3322f375f4f4c82dfb295969f686aa23d62649fcd6fb1b8d7348f57e6e5695bd` |
| `p7_ext_ucs_positive_cost_bound_d` | `a04400e4658a0a5aaf43128e27b0880682c8cb13e3cecd5ee33dfeefc04afcdf` |

P7b 的既有测试继续冻结六个 earlier preserve-direction items。冻结只是防止未授权的内容漂移，绝不把外部题注册到 production。

## P7c Local Search proposal 的拒绝理由

P7c 条目 `p7_ext_local_search_representation_b` 的题干预先给出了“只关心最终返回状态是否达到目标，而不关心完整路径”的判定规则；其正确选项再用 N 皇后最终布局和“不要求完整移动序列”复述该规则。因此存在 `ANSWER_RULE_DISCLOSED_IN_STEM` / `HIGH_SEMANTIC_CUE`：即使不了解 Local Search，普通语义匹配也可以选出 A。

第三轮决定认可它已避开 P7b 的 candidate/neighborhood shortcut，但不认可这种由题干直接披露答案规则的构念效度。

## P7d Local Search source 与替代可行性审计

**授权 source：** `ai_lec4_local_search_and_llm_search.pdf`，物理页 9–11，关联 chunk `lec4_local_search_state_neighbors`。
**直接内容：** Lec4 表述许多问题只关心最终返回状态是否达到目标、无需搜索从初始状态开始的各条路径；同一页还以当前状态的 neighborhood 近邻评价和移动到更好解描述 Local Search，并展示 N 皇后与数独示例。
**source strength：** 对两个上位命题均为 `STRONG`；但该有限页面没有提供第三个可闭合、可评分、且不落入这两条命题的 Local Search representation construct。

### Adversarial audit

| 测试 | 结论 |
| --- | --- |
| A. Semantic paraphrase | 任何将“最终状态而非路径”放入题干、再在选项中寻找同义任务结果的形式，都失败：题干直接披露答案规则。 |
| B. Neighbor shortcut | 任何转而询问当前状态、邻域、质量比较或更新的形式，都与已批准的 `p7_ext_local_search_neighbor_a` 共享“candidate/neighbors，而非 path/frontier”的路径。 |
| C. Algorithm-name recognition | 使用 N 皇后或数独作正确选项会形成 `N-Queens/Sudoku = Local Search` 的课程示例识别捷径；不使用该例则没有更强的本地任务依据。 |
| D. Production overlap | `verify_local_search_final_state_focus_v1` 已以定义匹配方式测量 final-state focus 与 candidate-solution quality。新的 final-output 选择题仍要求同一核心定义匹配，不能仅凭“换情境”称为独立。 |
| E. Second-answer | 路径、frontier、枚举型 distractor 虽可形成单一正确答案，却同时造成与 production / sibling 相同的排除法；移除这些区分后，Lec4 又未给出足够的唯一闭合命题。 |

### 生产与 sibling 的答题路径比较

| 项目 | 输入 | 推理 | 要求输出 |
| --- | --- | --- | --- |
| production `verify_local_search_final_state_focus_v1` | 直接比较完整路径系统搜索与 Local Search | 识别 final-state / candidate-quality 定义 | Local Search 关注当前候选状态或解的整体质量 |
| approved sibling `p7_ext_local_search_neighbor_a` | 当前课表、一次移动近邻、冲突数比较 | 识别 candidate-neighborhood quality process | 选择局部过程概括 |
| P7c representation | final-state/path rule已写入题干 | 词汇/语义复述 | 选“不需路径”的 N 皇后结果 |
| 可用的 P7d 替代 | 不存在 | 任何可由 Lec4 直接支持的候选都回落到以上任一推理 | 不强造一个表面不同的 closed item |

因此，本轮没有新的 P7d Local Search 题干、A/B/C/D 或 expected answer；空缺是经过记录的科学性限制，而不是未完成草稿。

## Capability boundary 与状态

被移除条目本来拟测：在上位 Local Search framing 下判断 final-state requirement / path irrelevance。P7d 不否认此课程构念；只确认在当前授权 source 与现有 production/sibling 的组合下，不能将其作为独立外部 closed item 而不引入 semantic cue 或能力重复。

该条目不测 Hill Climbing、Simulated Annealing、tabu/history/population/temperature、所有实现的内存结构、全局最优性或收敛性；这些边界未被扩展。

active research-only bank 因科学性 blocking 从 12 项变为 11 项；`local_search` 保留一个已批准的 neighbor item。validator 保留“每个已选概念至少一项”的完整性检查，但不再错误强制每概念两项；这不等于创建 strict parallel forms 或恢复被阻断题目。

## 研究边界与下一步

P7 仍为 **LEVEL 1 — synthetic pipeline validated**。未创建 human study、招募、研究 UI、participant data、parallel-form pairing 或新的 mastery policy。外部结果依旧不写入 production learner state、mastery、recommendation 或 ordinary student UI。

`LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE` 是下一轮负责人研究设计决策的输入：若将来要重新纳入该构念，必须先取得新的、足以支持独立 construct 的人工审核课程证据或重新设计 research scope；不得靠 cosmetic rewrite 恢复。
