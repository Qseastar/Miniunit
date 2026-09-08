# Search Algorithms P2d 第二批候选题审核

本文件记录 P2d-a 草稿、独立课程审核、P2d-b candidate-only revision，以及
负责人最终批准后的 P2d-c 受控 production promotion。三道题均已晋级
`data/diagnostic_templates.json`；production promotion 代码尚待用户 commit。

## verify_graph_search_repeated_state_handling_v1

### 当前状态

`human_verified` / `promoted_to_production`

### 验证目标

应用 Lec2 p.27 的 graph-search 条件分支，判断一个表示已记录 state 的新 search
node 是否应再次扩展。

### 主要 concept

`tree_search_vs_graph_search`

### 课件依据

- `ai_lec2_uninformed_search.pdf`，当前精简 PDF 第 27 页
- chunk：`lec2_graph_search_repeated_states`
- chunk topics：`tree_search_vs_graph_search`、`frontier_and_explored_set`

### 原始页面审核结论

页面直接对比 tree search 与 graph search，并包含 graph-search 伪代码：

- fringe/frontier 保存 search node；
- `closed` 记录 problem state；
- 从 frontier 取出 node 后、扩展前检查 `STATE[node]`；
- 只有 state 不在 closed 时，才记录 state 并扩展 node；
- 页面没有同时检查 frontier，也没有规定其他实现必须采用相同检查时点。

本题将课件的 `closed` 称为 `explored`，并在题面首次出现时明确说明。chunk 摘要
方向正确，但没有恢复伪代码细节；原始页面提供了更强的直接证据。

### 证据强度

`direct`

### 修订后题干

本题沿用 Lec2 p.27 的 graph-search 伪代码，并将其中的 closed 称为 explored：
frontier 保存 search node；从 frontier 取出一个 node 后，算法检查
`STATE[node]` 是否已在 explored，只有不在时才将该 state 加入 explored 并扩展
该 node。现在状态 S 已在 explored 中，随后从 frontier 取出另一个节点 N，且
`STATE[N]=S`。下一步应怎样处理？

### 选项

- `discard_repeat`：跳过节点 N，不再次扩展状态 S
- `expand_then_record`：先扩展节点 N，再把状态 S 再次加入 explored
- `remove_and_expand`：先从 explored 删除状态 S，再扩展节点 N
- `keep_until_empty`：把节点 N 放回 frontier，等待其他节点处理完

### 标准答案

`discard_repeat`

### 为什么答案成立

`STATE[N]` 已在 explored/closed 中，因此 p.27 伪代码的“不在 closed”条件不成立，
记录和扩展分支不会执行。N 是另一个 search node，但它仍表示同一个 problem state。
其他选项都会重复扩展、破坏访问记录或重新保留该重复节点。

### Hint

比较 `STATE[N]` 与 explored，并注意课件伪代码中的扩展操作位于“state 不在
closed”这一条件分支内。

### Explanation

Lec2 p.27 的 graph-search 伪代码先从 frontier 取出 node，再检查其 state 是否
不在 closed；只有条件成立时才记录并扩展。因为 `STATE[N]=S` 且 S 已在
explored/closed 中，该条件不成立，所以不再次扩展 N。N 是另一个 search node，
但它表示的仍是同一个 problem state。本题只验证课件这版伪代码中的重复状态处理，
不涵盖生成时去重、frontier duplicate、reopening 或 lower-cost replacement。

### 正确测试答案

`discard_repeat`

### 错误测试答案

`expand_then_record`

Malformed acceptance answer：`["discard_repeat"]`。

### Mastery 映射

仅映射 `tree_search_vs_graph_search`。`frontier_and_explored_set` 只是支持上下文，
不复制相同 mastery evidence。

### 能力边界

本题不验证生成时去重、frontier duplicate、不同 path cost 下的 reopening、
lower-cost replacement 或其他教材的 graph-search 变体。一题正确不代表完整掌握
tree search 与 graph search。

### 独立课程审核结论

`REVISED / READY FOR HUMAN DECISION`

