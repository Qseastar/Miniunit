# Search Algorithms template review packet

This packet records evidence and review inputs only. It does not approve or promote any candidate.
Authoritative owner decisions are recorded in `docs/search_algorithms_p2f_candidate_review.md`; the `owner_decision` fields in this generated packet remain blank by design.

## Production reviewed templates

### `verify_bfs_frontier_choice_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `breadth_first_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, explanation, comparison
- Explicit negative intent: definition
- Expected answer position: 1
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: BFS 按先进先出的顺序处理 frontier，因此 A 先于 B、C 被扩展。
- Sources:
  - `ai_lec2_uninformed_search.pdf:31-34` / `lec2_bfs_layer_order`

**Prompt:** BFS 的 frontier 中依次加入 A、B、C，且它们尚未扩展。下一步应选择哪个节点？

**Choices:**
- `A`: A
- `B`: B
- `C`: C

**Expected answer:** `{"choice_id": "A"}`

**Hint:** 回忆 BFS 对 frontier 的处理顺序：先进入 frontier 的节点会先被扩展。

**Explanation:** BFS 按先进先出的顺序处理 frontier，因此 A 先于 B、C 被扩展。

**Owner decision:**

### `verify_bfs_equal_cost_condition_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `breadth_first_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, explanation, comparison
- Explicit negative intent: definition
- Expected answer position: 1
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: BFS 按步数而不是累计代价选择路径。只有每一步代价相同，步数最少才等价于路径总代价最低。
- Sources:
  - `ai_lec2_uninformed_search.pdf:35-35` / `lec2_bfs_properties`

**Prompt:** 在哪种条件下，BFS 找到的最少步数路径也能保证路径总代价最小？

**Choices:**
- `equal_cost`: 所有动作或边的代价相同
- `nonnegative`: 所有边权非负
- `acyclic`: 图中不存在环
- `priority_queue`: 使用优先队列

**Expected answer:** `{"choice_id": "equal_cost"}`

**Hint:** 区分“边权非负”和“每一步代价相同”：只有后者会使步数与总代价等价。

**Explanation:** BFS 按步数而不是累计代价选择路径。只有每一步代价相同，步数最少才等价于路径总代价最低。

**Owner decision:**

### `verify_ucs_min_g_choice_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `uniform_cost_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation, comparison
- Explicit negative intent: algorithm_trace
- Expected answer position: 2
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: UCS 总是优先扩展累计路径代价 g(n) 最小的 frontier 节点，因此应选择 A。
- Sources:
  - `ai_lec2_uninformed_search.pdf:60-62` / `lec2_ucs_lowest_cost`

**Prompt:** frontier 中 A 的累计路径代价 g(n)=5，B 的 g(n)=8，C 的 g(n)=6。UCS 下一步扩展哪个节点？

**Choices:**
- `B`: B
- `A`: A
- `C`: C

**Expected answer:** `{"choice_id": "A"}`

**Hint:** 比较每个节点的累计路径代价 g(n)，而不是节点名称或进入 frontier 的顺序。

**Explanation:** UCS 总是优先扩展累计路径代价 g(n) 最小的 frontier 节点，因此应选择 A。

**Owner decision:**

### `verify_search_problem_components_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `search_problem_formulation`
- Scorer / type: `multiple_choice_v1` / `multiple_choice`
- Eligible intents: diagnostic_request, definition, explanation
- Explicit negative intent: comparison
- Expected answer position: None
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 本题所依据的五项要素是初始状态、可执行动作、状态转移模型、目标测试和路径代价；它们描述问题本身。具体搜索算法和 frontier 的实现属于求解策略，而不是这五项问题定义要素。本题只验证能否识别课件明确列出的定义要素，不代表已经能够独立完成完整的问题建模。
- Sources:
  - `ai_lec2_uninformed_search.pdf:6-10` / `lec2_search_problem_components`

**Prompt:** 按照课件“搜索问题的五个组成部分”这一节，下列哪些项目属于定义一个搜索问题时需要明确的五项要素？请选择全部正确项。

**Choices:**
- `initial_state`: 初始状态
- `algorithm_choice`: 预先指定必须使用哪一种搜索算法
- `actions`: 可执行动作
- `transition_model`: 状态转移模型
- `frontier_container`: 预先指定 frontier 必须使用哪一种容器
- `goal_test`: 目标测试
- `path_cost`: 路径代价

