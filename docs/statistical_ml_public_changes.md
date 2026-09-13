# Statistical ML 模块 — 公共文件改动说明

> 为支持统计机器学习（Statistical ML）模块的知识图谱渲染，本 Mini Unit 修改了 3 个
> 公共框架文件。本文逐个说明改动内容、原因、向后兼容性、测试情况与回归原仓库时的
> owner 注意事项。**这 3 处均属 `ARCHITECTURE_REVIEW_REQUIRED`**，合并回
> `leyangzhang0711-byte/introai-tutor` 前需要 owner 进行 architecture review。

## 背景：为什么必须改

Search Algorithms 是首个模块，其掌握图谱层名在 `mastery_map_visualization.py` 中
以模块级常量 `LAYER_STAGE_NAMES` 硬编码为 10 个学习阶段（对应 Search 的 10 层）。
Statistical ML 的掌握图谱只有 7 层（0–6），且层名完全不同。若不放宽该硬编码，
`build_visual_mastery_map_model` 会因「层数与硬编码层名集合不一致」直接抛
`MasteryMapError`，导致新模块的图谱无法渲染。

因此，最小改动方案是：让「层名」可从模块 registry 动态传入，未传入时仍回退到原有
硬编码常量——既解除了单一模块的耦合，又保持 Search 行为完全不变。

---

## 1. `src/introai_tutor/mastery_map_visualization.py`

- **具体改动**：`build_visual_mastery_map_model(...)` 新增可选关键字参数
  `stage_names: dict[int, str] | None = None`；函数体新增一行
  `effective_stage_names = LAYER_STAGE_NAMES if stage_names is None else stage_names`，
  并将函数内原本 3 处直接引用 `LAYER_STAGE_NAMES` 的地方改为 `effective_stage_names`。
- **为什么必须改**：原实现硬编码 `LAYER_STAGE_NAMES` 作为唯一合法的层名来源，无法表达
  statistical_ml 的 7 层结构。
- **是否向后兼容**：是。`stage_names` 缺省为 `None` 时，行为与改动前完全一致
  （仍使用 `LAYER_STAGE_NAMES`）；所有既有调用方无需改动。
- **相关测试**：`tests/test_mastery_map_visualization.py` 全部通过（该文件原有测试均
  不传 `stage_names`，覆盖了默认回退路径）。
- **是否 ARCHITECTURE_REVIEW_REQUIRED**：是。
- **owner 注意**：确认「层名可注入」这一契约是否符合多模块图谱的长期方向；若 owner
  更倾向于「每模块一份布局+层名聚合视图」而非注入参数，本改动可作为过渡方案替换。

## 2. `src/introai_tutor/course_modules.py`

- **具体改动**：
  1. 在 `_MODULE_OPTIONAL_FIELDS` 中新增 `"mastery_map_stage_names"`（可选字段）；
  2. 在 `validate_course_module_registry` 中，当 module entry 包含该字段时，调用新增的
     校验函数 `_stage_names(...)` 解析并写入 `item["mastery_map_stage_names"]`；
  3. 新增 `_stage_names(value, field_name) -> dict[int, str]`：要求非空对象，键为
     非负整数字符串（或整数）→ 归一化为 `int`，值为非空字符串。
- **为什么必须改**：registry 需要把模块专属的层名数据安全地传递到渲染层；若不扩展
  registry 字段，`app.py` 无法拿到 statistical_ml 的层名。
- **是否向后兼容**：是。字段为**可选**；未声明的模块（含 Search）不携带该键，
  `resolve_course_module`/`load_course_module_data` 输出中也不出现该键，下游回退到
  默认层名。Search 的 registry entry 无需任何改动。
- **相关测试**：`tests/test_course_modules.py` 全部通过（含 registry schema 校验、
  模块隔离等既有用例）；新增字段不影响既有断言。
- **是否 ARCHITECTURE_REVIEW_REQUIRED**：是。
- **owner 注意**：`mastery_map_stage_names` 属于 registry schema 的可选扩展，按
  `NEW_MODULE_QUICKSTART.md`「不要自行扩展 registry schema」的要求，需 owner review
  确认字段命名与校验语义后再合并。

## 3. `app.py`

- **具体改动**：
  1. 在 QA 示例文案分支中为 `statistical_ml` 模块新增 `st.caption(...)` 与
     `placeholder` 示例（监督/无监督区别、k 值、对数几率回归等）；
  2. 在 `introai_mastery_map_static_inputs` 字典中新增
     `"stage_names": data["module"].get("mastery_map_stage_names")`；
  3. 在调用 `build_visual_mastery_map_model(...)` 时新增
     `stage_names=static_inputs.get("stage_names")`。
- **为什么必须改**：(a) 不同模块需要各自的 QA 示例文案；(b) 需要把 registry 中的
  `stage_names` 透传给图谱渲染函数。
- **是否向后兼容**：是。对 Search 模块，其 registry entry 无 `mastery_map_stage_names`，
  `stage_names` 为 `None`，`build_visual_mastery_map_model` 回退到 `LAYER_STAGE_NAMES`，
  渲染结果不变；QA 示例文案仅新增一个 `statistical_ml` 分支，未改动 Search 分支。
- **相关测试**：`tests/test_streamlit_app.py` 全部通过。
- **是否 ARCHITECTURE_REVIEW_REQUIRED**：是。
- **owner 注意**：`app.py` 是组合层，`stage_names` 的透传方式（放在 static inputs 中、
  用 `module.get(...)` 兜底）需 owner 确认是否符合现有「UI 不重算业务语义」的边界。

---

## 汇总

| 文件 | 改动性质 | 向后兼容 | ARCHITECTURE_REVIEW_REQUIRED |
| --- | --- | --- | --- |
| `src/introai_tutor/mastery_map_visualization.py` | 新增可选参数 `stage_names` | 是 | 是 |
| `src/introai_tutor/course_modules.py` | 新增可选 registry 字段 + 校验 | 是 | 是 |
| `app.py` | 新增模块示例文案 + 透传 `stage_names` | 是 | 是 |

三处改动均**不触碰** `recommend.py`、mastery 证据语义、learner state schema、证据门、
确定性 scorer 注册表或生产模板审核/promotion 规则。
