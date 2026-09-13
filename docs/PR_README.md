# Statistical ML 模块 Mini Unit — PR 说明

> 本文是统计机器学习（Statistical ML）模块 Mini Unit 的 PR 说明，供课程 owner 与评审人快速了解改动范围、验收点与已知风险。本文不替代 `docs/NEW_MODULE_QUICKSTART.md` 与 `docs/DEVELOPER_HANDOFF_GUIDE.md` 中的正式边界说明。

## 1. 我负责哪个模块

- **模块**：统计机器学习（`statistical_ml` / Statistical Machine Learning）
- **课件**：`lec8`（南京大学《人工智能导论》，统计机器学习算法），本地文件为 `lec8.pdf`，在数据文件中统一登记为 `ai_lec8_statistical_learning.pdf`（47 页，`course_core` 角色）。
- **接入方式**：通过中央课程模块 registry（`data/course_modules.json`）新增一个 module entry，使用模块独立的 knowledge / chunks / manifest / templates / mastery-map 数据文件，未改动 Search Algorithms 的任何业务数据。

## 2. 当前完成哪些知识点（17 个）

`concept_id` 使用 `statistical_ml__` 前缀，整门课程内唯一。先修关系如下（`→` 表示先修指向依赖）：

| # | concept_id | 中文名 | 先修（prerequisites） |
| --- | --- | --- | --- |
| 1 | `statistical_ml__supervised_learning` | 监督学习 | （无） |
| 2 | `statistical_ml__unsupervised_learning` | 无监督学习 | （无） |
| 3 | `statistical_ml__knn_lazy_learning` | 懒惰学习 | `statistical_ml__supervised_learning` |
| 4 | `statistical_ml__knn_k_value_selection` | k 值选择 | `statistical_ml__supervised_learning` |
| 5 | `statistical_ml__knn_distance_metric` | 距离度量 | `statistical_ml__supervised_learning` |
| 6 | `statistical_ml__linear_regression_univariate` | 一元线性回归 | `statistical_ml__supervised_learning` |
| 7 | `statistical_ml__linear_regression_multivariate` | 多元线性回归 | `statistical_ml__linear_regression_univariate` |
| 8 | `statistical_ml__linear_regression_regularization` | 正则化 | `statistical_ml__linear_regression_multivariate` |
| 9 | `statistical_ml__linear_regression_srm` | 结构风险最小化 | `statistical_ml__linear_regression_regularization` |
| 10 | `statistical_ml__logistic_regression_glm` | 广义线性模型 | `statistical_ml__linear_regression_multivariate` |
| 11 | `statistical_ml__logistic_regression_sigmoid` | Sigmoid 函数 | `statistical_ml__logistic_regression_glm` |
| 12 | `statistical_ml__logistic_regression_mle` | 极大似然估计 | `statistical_ml__logistic_regression_sigmoid` |
| 13 | `statistical_ml__logistic_regression_gradient_descent` | 梯度下降法 | `statistical_ml__logistic_regression_mle` |
| 14 | `statistical_ml__clustering_evaluation` | 聚类评价指标 | `statistical_ml__unsupervised_learning` |
| 15 | `statistical_ml__kmeans_algorithm` | K 均值聚类 | `statistical_ml__clustering_evaluation` |
| 16 | `statistical_ml__kmeans_limitations` | K-Means 不足 | `statistical_ml__kmeans_algorithm` |
| 17 | `statistical_ml__clustering_applications` | 聚类应用 | `statistical_ml__kmeans_algorithm` |

## 3. Diagnostic 有哪些（18 道）

全部 18 道题均为 `mastery_verification`，已进入模块生产模板文件（`data/statistical_ml_templates.json`，`review_status="human_verified"`）。全部题型均为 `single_choice`（确定性 scorer `single_choice_v1`），与现有学生界面的渲染能力一致。