**Expected answer:** `{"choice_ids": ["initial_state", "actions", "transition_model", "goal_test", "path_cost"]}`

**Hint:** 先区分“问题本身需要如何定义”和“之后采用什么策略求解”，再检查是否选全课件明确列出的五项要素。

**Explanation:** 本题所依据的五项要素是初始状态、可执行动作、状态转移模型、目标测试和路径代价；它们描述问题本身。具体搜索算法和 frontier 的实现属于求解策略，而不是这五项问题定义要素。本题只验证能否识别课件明确列出的定义要素，不代表已经能够独立完成完整的问题建模。

**Owner decision:**

### `verify_successor_operator_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `state_space_and_operators`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation
- Explicit negative intent: comparison
- Expected answer position: 2
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 空格位于左上角，合法 operator 有向右和向下：可以与右侧的 1 或下方的 3 交换。当前四个候选选项中，只有 move_right 表示的状态是合法 successor；向下交换得到的另一个合法 successor 没有出现在选项中。因此本题是候选选项中唯一正确，并不表示全局只有一个合法 successor。
- Sources:
  - `ai_lec2_uninformed_search.pdf:12-12` / `lec2_eight_puzzle_formulation`

**Prompt:** 八数码当前状态为“空格、1、2 / 3、4、5 / 6、7、8”。一次动作只能把空格与上下左右相邻的一个方块交换。以下四个候选状态中，哪一个可以由一次合法动作直接得到？

**Choices:**
- `swap_non_adjacent`: 空格、2、1 / 3、4、5 / 6、7、8
- `move_right`: 1、空格、2 / 3、4、5 / 6、7、8
- `move_to_bottom_right`: 1、2、3 / 4、5、6 / 7、8、空格
- `no_change`: 空格、1、2 / 3、4、5 / 6、7、8

**Expected answer:** `{"choice_id": "move_right"}`

**Hint:** 先找到空格当前位置，再只考虑与它上下左右相邻的方块。

**Explanation:** 空格位于左上角，合法 operator 有向右和向下：可以与右侧的 1 或下方的 3 交换。当前四个候选选项中，只有 move_right 表示的状态是合法 successor；向下交换得到的另一个合法 successor 没有出现在选项中。因此本题是候选选项中唯一正确，并不表示全局只有一个合法 successor。

**Owner decision:**

### `verify_frontier_explored_membership_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `frontier_and_explored_set`
- Scorer / type: `multiple_choice_v1` / `multiple_choice`
- Eligible intents: diagnostic_request, definition, explanation
- Explicit negative intent: comparison
- Expected answer position: None
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 本题采用题面所声明的 graph-search 约定。开始时 frontier=[Y]、explored={}；取出并记录 Y 后，frontier=[]、explored={Y}；扩展 Y 并加入新节点 X 后，frontier=[X]、explored={Y}。因此节点 X 位于 frontier，状态 Y 位于 explored；状态 X 尚未加入 explored，节点 Y 已不在 frontier，Z 尚未生成。这个加入时点是本题明确规定的约定，不主张它是所有教材和实现的唯一规则。
- Sources:
  - `ai_lec2_uninformed_search.pdf:20-20` / `lec2_frontier_expansion`
  - `ai_lec2_uninformed_search.pdf:27-27` / `lec2_graph_search_repeated_states`

**Prompt:** 本题采用以下 graph-search 约定：frontier 保存已经生成但尚未扩展的搜索节点；从 frontier 取出节点后，把它表示的状态加入 explored，再生成后继。开始时 frontier 中只有节点 Y，explored 为空。算法依次执行：
1. 从 frontier 取出节点 Y，并把状态 Y 加入 explored；
2. 扩展 Y，生成节点 X。状态 X 此前不在 frontier 或 explored，因此把节点 X 加入 frontier；
3. 状态 Z 尚未生成。
在第2步完成后，下列哪些判断正确？请选择全部正确项。

**Choices:**
- `x_frontier`: 节点 X 位于 frontier
- `x_explored`: 状态 X 已位于 explored
- `y_explored`: 状态 Y 位于 explored
- `y_frontier`: 节点 Y 仍位于 frontier
- `z_frontier`: 节点 Z 已位于 frontier

**Expected answer:** `{"choice_ids": ["x_frontier", "y_explored"]}`

**Hint:** 先按题目规定的步骤分别写出第2步结束时 frontier 和 explored 的内容，并注意节点与状态的区别。

