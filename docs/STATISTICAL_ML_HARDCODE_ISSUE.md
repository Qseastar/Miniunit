# Statistical ML 模块接入：概念总数 `26` 硬编码清单与放宽方案

> 供架构 owner 参考。本文记录在 `data/knowledge_points.json` 新增 5 个
> `statistical_ml` 知识点（总数 26 → 31）后，因多处硬编码「26 个概念」而失败的
> 测试与数据文件，并提出可行的放宽方案。**本文不修改任何共享语义，仅为决策提供清单。**

## 背景

Search Algorithms 是当前唯一落地模块，注册了 26 个概念。多个测试、数据文件与
工具把「26」当成了不变的事实，而不是「>= 26」或「从 registry 动态推导」。新增
Statistical ML 的 5 个知识点后，`len(knowledge_points)` 变为 31，导致约 40 个
既有测试失败。这些失败是**框架为单一模块时期留下的耦合**，不是新增内容本身的错误。

新增的 5 个知识点（`module="statistical_ml"`）：
`supervised_vs_unsupervised`、`k_nearest_neighbors`、`linear_regression_least_squares`、
`logistic_regression`、`k_means_clustering`。

---

## 一、直接断言 `== 26` 的测试（精确行号）

| 文件:行号 | 断言 |
| --- | --- |
| `tests/test_app_services.py:535` | `assert len(data["knowledge_data"]["knowledge_points"]) == 26` |
| `tests/test_app_services.py:547` | `assert len(second["knowledge_data"]["knowledge_points"]) == 26` |
| `tests/test_diagnostic_state_integration.py:465` | `assert len(knowledge["knowledge_points"]) == 26` |
| `tests/test_internal_pilot_pack.py:28` | `"concept_count": 26,` |
| `tests/test_mastery_map.py:67` | `assert len(layout_data["nodes"]) == len(registry_ids) == 26` |
| `tests/test_mastery_map.py:68` | `assert len({(node["layer"], node["order"]) for node in layout_data["nodes"]}) == 26` |
| `tests/test_mastery_map_visualization.py:62` | `assert len(copy_ids) == 26` |
| `tests/test_mastery_map_visualization.py:97` | `assert len(visual["nodes_by_id"]) == 26` |
| `tests/test_mastery_map_visualization.py:111` | `"total": 26,` |
| `tests/test_mastery_map_visualization.py:139` | `assert sum(len(layer["nodes"]) ... ) == 26` |
| `tests/test_mastery_map_visualization.py:161` | `assert first.count(" [label=") == 26` |
| `tests/test_p2g_quality_gate.py:353` | `assert len(coverage["concepts"]) == 26` |
| `tests/test_p2g_quality_gate.py:354` | `assert len({item["concept_id"] for item in coverage["concepts"]}) == 26` |
| `tests/test_p6_learner_state_measurement_audit.py:46` | `assert inventory["concept_count"] == 26` |
| `tests/test_p6b_aggregation_policy_comparison.py:169` | `assert report["inventory"]["concept_count"] == 26` |
| `tests/test_p6b_aggregation_policy_comparison.py:177` | `"concept_count": 26,` |
| `tests/test_p7_human_grounded_evaluation_protocol.py:60` | `assert len(capability_map) == 26` |
| `tests/test_p7_study_a_owner_design.py:115` | `"concept_count": 26,` |
| `tests/test_release_preflight.py:28` | `"concepts": 26,` |
| `tests/test_streamlit_app.py:710` | `"知识点总数": 26,` |
| `tests/test_streamlit_app.py:712` | `"尚未追踪": 26,` |
| `tests/test_streamlit_app.py:728` | `assert len(map_node_buttons) == 26` |

## 二、硬编码 `26` 的工具

| 文件:行号 | 逻辑 | 影响 |
| --- | --- | --- |
| `tools/pilot_preflight.py:104` | `"PASS" if len(knowledge_data["knowledge_points"]) == 26 else "FAIL"` | 内测预检把 31 概念判为 FAIL |
| `tools/release_preflight.py:294` | `"concepts": _registry_concept_count(root)` | 函数本身动态推导（返回 31），但 `test_release_preflight.py:28` 期望 26 |

