# IntroAI Tutor

A course-grounded adaptive learning agent prototype for the Search unit of Introduction to Artificial Intelligence.

MVP goal:
- course knowledge structure
- learner memory
- diagnostic-explanation-practice-evaluation-recommendation loop
- simple local demo

## Run the MVP

Python 3.11+ is required. Install the single UI dependency, then start
Streamlit from the repository root:

```bash
python -m pip install -r requirements.txt
PYTHONPATH=src python -m streamlit run app.py
```

The application does not load `.env` itself. For a local configuration, copy
the safe template and export only the values you need in the current shell:

```bash
cp .env.example .env
set -a
source .env
set +a
PYTHONPATH=src python -m streamlit run app.py
```

`DEEPSEEK_API_KEY` is optional for the deterministic diagnostic and reviewed
verification path, but required for free-form course QA. `INTROAI_STATE_DB`
and `INTROAI_COURSE_MATERIALS_DIR` are optional overrides; Poppler and
cloudflared are optional system tools, not Python requirements.
需要干净的本地 learner profile 时，在页面设置区使用“创建新的本地学习档案”；
这不会删除其他 profile 或 SQLite 文件。

Before sharing a reproducible research run, run the offline release preflight:

```bash
PYTHONPATH=src python tools/release_preflight.py --strict
```

It separates blocking core failures from optional material/provider/Pilot
warnings and never reads a `.env` file or makes a network request. The full
quality gate and test commands are documented in the Summer release technical
snapshot: [`docs/releases/search_algorithms_summer_2026.md`](docs/releases/search_algorithms_summer_2026.md).

Tests use `pytest` as a development tool; install it separately when running
the local suite (`python -m pip install pytest`). It is intentionally not part
of the runtime `requirements.txt`.

The diagnostic tab is deterministic and works without an API key. The free
question-answering tab requires `DEEPSEEK_API_KEY` and the other optional
DeepSeek settings described by the adapter.

“知识掌握图谱”标签以关系图 + 分层浏览展示 Search Algorithms 的固定先修结构、已有审核学习证据
与系统估计掌握度。浏览节点或打开课程问答不会更新学习记录；只有完成已有的
人工审核确定性验证题才会更新 mastery。

## Diagnostic production boundary

Production diagnostic scoring is limited to human-verified canonical questions,
their reviewed prompt variants, and reviewed deterministic rubrics. It does not
turn an arbitrary student question into an LLM-generated diagnosis or score.
Student input may be mapped only to an already reviewed concept and diagnostic
template.
Before a new production diagnostic question is enabled, it needs explicit
criteria, blocking-misconception rules, human-verified positive and negative
examples, an authoritative benchmark case, and a learner-facing clarification
template. Optional semantic adjudication is advisory only: Python retains
authority over pass/fail, mastery evidence, learner state, and recommendation.

The P5b coverage-expansion batch has completed owner approval and controlled
promotion: eight reviewed templates are now visible to the production selector.
The staging document is empty (`candidate_status=promoted_to_production`), so
these templates use the same deterministic evidence gate as the existing bank.
The current inventory is 28 production templates, 0 active candidates, 1 blocked
slot, and 26 registered concepts. The derived primary-concept formal coverage is
21/26 (the pre-P5b registry measured 13/26); this adds narrow evidence slices
rather than claiming complete mastery or learning-effectiveness gains.
See
[`docs/diagnostics/p5b_reviewed_diagnostic_expansion.md`](docs/diagnostics/p5b_reviewed_diagnostic_expansion.md).

## 本地课程材料

课程 PDF 位于本地 `local_materials/`，不会进入 Git。CI 不下载或伪造 PDF；它使用
`data/course_material_manifest.json`、课程 chunk metadata 和模板 source refs 验证
文件名、source role 与物理页码。拥有真实材料的开发者可额外运行：

```bash
INTROAI_REQUIRE_LOCAL_MATERIALS=1 \
PYTHONPATH=src python tools/verify_local_course_materials.py --require
```