**Explanation:** 本题采用题面所声明的 graph-search 约定。开始时 frontier=[Y]、explored={}；取出并记录 Y 后，frontier=[]、explored={Y}；扩展 Y 并加入新节点 X 后，frontier=[X]、explored={Y}。因此节点 X 位于 frontier，状态 Y 位于 explored；状态 X 尚未加入 explored，节点 Y 已不在 frontier，Z 尚未生成。这个加入时点是本题明确规定的约定，不主张它是所有教材和实现的唯一规则。

**Owner decision:**

### `verify_graph_search_repeated_state_handling_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `tree_search_vs_graph_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation
- Explicit negative intent: comparison
- Expected answer position: 3
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: Lec2 p.27 的 graph-search 伪代码先从 frontier 取出 node，再检查其 state 是否不在 closed；只有条件成立时才记录并扩展。因为 STATE[N]=S 且 S 已在 explored/closed 中，该条件不成立，所以不再次扩展 N。N 是另一个 search node，但它表示的仍是同一个 problem state。本题只验证课件这版伪代码中的重复状态处理，不涵盖生成时去重、frontier duplicate、reopening 或 lower-cost replacement。
- Sources:
  - `ai_lec2_uninformed_search.pdf:27-27` / `lec2_graph_search_repeated_states`

**Prompt:** 本题沿用 Lec2 p.27 的 graph-search 伪代码，并将其中的 closed 称为 explored：frontier 保存 search node；从 frontier 取出一个 node 后，算法检查 STATE[node] 是否已在 explored，只有不在时才将该 state 加入 explored 并扩展该 node。现在状态 S 已在 explored 中，随后从 frontier 取出另一个节点 N，且 STATE[N]=S。下一步应怎样处理？

**Choices:**
- `expand_then_record`: 先扩展节点 N，再把状态 S 再次加入 explored
- `remove_and_expand`: 先从 explored 删除状态 S，再扩展节点 N
- `discard_repeat`: 跳过节点 N，不再次扩展状态 S
- `keep_until_empty`: 把节点 N 放回 frontier，等待其他节点处理完

**Expected answer:** `{"choice_id": "discard_repeat"}`

**Hint:** 比较 STATE[N] 与 explored，并注意课件伪代码中的扩展操作位于“state 不在 closed”这一条件分支内。

**Explanation:** Lec2 p.27 的 graph-search 伪代码先从 frontier 取出 node，再检查其 state 是否不在 closed；只有条件成立时才记录并扩展。因为 STATE[N]=S 且 S 已在 explored/closed 中，该条件不成立，所以不再次扩展 N。N 是另一个 search node，但它表示的仍是同一个 problem state。本题只验证课件这版伪代码中的重复状态处理，不涵盖生成时去重、frontier duplicate、reopening 或 lower-cost replacement。

**Owner decision:**

### `verify_dfs_frontier_choice_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `depth_first_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation, algorithm_trace
- Explicit negative intent: comparison
- Expected answer position: 4
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: DFS 优先扩展 frontier 中最深的节点。B 和 C 都处于 depth=2，比 A 更深；题面又明确 C 在 B 之后入栈，因此按照 stack 的后进先出规则，C 位于栈顶并应被下一步弹出。选择 B 忽略了同深度节点的 LIFO 次序，选择 A 忽略了 deepest-first，DFS 也不会一次同时弹出两个节点。本题已显式给出 frontier 和入栈顺序，不依赖未声明的左右 successor 顺序；它只验证一次 DFS frontier 选择，不测量完备性、最优性或复杂度，也不代表已经完整掌握 DFS。
- Sources:
  - `ai_lec2_uninformed_search.pdf:37-46` / `lec2_dfs_deepest_first`
  - `ds_stack_queue_priority_queue.pdf:1-2` / `support_stack_lifo`

**Prompt:** 本题中的 DFS 实现使用 stack 管理 frontier。当前尚未扩展的节点按“栈底 → 栈顶”写为 [A(depth=1), B(depth=2), C(depth=2)]；A 最先入栈，随后是 B，最后是 C，且此时没有新节点加入。DFS 下一步应从 frontier 弹出哪个节点？

**Choices:**
- `node_a`: 节点 A
- `node_b`: 节点 B
- `nodes_b_and_c`: 同时弹出节点 B 和节点 C
- `node_c`: 节点 C

