# P2f：Search Algorithms v1 七道候选晋级记录

## 晋级结果

- 批次：`search_algorithms_p2f_a`
- 分支：`feature/p2f-promote-seven-approved`
- candidate staging：`data/candidate_templates/search_algorithms_p2f_candidates.json`
- promotion 状态：已完成；`candidate_status=promoted_to_production`
- production reviewed templates：20
- active candidates：0
- blocked slots：1

以下七道题已由负责人最终批准并按既有 P2e 流程晋级；题干、选项、顺序、答案、concept、intent、scorer、教学说明和 source metadata 均保持不变。

| Template | Owner decision | Production status |
|---|---|---|
| `verify_path_cost_accumulation_v1` | `approve` | `human_verified` |
| `verify_search_node_state_distinction_v1` | `approve` | `human_verified` |
| `verify_dfs_infinite_branch_risk_v1` | `approve` | `human_verified` |
| `verify_search_algorithm_properties_v1` | `approve` | `human_verified` |
| `verify_greedy_suboptimality_v1` | `approve` | `human_verified` |
| `verify_astar_f_value_v1` | `approve` | `human_verified` |
| `verify_consistency_edge_check_v1` | `approve` | `human_verified` |

`independent review` 与 `human approval` 的流程区别在 promotion 前已记录；本次 promotion 仅执行负责人批准后的状态迁移，不把任何自动检查当作负责人批准。

## Candidate staging

晋级完成后 staging 按既有惯例清空：`templates=[]`、`acceptance_cases={}`。因此七道 ID 不再由 candidate loader 激活，production/candidate overlap 为 `[]`。

## 保持阻塞的能力

`verify_ucs_frontier_update_v1` 仍为 `keep_blocked`。当前课件没有直接支持 lower-cost duplicate frontier replacement/decrease-key 的安全页面证据；本轮没有创建第 21 道题，也没有使用 Dijkstra 先修材料替代 AI 主课件证据。

IDDFS 的 source-role 链仍保持：Lec2 p.53 为 `context_only`，p.58 为 `primary_evidence`；context-only 不能独立满足 primary evidence gate。

## 验收边界

- production loader：20/20 通过；
- selector、deterministic scorer、VerificationDiagnosticService 与 Streamlit AppTest 覆盖七道新题；
- source-role、evidence gate、assistance、mastery、recommendation 和原有 production 题保持原有语义；
- 本轮未修改 production Python、`app.py`、mastery、recommendation、P5B、课程数据或 API 配置。

## 后续中文文案复核

`verify_search_algorithm_properties_v1` 已经人工内容复核，并仅将题干由“下列哪项与课件的搜索算法性能页一致？”修订为“下列哪项与课件中关于搜索算法性能的结论一致？”。本次修订只改善中文表达，不改变能力切片、选项、顺序、标准答案、concept、eligible intents、scorer、教学说明或 source metadata。