该命令验证 PDF 的 SHA-256、大小和页数。manifest 不包含课件正文，不能替代人工课程内容审核。

课程回答下的“查看引用课件”是可选的单页服务端预览。若本机已有经授权的本地 PDF，可配置：

```bash
export INTROAI_COURSE_MATERIALS_DIR=/path/to/course/materials
```

预览只接受 manifest 白名单中的 source 和 1-based physical page，使用本机 Poppler 渲染单页；未配置材料时，回答和 citation 仍可正常使用，只有预览显示不可用提示。详见 [docs/course_material_preview.md](docs/course_material_preview.md)。

## 本地学习记录

Streamlit 会在 URL 中维护匿名 `learner` UUID，并默认把最小学习状态保存在
`~/.introai_tutor/learner_state.sqlite3`。刷新或服务重启后，使用同一 URL 可恢复
本机档案。可用 `INTROAI_STATE_DB` 覆盖数据库路径；该数据库不会提交到 Git。

该功能不提供账号、云同步或跨设备恢复，也不会保存完整问题、回答、课程文本或 API 凭据。

## 组内内测（默认关闭）

只有在本地显式设置 `INTROAI_PILOT_MODE=1` 时，应用才会显示“内测任务与反馈”标签。该标签提供固定任务清单和下载式结构化反馈，不会自动上传、不会写入学习档案，也不收集题目、回答、证据、推荐或身份信息。内测说明见 [docs/pilot/tester_quickstart.md](docs/pilot/tester_quickstart.md)；负责人可离线汇总下载的 JSON：

```bash
PYTHONPATH=src python tools/summarize_pilot_feedback.py feedback_downloads --output-dir pilot_summary
```

负责人可在内测前运行 P4b 离线预检，并生成六人执行包：

```bash
PYTHONPATH=src python tools/pilot_preflight.py --strict --db-path /tmp/introai-pilot.sqlite3
PYTHONPATH=src python tools/generate_internal_pilot_pack.py --output-dir pilot_session_pack
```

预检不调用网络；启动脚本 `scripts/run_internal_pilot.sh` 会在 Streamlit 之前再次预检并显式开启 Pilot mode。角色用于测试分工，页面生成的 `G-XXXXXX` 仅用于匿名反馈文件识别。

P4c 受控访问说明见 [docs/pilot/controlled_access.md](docs/pilot/controlled_access.md)。绑定非本机地址时，启动脚本要求配置有效的 `INTROAI_PILOT_ACCESS_CODE`；访问码通过独立私密渠道发送，绝不会写入 URL、SQLite、反馈文件或日志。

六人异地短期内测可由负责人自行准备 `cloudflared` 后使用 `scripts/remote_pilot_ctl.sh` 统一管理 doctor/start/status/url/logs/restart/stop。该控制器仍只把 Streamlit 绑定到 `127.0.0.1`，以临时 HTTPS Quick Tunnel 转发，并强制要求访问码；它会在远程预检和受管子进程中自动启用 Pilot mode，不会改变普通应用模式。它把本地 health 和 Quick Tunnel URL 等待分开：URL 稍慢时保留健康受管实例，随后用 `status` 或 `url --wait 120` 获取本轮 URL。底层 `scripts/run_remote_pilot.sh` 仍可用于兼容场景。完整操作、进程安全和隐私边界见 [docs/pilot/remote_pilot_operator_guide.md](docs/pilot/remote_pilot_operator_guide.md) 与 [docs/pilot/remote_pilot_delivery.md](docs/pilot/remote_pilot_delivery.md)。

## 统计机器学习（statistical_ml）模块状态

> 本模块（第一阶段 Mini Unit）负责人为统计机器学习模块开发者，参考 Search Algorithms 的实现方式接入，不修改共享 mastery / recommendation / 公共接口。已按 multi-module 架构迁移：独立 per-module 文件 + `data/course_modules.json` 注册。