**Expected answer:** `{"choice_id": "node_c"}`

**Hint:** 先找当前 stack 的栈顶；深度相同时，使用题面已给出的入栈顺序和 LIFO 规则。

**Explanation:** DFS 优先扩展 frontier 中最深的节点。B 和 C 都处于 depth=2，比 A 更深；题面又明确 C 在 B 之后入栈，因此按照 stack 的后进先出规则，C 位于栈顶并应被下一步弹出。选择 B 忽略了同深度节点的 LIFO 次序，选择 A 忽略了 deepest-first，DFS 也不会一次同时弹出两个节点。本题已显式给出 frontier 和入栈顺序，不依赖未声明的左右 successor 顺序；它只验证一次 DFS frontier 选择，不测量完备性、最优性或复杂度，也不代表已经完整掌握 DFS。

**Owner decision:**

### `verify_iddfs_depth_limit_schedule_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `iterative_deepening_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation
- Explicit negative intent: comparison
- Expected answer position: 1
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: IDDFS 会用逐步增加的 depth limit 反复运行 depth-limited DFS。按题面明确声明的 0、1、2、…… 约定，limit=0 和 limit=1 都未找到目标后，下一轮应把 limit 提高到 2，并从根节点重新开始，而不是继续上一轮暂停的 DFS。重复 limit=1 或改成一次无限深 DFS 也不符合 iterative deepening。Lec2 p.53 的文字从 limit=1 开始展示，p.54–55 的动画明确包含 limit=0 和 limit=1；本题明确采用动画页的 0、1、2 约定，因此答案唯一。本题只验证 limit 递增和每轮重启，不代表完整掌握 IDDFS 的复杂度、完备性或最优性；depth-limited DFS 在此是 IDDFS 的内部步骤，不是独立的 mastery concept。
- Sources:
  - `ai_lec2_uninformed_search.pdf:53-57` / `lec2_iddfs_strategy`

**Prompt:** 本题明确采用 depth limit 依次为 0、1、2、…… 的 IDDFS 约定；每一轮都从根节点重新运行一次 depth-limited DFS，找到目标就停止。limit=0 和 limit=1 两轮都已完成且没有找到目标。下一步应做什么？

**Choices:**
- `restart_limit_2`: 把 depth limit 提高到 2，并从根节点重新运行 depth-limited DFS
- `continue_limit_2`: 不重新开始，直接把上一轮尚未完成的 DFS 延伸到 depth=2
- `restart_limit_1`: 仍使用 depth limit=1，从根节点再运行同一轮
- `run_unlimited_dfs`: 取消 depth limit，改为运行一次无限深 DFS

**Expected answer:** `{"choice_id": "restart_limit_2"}`

**Hint:** 关注下一轮是否提高 depth limit，以及 iterative deepening 的每一轮从哪里开始。

**Explanation:** IDDFS 会用逐步增加的 depth limit 反复运行 depth-limited DFS。按题面明确声明的 0、1、2、…… 约定，limit=0 和 limit=1 都未找到目标后，下一轮应把 limit 提高到 2，并从根节点重新开始，而不是继续上一轮暂停的 DFS。重复 limit=1 或改成一次无限深 DFS 也不符合 iterative deepening。Lec2 p.53 的文字从 limit=1 开始展示，p.54–55 的动画明确包含 limit=0 和 limit=1；本题明确采用动画页的 0、1、2 约定，因此答案唯一。本题只验证 limit 递增和每轮重启，不代表完整掌握 IDDFS 的复杂度、完备性或最优性；depth-limited DFS 在此是 IDDFS 的内部步骤，不是独立的 mastery concept。

**Owner decision:**

### `verify_informed_search_g_h_roles_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `informed_search_and_heuristics`
- Scorer / type: `multiple_choice_v1` / `multiple_choice`
- Eligible intents: diagnostic_request, definition, explanation, comparison
- Explicit negative intent: algorithm_trace
- Expected answer position: None
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 课件把 g(n) 定义为从起始结点到结点 n 的开销代价值，把 h(n) 定义为从结点 n 到目标结点路径中所估算的最小开销代价值。它们分别描述已走路径与到目标的估计，不要求 h(n) 等于真实剩余代价。本题只验证这两个记号的角色，不验证 A* 的 frontier 选择。
- Sources:
  - `ai_lec3_informed_search.pdf:18-18` / `lec3_a_star_f_g_h`