## 三、硬编码 `26` 的课程数据文件（Search 专属，未被新模块覆盖）

| 文件 | 说明 |
| --- | --- |
| `data/search_algorithms_mastery_map_layout.json` | 掌握图谱布局，含 26 个 Search 节点 |
| `data/search_algorithms_concept_copy_zh.json` | 掌握图谱中文文案，含 26 个概念 |

这两个文件是 Search 模块专属的展示数据。新增知识点后，registry 有 31 个概念但
布局/文案只有 26 个，导致 `test_mastery_map.py`（8 个失败）与
`test_mastery_map_visualization.py`（6–7 个失败）中「布局恰好覆盖 registry」一类断言
失败。`test_streamlit_app.py` 的 mastery-map 测试同理。

---

## 四、可行的放宽方案（按类别）

### 方案 A：把 `== 26` 改为 `>= 26`（最小改动，适合「数量断言」）

对「只关心概念数量不少于当前值」的测试，直接放宽为 `>= 26`，或改成从
registry 动态推导：

```python
# 旧
assert len(data["knowledge_data"]["knowledge_points"]) == 26
# 新（动态推导，永不过期）
assert len(data["knowledge_data"]["knowledge_points"]) >= 26
# 或更严谨：
from introai_tutor.knowledge import load_knowledge_points
expected = len(load_knowledge_points(...)["knowledge_points"])
assert len(data["knowledge_data"]["knowledge_points"]) == expected
```

适用：第一节表格中除 mastery-map 外的绝大多数断言（app_services、
diagnostic_state_integration、internal_pilot_pack、p6/p6b、p7、quality_gate、
release_preflight、pilot_preflight）。

### 方案 B：让掌握图谱按 module 分片（结构性改动，推荐中期做）

`search_algorithms_mastery_map_layout.json` 与 `search_algorithms_concept_copy_zh.json`
是 Search 专属数据。多模块化应改为「每模块一个 layout/copy 文件 + 一个聚合视图」，
而不是把新模块硬塞进 Search 的布局文件。mastery-map 相关测试应改为：
- 断言「本模块布局覆盖本模块 registry 概念」，而非「全局 registry == 26」；
- 或按 `module` 过滤后再比较。

适用：`test_mastery_map.py`、`test_mastery_map_visualization.py`、
`test_streamlit_app.py` 的 mastery-map 断言。

### 方案 C：`course.unit` 元数据升级（仅元数据，可选）

`data/knowledge_points.json` 顶层 `course.unit` 仍为 `"Search Algorithms"`。多模块化
可改为 `units` 列表或在知识点层用 `module` 字段作为权威分片。不影响逻辑，仅影响
展示与检索文案。注意：`question_understanding.py`、`grounded_answering.py` 等 QA
提示词里也硬编码了 "Search Algorithms" 文案，属于同一类「单模块文案耦合」。

---

## 五、不应触碰的边界（即使放宽也要保留）

- `recommend_next_concept()` 的先修关系语义（新模块的先修只在本模块内闭环）。
- mastery 证据语义、`DiagnosticStateIntegrationService` 的 evidence gate。
- 确定性 scorer 注册表（`single_choice_v1` / `multiple_choice_v1` /
  `numeric_answer_v1` / `ordering_v1`）与生产模板审核/promotion 规则。
- `docs/evaluation/` 下 P6/P7 测量设计（其「26/21 覆盖」结论是 Search 模块当时的
  测量快照，不应因加模块而静默改写，应单独重算或标注为「Search 专属快照」）。

## 六、结论

- 把「26」当作常量是单模块时期的遗留耦合；多模块化应统一改为「从 registry 动态
  推导」或「>= N」。
- 数量断言类（方案 A）可以安全、机械地放宽，不影响任何业务语义。
- 掌握图谱（方案 B）涉及展示数据结构，建议由 owner 单独设计多模块布局方案，不在此
  次 Mini Unit 内强改。
- `course.unit` 与 QA 提示词里的 "Search Algorithms" 文案（方案 C）属元数据/文案，
  可随模块接入逐步清理。