### 负责模块

统计机器学习（`module_id="statistical_ml"`、`unit_id="statistical_ml"`），课件依据为 lec8《统计机器学习算法》（南京大学《人工智能导论》）。

### 已完成知识点（5 个，concept ID 带 `statistical_ml__` 前缀）

| concept_id | 中文名 | 先修 |
| --- | --- | --- |
| `statistical_ml__supervised_vs_unsupervised` | 监督学习与无监督学习 | 无 |
| `statistical_ml__k_nearest_neighbors` | k近邻算法 | `statistical_ml__supervised_vs_unsupervised` |
| `statistical_ml__linear_regression_least_squares` | 线性回归与最小二乘 | `statistical_ml__supervised_vs_unsupervised` |
| `statistical_ml__logistic_regression` | 对数几率回归 | `statistical_ml__linear_regression_least_squares` |
| `statistical_ml__k_means_clustering` | K均值聚类 | `statistical_ml__supervised_vs_unsupervised` |

### 模块数据文件

- `data/statistical_ml_knowledge.json` — 5 个知识点
- `data/statistical_ml_chunks.json` — lec8 course chunks（`codex_draft`）
- `data/statistical_ml_manifest.json` — `ai_lec8_statistical_learning.pdf` 来源登记
- `data/statistical_ml_templates.json` — 生产模板（当前为空，待 promotion 后填充）
- `data/candidate_templates/statistical_ml_p1_candidates.json` — 9 道候选诊断题（`candidate_draft`）

### 候选诊断题（9 道，待人工审核）

| template_id | 题型 | 知识点 | scorer |
| --- | --- | --- | --- |
| `verify_supervised_vs_unsupervised_definition_v1` | single_choice | `statistical_ml__supervised_vs_unsupervised` | `single_choice_v1` |
| `verify_knn_k_value_effect_v1` | single_choice | `statistical_ml__k_nearest_neighbors` | `single_choice_v1` |
| `verify_knn_manhattan_distance_v1` | numeric_answer | `statistical_ml__k_nearest_neighbors` | `numeric_answer_v1` |
| `verify_linear_regression_least_squares_objective_v1` | single_choice | `statistical_ml__linear_regression_least_squares` | `single_choice_v1` |
| `verify_linear_regression_closed_form_intercept_v1` | numeric_answer | `statistical_ml__linear_regression_least_squares` | `numeric_answer_v1` |
| `verify_logistic_regression_is_classifier_v1` | single_choice | `statistical_ml__logistic_regression` | `single_choice_v1` |
| `verify_logistic_regression_sigmoid_range_v1` | single_choice | `statistical_ml__logistic_regression` | `single_choice_v1` |
| `verify_kmeans_steps_order_v1` | ordering | `statistical_ml__k_means_clustering` | `ordering_v1` |
| `verify_kmeans_limitations_v1` | single_choice | `statistical_ml__k_means_clustering` | `single_choice_v1` |

### 已知问题

- **模板尚未 human_verified**：`data/statistical_ml_templates.json` 当前为空；`load_diagnostic_templates` 要求非空 `human_verified` 模板，因此在 owner 审核并 promotion 之前，该模块无法被 `load_course_module_data` / `load_all_course_module_data` 加载（进而影响 `load_global_learning_catalog`）。
- **lec8 course chunks 为 `codex_draft`**：需人工核对课件原文后置 `human_verified`。
- **Search 模块的 `test_course_modules.py` 仍断言 26 概念**：这是 Search 专属断言，与 statistical_ml 模块隔离，不再互相影响。

### 如何测试

```bash
# 本模块候选数据测试（应全部通过）
PYTHONPATH=src python -m pytest tests/test_statistical_ml_candidates.py -q

# 模块注册/加载测试（Search 仍应通过；statistical_ml 因模板未 promotion 暂不能 load）
PYTHONPATH=src python -m pytest tests/test_course_modules.py -q
```