**Prompt:** 课件在介绍 A* 的记号时，用 g(n) 表示已经走过的开销，用 h(n) 表示到目标的启发式估计。下列哪些配对与课件一致？请选择全部正确项。

**Choices:**
- `g_path_cost`: g(n) 表示从起始结点到结点 n 的开销代价值。
- `h_paid_cost`: h(n) 表示从起始结点到结点 n 已经付出的路径开销。
- `h_goal_estimate`: h(n) 表示从结点 n 到目标结点路径中所估算的最小开销代价值。
- `g_goal_estimate`: g(n) 表示从结点 n 到目标结点的估计剩余代价。

**Expected answer:** `{"choice_ids": ["g_path_cost", "h_goal_estimate"]}`

**Hint:** 先区分已经从起点付出的开销，与从当前结点到目标的估计开销。

**Explanation:** 课件把 g(n) 定义为从起始结点到结点 n 的开销代价值，把 h(n) 定义为从结点 n 到目标结点路径中所估算的最小开销代价值。它们分别描述已走路径与到目标的估计，不要求 h(n) 等于真实剩余代价。本题只验证这两个记号的角色，不验证 A* 的 frontier 选择。

**Owner decision:**

### `verify_greedy_min_h_choice_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `greedy_best_first_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation, algorithm_trace
- Explicit negative intent: comparison
- Expected answer position: 2
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: A、B、C、D 的 h 分别为 5、2、4、3，B 最小，因此贪婪搜索选择 B。D 的 g+h 更小这一点不改变本题答案：按 g+h 选择是 A* 的比较方式，不是这里测试的贪婪选择规则。本题只验证一次 min-h frontier 选择，不推断贪婪搜索的完备性或最优性。
- Sources:
  - `ai_lec3_informed_search.pdf:9-9` / `lec3_greedy_search`

**Prompt:** 贪婪搜索每次选择按启发式信息看起来离目标状态最近的 frontier 节点。当前 frontier 中 A 的 g=1、h=5；B 的 g=6、h=2；C 的 g=2、h=4；D 的 g=1、h=3。若 h 表示到目标的估计距离，下一步应选择哪个节点？

**Choices:**
- `node_a`: 节点 A
- `node_b`: 节点 B
- `node_c`: 节点 C
- `node_d`: 节点 D

**Expected answer:** `{"choice_id": "node_b"}`

**Hint:** 贪婪搜索在本题中只比较各节点离目标的启发式估计 h，而不把已付开销 g 加进去。

**Explanation:** A、B、C、D 的 h 分别为 5、2、4、3，B 最小，因此贪婪搜索选择 B。D 的 g+h 更小这一点不改变本题答案：按 g+h 选择是 A* 的比较方式，不是这里测试的贪婪选择规则。本题只验证一次 min-h frontier 选择，不推断贪婪搜索的完备性或最优性。

**Owner decision:**

### `verify_astar_min_f_choice_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `a_star_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation, algorithm_trace
- Explicit negative intent: comparison
- Expected answer position: 3
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 四个节点的 f 值依次为 A=6、B=7、C=4、D=5，所以 A* 选择 f 最小的 C。只按 h 选择会混同贪婪搜索，只按 g 选择会混同 UCS。本题只验证课件给出的 min-f frontier 选择，不主张它已经检验了 A* 的最优性条件。
- Sources:
  - `ai_lec3_informed_search.pdf:18-18` / `lec3_a_star_f_g_h`
  - `ai_lec3_informed_search.pdf:21-21` / `lec3_a_star_f_g_h`

**Prompt:** A* 按 f(n)=g(n)+h(n) 比较 frontier 节点。当前 A 的 g=1、h=5；B 的 g=4、h=3；C 的 g=2、h=2；D 的 g=0、h=5。下一步应选择哪个节点？

**Choices:**
- `node_a`: 节点 A
- `node_b`: 节点 B
- `node_c`: 节点 C
- `node_d`: 节点 D

**Expected answer:** `{"choice_id": "node_c"}`

**Hint:** 逐个计算 g(n)+h(n)，再比较得到的 f(n)，不要只比较 g 或只比较 h。

**Explanation:** 四个节点的 f 值依次为 A=6、B=7、C=4、D=5，所以 A* 选择 f 最小的 C。只按 h 选择会混同贪婪搜索，只按 g 选择会混同 UCS。本题只验证课件给出的 min-f frontier 选择，不主张它已经检验了 A* 的最优性条件。

