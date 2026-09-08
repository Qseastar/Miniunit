# Search Algorithms P2c 首批候选题审核

本文件保留三道题的独立内容审核和负责人最终决定。负责人已批准三道题，本轮已将
批准版本加入 `data/diagnostic_templates.json`；晋级内容已在工作区实施，Git commit
仍待用户执行。
原 staging 批次已清空，不再把同一 template ID 同时保留为 active candidate。

## verify_search_problem_components_v1

### 当前状态

`human_verified` / production promotion implemented；提交仍待用户执行。

### 验证目标

识别课件明确列出的五项搜索问题定义要素，并把问题定义与求解策略分开。

### 主要 concept

`search_problem_formulation`

### 课件依据

- `ai_lec2_uninformed_search.pdf`，当前精简 PDF 第 6—10 页
- chunk：`lec2_search_problem_components`

该 chunk 的 section title 是“搜索问题的五个组成部分”。修订后只按五项定义要素
计分，不再把 `state_space` 作为第六个 exact-match 必选项。

### 修订后题干

按照课件“搜索问题的五个组成部分”这一节，下列哪些项目属于定义一个搜索问题时
需要明确的五项要素？请选择全部正确项。

### 选项

- `initial_state`：初始状态
- `actions`：可执行动作
- `transition_model`：状态转移模型
- `goal_test`：目标测试
- `path_cost`：路径代价
- `algorithm_choice`：预先指定必须使用哪一种搜索算法
- `frontier_container`：预先指定 frontier 必须使用哪一种容器

### 标准答案

`initial_state`、`actions`、`transition_model`、`goal_test`、`path_cost`

### 为什么答案成立

这五项描述问题本身需要明确的起点、动作、动作结果、目标判断和代价。具体采用哪种
搜索算法以及 frontier 使用何种实现属于求解策略，不是本题所问的五项问题定义要素。

### 常见误区

把搜索算法或 frontier 容器当成问题定义本身。`state_space` 是课程核心概念，但
不再被放入本题作为错误干扰项，避免形成术语口径陷阱。

### Hint

先区分“问题本身需要如何定义”和“之后采用什么策略求解”，再检查是否选全课件
明确列出的五项要素。

### Explanation

本题所依据的五项要素是初始状态、可执行动作、状态转移模型、目标测试和路径代价；
它们描述问题本身。具体搜索算法和 frontier 的实现属于求解策略，而不是这五项
问题定义要素。本题只验证能否识别课件明确列出的定义要素，不代表已经能够独立完成
完整的问题建模。

### 正确测试答案

`initial_state`、`actions`、`transition_model`、`goal_test`、`path_cost`，
提交顺序不影响评分。

### 错误测试答案

遗漏 `path_cost`，只选择其余四项，应由 exact-match scorer 判错。

### Mastery 映射

仅映射 `search_problem_formulation`。一次答对只构成“识别五项定义要素”的一条
能力证据，不代表该 concept 的全部 capability coverage。

### 独立内容审核结论

`REVISED / READY FOR HUMAN DECISION`

### 负责人最终决定

`approve`

### Production promotion 状态

已加入 production template bank；active candidate bank 中不再保留该 ID。

## verify_successor_operator_v1

### 当前状态

`human_verified` / production promotion implemented；提交仍待用户执行。

### 验证目标

根据动作约束，在给定候选中识别八数码状态的一步合法 successor。

### 主要 concept

`state_space_and_operators`

### 课件依据

- `ai_lec2_uninformed_search.pdf`，当前精简 PDF 第 12 页
- chunk：`lec2_eight_puzzle_formulation`

该 chunk 支持用方块与空格分布表示状态，并把移动空格作为 action/operator。

### 修订后题干

八数码当前状态为“空格、1、2 / 3、4、5 / 6、7、8”。一次动作只能把空格与
上下左右相邻的一个方块交换。以下四个候选状态中，哪一个可以由一次合法动作直接
得到？

### 选项

- `move_right`：1、空格、2 / 3、4、5 / 6、7、8
- `swap_non_adjacent`：空格、2、1 / 3、4、5 / 6、7、8
- `move_to_bottom_right`：1、2、3 / 4、5、6 / 7、8、空格
- `no_change`：空格、1、2 / 3、4、5 / 6、7、8

### 标准答案

`move_right`

### 为什么答案成立

空格位于左上角，合法 operator 有向右和向下。当前四个候选中只有
`move_right` 描述了其中一个合法 successor；向下交换得到的另一个合法 successor
没有列入选项。因此这里是“给定候选中唯一正确”，不是“全局只有一个合法动作”。

### 常见误区

忽略 operator 的邻接约束、一次执行多个移动，或把没有执行动作的原状态当成
successor。当前尚未创建正式 misconception ID。

### Hint

先找到空格当前位置，再只考虑与它上下左右相邻的方块。

### Explanation

