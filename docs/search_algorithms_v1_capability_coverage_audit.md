# Search Algorithms v1 能力覆盖审计（P2f 晋级后）

## 口径

只有 `data/diagnostic_templates.json` 的 20 道 `human_verified` 模板可以产生受控 learner-state evidence；candidate staging 已清空。模板覆盖不等于 concept 完整掌握。

| Layer | Templates | Evidence boundary |
|---|---:|---|
| Production | 20 | 受控、确定性、已审核的窄能力 observation |
| Active candidate | 0 | 无 |
| Blocked | 1 | UCS lower-cost duplicate frontier update 缺主课件 direct rule |

## P2f 已进入 production 的能力切片

`verify_path_cost_accumulation_v1`、`verify_search_node_state_distinction_v1`、`verify_dfs_infinite_branch_risk_v1`、`verify_search_algorithm_properties_v1`、`verify_greedy_suboptimality_v1`、`verify_astar_f_value_v1`、`verify_consistency_edge_check_v1` 均为 `human_verified`，可由 selector、verification service 和 evidence gate 使用。

它们分别保持原有 `supported_inference` 或 `direct` 证据边界，不扩展为完整搜索算法性质证明。`uniform_cost_search` 仍只覆盖 min-g 选择；`verify_ucs_frontier_update_v1` 保持 blocked。

## 后续边界

继续增加题目前，应先获得 source evidence、唯一答案和能力边界审核；不得以数量凑出第 21 道题，不得把 support material 当成 AI 主课件定义。