| # | template_id | 题型 | 对应知识点（concept_id） | scorer |
| --- | --- | --- | --- | --- |
| 1 | `verify_supervised_vs_unsupervised_definition_v1` | single_choice | `statistical_ml__unsupervised_learning` | single_choice_v1 |
| 2 | `verify_knn_k_value_effect_v1` | single_choice | `statistical_ml__knn_k_value_selection` | single_choice_v1 |
| 3 | `verify_knn_manhattan_distance_v1` | single_choice | `statistical_ml__knn_distance_metric` | single_choice_v1 |
| 4 | `verify_linear_regression_least_squares_objective_v1` | single_choice | `statistical_ml__linear_regression_univariate` | single_choice_v1 |
| 5 | `verify_linear_regression_closed_form_intercept_v1` | single_choice | `statistical_ml__linear_regression_univariate` | single_choice_v1 |
| 6 | `verify_logistic_regression_is_classifier_v1` | single_choice | `statistical_ml__logistic_regression_glm` | single_choice_v1 |
| 7 | `verify_logistic_regression_sigmoid_range_v1` | single_choice | `statistical_ml__logistic_regression_sigmoid` | single_choice_v1 |
| 8 | `verify_kmeans_steps_order_v1` | single_choice | `statistical_ml__kmeans_algorithm` | single_choice_v1 |
| 9 | `verify_kmeans_limitations_v1` | single_choice | `statistical_ml__kmeans_limitations` | single_choice_v1 |
| 10 | `verify_statistical_ml_supervised_learning_sc_v1` | single_choice | `statistical_ml__supervised_learning` | single_choice_v1 |
| 11 | `verify_statistical_ml_knn_lazy_learning_sc_v1` | single_choice | `statistical_ml__knn_lazy_learning` | single_choice_v1 |
| 12 | `verify_statistical_ml_linear_regression_multivariate_sc_v1` | single_choice | `statistical_ml__linear_regression_multivariate` | single_choice_v1 |
| 13 | `verify_statistical_ml_linear_regression_regularization_sc_v1` | single_choice | `statistical_ml__linear_regression_regularization` | single_choice_v1 |
| 14 | `verify_statistical_ml_linear_regression_srm_sc_v1` | single_choice | `statistical_ml__linear_regression_srm` | single_choice_v1 |
| 15 | `verify_statistical_ml_logistic_regression_mle_sc_v1` | single_choice | `statistical_ml__logistic_regression_mle` | single_choice_v1 |
| 16 | `verify_statistical_ml_logistic_regression_gradient_descent_sc_v1` | single_choice | `statistical_ml__logistic_regression_gradient_descent` | single_choice_v1 |
| 17 | `verify_statistical_ml_clustering_evaluation_sc_v1` | single_choice | `statistical_ml__clustering_evaluation` | single_choice_v1 |
| 18 | `verify_statistical_ml_clustering_applications_sc_v1` | single_choice | `statistical_ml__clustering_applications` | single_choice_v1 |

## 4. 已知问题（提交前需 owner 知悉）

1. **公共文件改动属 ARCHITECTURE_REVIEW_REQUIRED**：为支持统计机器学习知识图谱渲染，修改了 3 个公共文件：
   - `src/introai_tutor/mastery_map_visualization.py`：`build_visual_mastery_map_model` 新增可选参数 `stage_names`（默认 `None` 时仍走原有硬编码 `LAYER_STAGE_NAMES`，向后兼容）。
   - `src/introai_tutor/course_modules.py`：新增可选的 `mastery_map_stage_names` 字段及其校验函数 `_stage_names`。
   - `app.py`：为 `statistical_ml` 模块新增 QA 示例文案，并把 registry 中的 `stage_names` 透传给图谱渲染。
   详见 `docs/statistical_ml_public_changes.md`。这些改动均向后兼容，Search 模块行为不受影响，但回归原仓库前需 architecture review。

2. **lec8 course chunks 均为 `codex_draft`，待人工核对**：`data/statistical_ml_chunks.json` 中 17 条 chunk 的 `review_status` 全部为 `codex_draft`，尚未标记 `human_verified`。逐条人工核对表见 `docs/statistical_ml_chunk_review.md`。

3. **自由问答依赖 `DEEPSEEK_API_KEY`，密钥未纳入仓库**：QA 链路需要外部 DeepSeek API Key，仅通过会话环境变量注入，不写入任何被 Git 追踪的文件（`.env` 已在 `.gitignore` 中）。

4. **候选模板状态与生产模板状态尚未对齐**：`data/candidate_templates/statistical_ml_p1_candidates.json` 的 `candidate_status` 仍为 `pending_human_review`、模板 `review_status` 为 `candidate_draft`，而 `data/statistical_ml_templates.json` 中同名模板已为 `human_verified`。合并前建议将候选文件状态更新为 `promoted_to_production`（与 Search 的 P5b 候选流程保持一致），属纯账目对齐，不影响评分语义。

## 5. 如何测试

在仓库根目录（`C:\Users\92847\statistical_ml_workspace`）执行：

```bash
# 模块候选数据离线校验（知识点 + 候选模板 + scorer 正确/错误/畸形输入）
PYTHONPATH=src python -m pytest tests/test_statistical_ml_candidates.py -q

# 模块注册、模块隔离与知识图谱（含 Search 回归）
PYTHONPATH=src python -m pytest tests/test_course_modules.py tests/test_mastery_map.py tests/test_mastery_map_visualization.py -q

# 统计机器学习集成测试（模块隔离 / QA 范围 / 17 节点图谱 / mastery 更新）
PYTHONPATH=src python -m pytest tests/test_statistical_ml_integration.py -q

# 完整测试套件
PYTHONPATH=src python -m pytest -q
```

预期结果：以上命令全部通过（离线、不依赖真实 PDF、不依赖 DeepSeek API Key）。涉及外部 API 的 QA 实测单独记录在 `docs/statistical_ml_qa_test.md`。