**Owner decision:**

### `verify_admissibility_no_overestimate_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `admissibility_and_consistency`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation
- Explicit negative intent: comparison
- Expected answer position: 4
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 可采纳性要求对任意节点有 h(n)≤h*(n)，即不高估真实最小剩余代价。选项 D 中 P 的估计恰好等于 4，Q 的估计小于 7，因此两者都满足；其余选项至少有一个节点高估。本题只检验可采纳性，不检验一致性，也不把这一次判断当作 A* tree-search 或 graph-search 最优性条件的完整证明。
- Sources:
  - `ai_lec3_informed_search.pdf:30-30` / `lec3_admissibility`

**Prompt:** 对两个节点，真实最小剩余代价分别为 h*(P)=4、h*(Q)=7。下列哪组启发式值满足课件中的可采纳性定义？

**Choices:**
- `p_overestimates`: h(P)=5，h(Q)=6
- `q_overestimates`: h(P)=2，h(Q)=8
- `both_overestimate`: h(P)=6，h(Q)=9
- `equal_and_under`: h(P)=4，h(Q)=6

**Expected answer:** `{"choice_id": "equal_and_under"}`

**Hint:** 分别检查每个节点是否满足 h(n) 不大于 h*(n)；等于真实最小剩余代价也允许。

**Explanation:** 可采纳性要求对任意节点有 h(n)≤h*(n)，即不高估真实最小剩余代价。选项 D 中 P 的估计恰好等于 4，Q 的估计小于 7，因此两者都满足；其余选项至少有一个节点高估。本题只检验可采纳性，不检验一致性，也不把这一次判断当作 A* tree-search 或 graph-search 最优性条件的完整证明。

**Owner decision:**

### `verify_path_cost_accumulation_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `search_problem_formulation`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation
- Explicit negative intent: comparison
- Expected answer position: 3
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 只验证三个单位行动的基础累计；不验证非单位代价、UCS、启发式或完整问题建模。
- Sources:
  - `ai_lec2_uninformed_search.pdf:11-11` / `lec2_solution_and_optimality`
  - `ai_lec2_uninformed_search.pdf:12-12` / `lec2_eight_puzzle_formulation`

**Prompt:** 一个搜索问题的某个解由连续 3 个行动组成。题面明确每一个行动的代价都为 1。该解的路径代价是多少？

**Choices:**
- `last_step_only`: 1，只看最后一个行动的代价
- `two_actions`: 2
- `three_action_costs`: 3，把三个行动的代价相加
- `four_nodes`: 4，把起点和三个行动后的节点数相加

**Expected answer:** `{"choice_id": "three_action_costs"}`

**Hint:** 路径代价对应一组行动序列的代价；题面给出的三个行动都要计入。

**Explanation:** 课件把解说明为从初始状态到目标状态的一组行动序列，并在八数码例子中明确每一步代价为 1。因此本题三次行动的路径代价为 1+1+1=3。它不检验非单位代价、UCS 或启发式函数。

**Owner decision:**

### `verify_search_node_state_distinction_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `tree_search_vs_graph_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation
- Explicit negative intent: comparison
- Expected answer position: 1
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 只验证 node 与 state 的表示关系；不规定完整 node schema，不覆盖 duplicate replacement 或 reopening。
- Sources:
  - `ai_lec2_uninformed_search.pdf:27-27` / `lec2_graph_search_repeated_states`

**Prompt:** Lec2 p.27 的 graph-search 伪代码从 frontier 取出 search node，再检查 STATE[node] 是否已经在 closed 中。下列哪项准确区分 search node 与 problem state？

**Choices:**
- `different_nodes_same_state`: N1 和 N2 可以是不同的 search node，但都表示同一个 problem state S
- `same_state_means_same_node`: 只要状态相同，N1 和 N2 必定是同一个 search node
- `state_contains_closed`: problem state S 本身等同于 closed 集合
- `must_expand_both`: graph-search 必须扩展 N1 和 N2，才能判断它们的状态是否相同

**Expected answer:** `{"choice_id": "different_nodes_same_state"}`

**Hint:** 区分伪代码中从 frontier 取出的 node，与用 STATE[node] 得到并放入 closed 的 problem state。