P2d-b 已删除原题干直接给出的“已存在就丢弃”结论，同时保留 p.27 的必要条件和
唯一答案。

### 负责人最终决定

`approve`

P2d-c promotion status：`promoted_to_production`。

## verify_dfs_frontier_choice_v1

### 当前状态

`human_verified` / `promoted_to_production`

### 验证目标

根据明确的 frontier stack、节点深度和入栈顺序，应用 DFS 的 deepest-first 与
LIFO 规则选择下一个节点。

### 主要 concept

`depth_first_search`

### 课件依据

- `ai_lec2_uninformed_search.pdf`，当前精简 PDF 第 37—46 页
  - chunk：`lec2_dfs_deepest_first`
- `ds_stack_queue_priority_queue.pdf`，当前精简 PDF 第 1—2 页
  - chunk：`support_stack_lifo`
  - source role：`prerequisite_support`

### 原始页面审核结论

Lec2 pp.37–46 直接说明 DFS 扩展当前 frontier 中最深的节点。stack 先修页直接
说明栈顶、push/pop 和 LIFO。AI 主课件仍是 DFS 定义的主要来源；先修材料只补充
容器行为。

题面已经给出栈底到栈顶、所有节点深度和完整入栈顺序，不依赖未声明的
left-to-right successor order。

### 证据强度

`direct`

### 修订后题干

本题中的 DFS 实现使用 stack 管理 frontier。当前尚未扩展的节点按“栈底 → 栈顶”
写为 `[A(depth=1), B(depth=2), C(depth=2)]`；A 最先入栈，随后是 B，最后是 C，
且此时没有新节点加入。DFS 下一步应从 frontier 弹出哪个节点？

### 选项

- `node_c`：节点 C
- `node_b`：节点 B
- `node_a`：节点 A
- `nodes_b_and_c`：同时弹出节点 B 和节点 C

### 标准答案

`node_c`

### 为什么答案成立

A 的 depth=1，浅于 B 和 C；B、C 的 depth 都是 2。C 最后入栈并位于栈顶，因此
LIFO 下一步弹出 C。题面给出的 deepest-first 和 stack 顺序指向同一唯一答案。

### Hint

先找当前 stack 的栈顶；深度相同时，使用题面已给出的入栈顺序和 LIFO 规则。

### Explanation

DFS 优先扩展 frontier 中最深的节点。B 和 C 都处于 depth=2，比 A 更深；C 又在
B 之后入栈并位于栈顶，因此按 stack 的 LIFO 规则弹出 C。选择 B 忽略同深度下的
stack 顺序，选择 A 忽略 deepest-first，一次扩展也不会同时弹出两个节点。本题不
测量 completeness、optimality、time complexity 或 space complexity，也不把 DFS
描述成只比较深度而忽略 stack 顺序。

### 正确测试答案

`node_c`

### 错误测试答案

`node_b`

Malformed acceptance answer：`["node_c"]`。

### Mastery 映射

仅映射 `depth_first_search`。stack 是 prerequisite support，不新增或更新其他
mastery concept。

### 能力边界

本题只验证一次 DFS frontier choice，不验证无限深分支、完备性、最优性或复杂度。
一题正确不代表完整掌握 DFS。

### 独立课程审核结论

`APPROVE / READY FOR HUMAN DECISION`

P2d-b 只把首句收窄为“本题中的 DFS 实现”，其余题目主体、答案和来源不变。

### 负责人最终决定

`approve`

P2d-c promotion status：`promoted_to_production`。

## verify_iddfs_depth_limit_schedule_v1

### 当前状态

`human_verified` / `promoted_to_production`

### 验证目标

识别 IDDFS 提高 depth limit 后，会从根节点重新运行下一轮 depth-limited DFS。

### 主要 concept

`iterative_deepening_search`

### 课件依据

- `ai_lec2_uninformed_search.pdf`，当前精简 PDF 第 53—57 页
- chunk：`lec2_iddfs_strategy`
- chunk topics：`iterative_deepening_search`、`depth_first_search`、
  `breadth_first_search`