空格位于左上角，合法 operator 有向右和向下：可以与右侧的 1 或下方的 3 交换。
当前四个候选选项中，只有 `move_right` 表示的状态是合法 successor；向下交换得到
的另一个合法 successor 没有出现在选项中。因此本题是候选选项中唯一正确，并不
表示全局只有一个合法 successor。

### 正确测试答案

`move_right`

### 错误测试答案

`no_change`

### Mastery 映射

仅映射 `state_space_and_operators`。本题验证一次 operator 应用，不代表已经枚举
完整 state space。

### 独立内容审核结论

`APPROVE / READY FOR HUMAN DECISION`

### 负责人最终决定

`approve`

### Production promotion 状态

已加入 production template bank；active candidate bank 中不再保留该 ID。

## verify_frontier_explored_membership_v1

### 当前状态

`human_verified` / production promotion implemented；提交仍待用户执行。

### 验证目标

在题面明确的 graph-search 时间线中，区分 frontier 中的搜索节点与 explored 中
的问题状态。

### 主要 concept

`frontier_and_explored_set`

### 课件依据

- `ai_lec2_uninformed_search.pdf`，当前精简 PDF 第 20 页
  - chunk：`lec2_frontier_expansion`
- `ai_lec2_uninformed_search.pdf`，当前精简 PDF 第 27 页
  - chunk：`lec2_graph_search_repeated_states`

第 20 页支持 frontier 中是已生成但尚待扩展的节点；第 27 页支持 graph search
记录访问状态以避免重复扩展。具体加入时点由题面显式规定，不把它描述成所有教材
和实现的唯一约定。

### 修订后题干

本题采用以下 graph-search 约定：frontier 保存已经生成但尚未扩展的搜索节点；
从 frontier 取出节点后，把它表示的状态加入 explored，再生成后继。开始时
frontier 中只有节点 Y，explored 为空。算法依次执行：

1. 从 frontier 取出节点 Y，并把状态 Y 加入 explored；
2. 扩展 Y，生成节点 X。状态 X 此前不在 frontier 或 explored，因此把节点 X
   加入 frontier；
3. 状态 Z 尚未生成。

在第 2 步完成后，下列哪些判断正确？请选择全部正确项。

### 选项

- `x_frontier`：节点 X 位于 frontier
- `x_explored`：状态 X 已位于 explored
- `y_explored`：状态 Y 位于 explored
- `y_frontier`：节点 Y 仍位于 frontier
- `z_frontier`：节点 Z 已位于 frontier

### 标准答案

`x_frontier`、`y_explored`

### 为什么答案成立

按题面约定，Y 已从 frontier 移除且其状态已记录到 explored；新生成、尚未扩展的
节点 X 被加入 frontier，状态 X 尚未加入 explored；Z 尚未生成。

### 常见误区

忽略题面时间线，把节点 X 所表示的状态提前放入 explored；把已经取出的节点 Y
继续留在 frontier；或把尚未生成的节点 Z 放入 frontier。当前尚未创建正式
misconception ID。

### Hint

先按题目规定的步骤分别写出第 2 步结束时 frontier 和 explored 的内容，并注意
节点与状态的区别。

### Explanation

本题采用题面所声明的 graph-search 约定：

- 开始：`frontier=[Y]`，`explored={}`；
- 取出并记录 Y：`frontier=[]`，`explored={Y}`；
- 扩展 Y 并加入新节点 X：`frontier=[X]`，`explored={Y}`。

因此节点 X 位于 frontier，状态 Y 位于 explored；状态 X 尚未加入 explored，
节点 Y 已不在 frontier，Z 尚未生成。这个加入时点是本题明确规定的约定，不主张
它是所有教材和实现的唯一规则。

### 正确测试答案

`x_frontier`、`y_explored`，提交顺序不影响评分。

### 错误测试答案

选择 `x_explored` 和 `y_explored`，应由 exact-match scorer 判错。

### Mastery 映射

仅映射 `frontier_and_explored_set`。题面把 graph-search 约定作为已知上下文，不
同时为 `tree_search_vs_graph_search` 创建 observation。

### 独立内容审核结论

`REVISED / READY FOR HUMAN DECISION`

### 负责人最终决定

`approve`

### Production promotion 状态

已加入 production template bank；active candidate bank 中不再保留该 ID。

## 审批表

| Template | 独立审核结论 | 负责人最终决定 | Production promotion | 提交状态 |
|---|---|---|---|---|
| `verify_search_problem_components_v1` | REVISED / READY FOR HUMAN DECISION | approve | implemented | 待用户提交 |
| `verify_successor_operator_v1` | APPROVE / READY FOR HUMAN DECISION | approve | implemented | 待用户提交 |
| `verify_frontier_explored_membership_v1` | REVISED / READY FOR HUMAN DECISION | approve | implemented | 待用户提交 |