**Explanation:** 课件的 graph-search 伪代码把 node 从 frontier 取出，却把 STATE[node] 与 closed 比较并记录。因而不同 search node 可以表示同一个 problem state；图搜索借此避免重复扩展状态。本题不规定 search node 的完整实现字段，也不检验 frontier duplicate 或 lower-cost replacement。

**Owner decision:**

### `verify_dfs_infinite_branch_risk_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `depth_first_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, explanation, property
- Explicit negative intent: definition
- Expected answer position: 2
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 只验证受限 infinite-branch 场景中的完备性风险；不测时间、空间或所有有限问题上的表现。
- Sources:
  - `ai_lec2_uninformed_search.pdf:37-46` / `lec2_dfs_deepest_first`
  - `ai_lec2_uninformed_search.pdf:48-48` / `lec2_dfs_properties`

**Prompt:** DFS 总是扩展当前 frontier 中最深的节点。设它先进入一条没有目标、但可以无限延伸的分支；另一条尚未扩展的分支在深度 1 就有目标。关于这一次搜索，下列哪项最符合课件对 DFS 完备性的结论？

**Choices:**
- `must_find_shallow_goal`: DFS 一定会先返回深度 1 的目标，因为目标更浅
- `may_not_find_shallow_goal`: DFS 可能持续沿更深分支搜索，因而不保证找到这个浅层目标
- `switches_to_bfs`: DFS 会自动改为 BFS，以保证找到最浅目标
- `must_be_optimal`: DFS 因为优先深入，所以必定返回总代价最小的解

**Expected answer:** `{"choice_id": "may_not_find_shallow_goal"}`

**Hint:** 把 deepest-first 的选择规则，与课件性能页给出的 DFS 完备性结论结合起来判断。

**Explanation:** 课件说明 DFS 扩展最深的 frontier 节点，并在性能页将其标为非完备、非最优。在题面明确存在可无限延伸的先行分支时，它可能一直深入而不保证到达另一条浅层目标分支。该结论说的是“不保证”，并不表示 DFS 在每个有限问题上都会失败；本题也不测量时间或空间复杂度。

**Owner decision:**

### `verify_search_algorithm_properties_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `completeness_optimality_complexity`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, comparison, property
- Explicit negative intent: definition
- Expected answer position: 4
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 只验证 IDDFS 的一个条件性性质陈述；不构成 BFS、DFS、IDDFS、UCS 的完整性质矩阵。
- Sources:
  - `ai_lec2_uninformed_search.pdf:53-53` / `lec2_iddfs_strategy`
  - `ai_lec2_uninformed_search.pdf:58-58` / `lec2_iddfs_properties`
  - `ai_lec2_uninformed_search.pdf:35-35` / `lec2_bfs_properties`
  - `ai_lec2_uninformed_search.pdf:48-48` / `lec2_dfs_properties`
  - `ai_lec2_uninformed_search.pdf:63-63` / `lec2_ucs_properties`

**Prompt:** 下列哪项与课件中关于搜索算法性能的结论一致？

**Choices:**
- `bfs_equal_cost_for_complete`: BFS 只有在所有行动代价相同时才是完备的
- `dfs_complete_not_optimal`: DFS 是完备的，但不是最优的
- `ucs_not_optimal`: UCS 不是最优的，因为它不按深度选择节点
- `iddfs_equal_cost_optimal`: IDDFS 是完备的；当所有行动代价相同时，它是最优的

**Expected answer:** `{"choice_id": "iddfs_equal_cost_optimal"}`

**Hint:** 逐项核对课件对 complete 和 optimal 的结论，并注意最优性是否带有行动代价条件。

**Explanation:** Lec2 p.58 将 IDDFS 标为完备，并注明“如果所有行动代价相同”时具有最优性。BFS 的完备性并不以该条件为前提；DFS 在课件中是非完备、非最优；UCS 在课件中标为最优。本题只验证这一组受限性质陈述，不构成完整的算法性质矩阵。

**Owner decision:**

### `verify_greedy_suboptimality_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `greedy_best_first_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, explanation, property
- Explicit negative intent: definition
- Expected answer position: 1
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 只验证可能非最优的性质边界；不构造反例，不推断 Greedy 总失败或完整性。
- Sources:
  - `ai_lec3_informed_search.pdf:14-14` / `lec3_greedy_limitations`

**Prompt:** 课件说明贪婪搜索每一步选择按启发式信息看起来离目标更近的节点，并列出了它的 bad case。下列哪项是课件支持的结论？