### 原始页面审核结论

- p.53 的文字从 depth limit 1 开始展示，随后为 2、3；
- p.54–55 的动画明确包含 limit 0 和 limit 1；
- p.57 说明浅层节点以及根节点会在不同迭代中重复生成；
- 课件不同页面的起始展示口径不同，但都支持逐轮提高 limit 并重新运行受限 DFS。

本题明确采用动画页的 `0、1、2、……` 约定，因此不要求学生猜测不同页面的起始
编号，下一轮答案唯一。

### 证据强度

`direct`

### 修订后题干

本题明确采用 depth limit 依次为 0、1、2、…… 的 IDDFS 约定；每一轮都从根节点
重新运行一次 depth-limited DFS，找到目标就停止。`limit=0` 和 `limit=1` 两轮都
已完成且没有找到目标。下一步应做什么？

### 选项

- `restart_limit_2`：把 depth limit 提高到 2，并从根节点重新运行 depth-limited DFS
- `continue_limit_2`：不重新开始，直接把上一轮尚未完成的 DFS 延伸到 depth=2
- `restart_limit_1`：仍使用 depth limit=1，从根节点再运行同一轮
- `run_unlimited_dfs`：取消 depth limit，改为运行一次无限深 DFS

### 标准答案

`restart_limit_2`

### 为什么答案成立

按题面明确采用的序列，下一轮 limit 为 2。IDDFS 的新一轮从根节点重新运行
depth-limited DFS，而不是继续上一轮暂停的 DFS。

### Hint

关注下一轮是否提高 depth limit，以及 iterative deepening 的每一轮从哪里开始。

### Explanation

IDDFS 会用逐步增加的 depth limit 反复运行 depth-limited DFS。按题面的 0、1、
2、…… 约定，前两轮没有找到目标后，下一轮应把 limit 提高到 2 并从根节点重新
开始。Lec2 p.53 的文字从 limit=1 开始展示，p.54–55 的动画包含 limit=0 和
limit=1；本题明确采用动画页约定，因此答案唯一。本题验证 limit 递增和每轮重启，
不代表完整掌握 IDDFS 的复杂度、完备性或最优性。depth-limited DFS 是 IDDFS 的
内部步骤，不是独立的 mastery concept。

### 正确测试答案

`restart_limit_2`

### 错误测试答案

`continue_limit_2`

Malformed acceptance answer：`"unknown_limit_action"`。

### Mastery 映射

仅映射 `iterative_deepening_search`。不创建 `depth_limited_search` concept，也不
向 DFS 或 BFS 复制同一 evidence。

### 能力边界

本题只验证一次 limit 调度和重启行为，不验证 cutoff/failure 的完整实现，也不验证
IDDFS 的复杂度、完备性或最优性。一题正确不代表完整掌握 IDDFS。

### 独立课程审核结论

`APPROVE / READY FOR HUMAN DECISION`

P2d-b 保持题干、选项和答案不变，只把原始页面证据说明更新为 direct。

### 负责人最终决定

`approve`

P2d-c promotion status：`promoted_to_production`。

## Scorer 与 UI 选择

三题继续使用现有 `single_choice_v1`。IDDFS 单选已经能同时验证 limit 增长和从根
重启；本批次不需要、也没有实现 ordering UI。

## 审批表

| Template | 独立审核结论 | 题干 | 答案 | 课件依据 | Hint/Explanation | Concept mapping | 负责人最终决定 |
|---|---|---|---|---|---|---|---|
| `verify_graph_search_repeated_state_handling_v1` | REVISED / READY FOR HUMAN DECISION | approve | approve | approve | approve | approve | approve |
| `verify_dfs_frontier_choice_v1` | APPROVE / READY FOR HUMAN DECISION | approve | approve | approve | approve | approve | approve |
| `verify_iddfs_depth_limit_schedule_v1` | APPROVE / READY FOR HUMAN DECISION | approve | approve | approve | approve | approve | approve |
