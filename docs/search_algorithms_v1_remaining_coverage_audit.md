# Search Algorithms v1 剩余能力覆盖审计（P2f 晋级后）

## 当前结论

- 名义目标：21 道 reviewed templates；
- production：20 道 `human_verified`；
- active candidates：0；
- blocked：1（`verify_ucs_frontier_update_v1`）；
- 当前 course-core 证据支持的 v1 reviewed-template 范围已完成；UCS lower-cost frontier update 仍排除。

P2f 七道 owner-approved candidates 已按既有 promotion 流程进入 production。没有创建第 21 道证据不足的题，也没有用 Dijkstra 先修材料替代 AI 主课件证据。

| 已晋级模板 | 能力切片 | 证据强度 |
|---|---|---|
| `verify_path_cost_accumulation_v1` | 单位行动的 path cost 累计 | `supported_inference` |
| `verify_search_node_state_distinction_v1` | `node` 与 `STATE[node]` 的区分 | `supported_inference` |
| `verify_dfs_infinite_branch_risk_v1` | 无限先行分支下 DFS 的完备性风险 | `supported_inference` |
| `verify_search_algorithm_properties_v1` | IDDFS 完备性与等步代价最优性 | `supported_inference` |
| `verify_greedy_suboptimality_v1` | Greedy 可能非最优 | `direct` |
| `verify_astar_f_value_v1` | 单节点 `f=g+h` 计算 | `direct` |
| `verify_consistency_edge_check_v1` | 单边 consistency inequality | `direct` |

模板存在不等于学生已经掌握 concept；每道题仍只提供窄能力 evidence。IDDFS p.53 为 context-only、p.58 为 primary evidence，source gate 继续 fail closed。