**Choices:**
- `may_be_nonoptimal`: 贪婪搜索可能不是最优的，其效果依赖启发式函数
- `always_optimal`: 只要每一步选择 h 最小的节点，贪婪搜索就一定最优
- `h_is_paid_cost`: 贪婪搜索中的 h 是从起点到当前节点已经付出的路径代价
- `uses_g_plus_h`: 贪婪搜索总是按 g(n)+h(n) 选择节点

**Expected answer:** `{"choice_id": "may_be_nonoptimal"}`

**Hint:** 课件把贪婪搜索的选择依据写为“看起来离目标更近”，并在 bad case 中列出其性质限制。

**Explanation:** 课件明确将贪婪搜索的 bad case 列为“非完备、非最优、依赖启发式函数”。因此它可能得到非最优结果，而不是总会失败；h 是到目标的估计，g+h 是 A* 的评价方式。本题只验证这一性质边界，不要求构造反例，也不检验完备性。

**Owner decision:**

### `verify_astar_f_value_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `a_star_search`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation, algorithm_trace
- Explicit negative intent: comparison
- Expected answer position: 2
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 只验证一次公式代入；不测 min-f selection、可采纳性、一致性或 A* 最优性。
- Sources:
  - `ai_lec3_informed_search.pdf:18-18` / `lec3_a_star_f_g_h`

**Prompt:** 对某个 frontier 节点 N，已知 g(N)=4、h(N)=3。按照课件中 A* 的 f(N)=g(N)+h(N)，f(N) 是多少？

**Choices:**
- `g_only`: 4
- `g_plus_h`: 7
- `h_only`: 3
- `g_minus_h`: 1

**Expected answer:** `{"choice_id": "g_plus_h"}`

**Hint:** 本题不比较多个节点；只把当前节点的 g 和 h 按 f=g+h 相加。

**Explanation:** 课件定义 A* 的 f(N)=g(N)+h(N)。本题中 4+3=7。只取 g 会混同 UCS，只取 h 会混同贪婪搜索；本题只验证一次 f 值计算，不检验 min-f frontier 选择、可采纳性、一致性或最优性。

**Owner decision:**

### `verify_consistency_edge_check_v1`

- Bank: `production`
- Review status: `human_verified`
- Primary concept: `admissibility_and_consistency`
- Scorer / type: `single_choice_v1` / `single_choice`
- Eligible intents: diagnostic_request, definition, explanation, property
- Explicit negative intent: comparison
- Expected answer position: 3
- Evidence expectation: `evidence_eligible`
- UI available: True
- Capability boundary: 只验证单条边的一致性条件；不证明整个 heuristic 对所有边一致，也不证明 A* 的完整最优性条件。
- Sources:
  - `ai_lec3_informed_search.pdf:39-39` / `lec3_consistency`

**Prompt:** 对一条从 n 到后继 n' 的行动，已知 cost(n,a,n')=3、h(n)=7、h(n')=4。下列哪项关于这一条边的说法正确？

**Choices:**
- `strictly_less_required`: 不满足一致性，因为 h(n) 必须严格小于 cost(n,a,n')+h(n')
- `admissibility_comparison`: 不满足一致性，因为应比较 h(n) 与真实剩余代价 h*(n)
- `edge_satisfies_equality`: 这条边满足一致性：7≤3+4，等号允许
- `proves_global_consistency`: 检查这一条边就能证明整个启发函数对所有边都一致

**Expected answer:** `{"choice_id": "edge_satisfies_equality"}`

**Hint:** 代入课件的一致性条件 h(n)≤cost(n,a,n')+h(n')，并区分它与可采纳性的 h(n)≤h*(n)。

**Explanation:** 本题中 7≤3+4，因此这一条边满足课件的一致性不等式，等号允许。可采纳性使用 h*(n) 而不是一条边的行动代价；检查单条边也不能证明所有相关边都满足一致性。本题只验证一个 edge check，不代表完整掌握一致性或 A* 图搜索最优性。

**Owner decision:**

## Candidate templates — human approval required

## Blocked capability slots
- `verify_ucs_frontier_update_v1` (uniform_cost_search): The reviewed project subset does not directly support a safe frontier lower-cost-update item.
  - Missing evidence: A source page that explicitly specifies replacement or decrease-key behavior for a lower-cost duplicate frontier path.
  - Prohibited fallback: Do not infer implementation-specific UCS frontier-update behavior from general textbook knowledge.
