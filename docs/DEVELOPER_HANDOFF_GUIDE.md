# IntroAI Tutor 开发者交接指南

> 面向第一次加入项目、准备为《人工智能导论》新增一个课程 Mini Unit 的开发者。本文以当前已完成的 Search Algorithms 模块为参考实现，说明应复用的工程边界与开发流程，而不是要求你重新设计一套教学系统。

## 1. Project Overview

IntroAI Tutor 是一个面向《人工智能导论》课程的、以课程材料为依据的学习支持原型。Search Algorithms 是当前完整的 reference implementation；系统现在通过中央课程模块 registry 支持其他 Mini Unit 按相同边界接入。学生可以围绕当前选择的课程模块自由提问、查看回答引用的课件来源、完成经人工审核的诊断验证题，并在满足正式证据条件时获得学习记录与下一步建议。

它不是“向模型提问、直接相信模型”的普通聊天机器人。系统把解释性学习与学习状态测量分开处理：

```text
本地课程材料与知识点
        ↓
问题理解 → 检索课程证据 → 基于证据的 QA → citation / 单页课件预览
        ↓                                  （不更新 mastery）
已审核的 diagnostic template → 确定性 scorer → 正式学习证据
        ↓
learner state / mastery 更新 → prerequisite-aware recommendation
```

其中，QA 帮助学生理解概念；正式验证题才负责产生可审计的学习证据。课程 PDF 是本地授权材料，不应加入 Git；仓库保存的是课程 chunk、manifest 与页码等可复现元数据。

## 2. Core Design Philosophy

### QA != Mastery Evidence

自由问答链会根据课程材料检索证据并生成带 citation 的回答。它可用于学习辅助、解释概念和帮助定位课件，但回答文本、点击行为、浏览图谱或阅读引用页面都不会更新 `mastery`。开放式形成性反馈也是教学支持，不是正式测量。

这样做是因为自然语言回答存在表达差异，模型输出也可能不稳定。系统可以用模型做受限的理解、检索或 advisory 反馈，但不能把一次模型判断直接转换为“学生已经掌握”的记录。

### Formal Evidence

当前生产中的 mastery 更新必须同时具备：

```text
human-reviewed diagnostic template
+ 明确的 expected answer
+ deterministic scoring
+ evidence-eligible completed verification
```

正式题由 `VerificationDiagnosticService` 使用既定 scorer 判分，完成后才由 `DiagnosticStateIntegrationService` 集中处理证据、辅助作答 provenance 与学习状态更新。复习同一题会被区分为 `practice_only`；提示、澄清或查看答案后的作答也不能冒充新的独立 mastery evidence。LLM 没有 pass/fail、mastery、learner state 或 recommendation 的最终决策权。

## 3. Search Algorithms Reference Implementation

Search Algorithms 是当前的 reference implementation，不是一次性的特殊案例。它已把以下链路串通：

- 课程材料：`data/course_chunks.json`、`data/course_material_manifest.json` 与本地受授权 PDF 提供来源、课件角色和物理页码边界；
- 知识结构：`data/knowledge_points.json` 目前登记 26 个概念及其先修关系，例如 `breadth_first_search`、`uniform_cost_search`、`a_star_search`；
- 正式诊断：`data/diagnostic_templates.json` 目前含 28 道 `human_verified`、`mastery_verification` 模板；
- 判分：现有生产模板使用单选或多选的确定性 scorer，答案以稳定 choice ID 提交；
- 学习状态：完成的未辅助 observation 才能进入 P5B integration；受帮助、重复练习与形成性互动保留其教学意义，但不被伪装成独立证据；
- 建议：`recommend_next_concept()` 基于已记录 mastery 与真实 prerequisite 图选择下一步，不把 recommendation 当作学习效果证明。

新单元应复制这套“课程依据 → 已审核题目 → 确定性证据 → 可追溯状态”的模式。不要因为新内容较小，就另建一套 learner state、自由文本判分器或推荐逻辑。

## 4. Architecture Overview

| 层 | 主要位置 | 职责 |
| --- | --- | --- |
| 课程模块 registry | `data/course_modules.json`、`course_modules.py` | 集中登记模块名称、全局唯一 `unit_id`、各模块自己的数据文件与默认诊断范围；不承载学习状态规则。 |
| 课程材料与知识结构 | 各模块在 registry 声明的 `*_chunks.json`、`*_manifest.json`、`*_knowledge.json` | 保存模块 chunk 元数据、来源页与概念/先修关系；QA 只接收当前模块的材料。 |
| QA 与 grounding | `question_understanding.py`、`retrieval.py`、`grounded_answering.py`、`tutor_service.py` | 理解问题、选择课程证据、生成受 citation 约束的回答。 |
| 引用预览 | `course_material_preview.py` | 在本地材料根目录和 manifest 白名单内安全渲染被引用的单页。 |
| 模板选择与验证 | `template_selection.py`、`verification_diagnostics.py`、`verification_scorers.py` | 只选择已审核模板，按题型做确定性计分并维护验证 session。 |
| learner state 与 integration | `learner.py`、`diagnostic_state_integration.py`、`learner_state_repository.py` | 校验、隔离、持久化最小 learner state，并在 evidence gate 后更新。 |
| 推荐 | `recommend.py` | 利用 mastery 与 prerequisite 关系生成下一概念建议。 |
| UI | `app.py`、`ui_*.py`、`mastery_map*.py` | 展示 QA、诊断、学习图谱、引用和本地 profile；UI 不重算学习证据。 |

调用边界可概括为：

```text
Student question
  → QuestionUnderstandingService → retrieval → GroundedAnswerService → TutorService
  → cited QA response (no learner-state write)

Reviewed template plan
  → TemplateSelectionService → VerificationDiagnosticService
  → completed evidence-eligible summary
  → DiagnosticStateIntegrationService → learner state → recommend_next_concept
```

`app.py` 是组合与展示层；业务规则应放在可离线测试的服务或纯函数中，而不是写入 Streamlit 回调。

## 5. New Module Development Workflow

第一阶段 Mini Unit 建议只选择 **3–5 个概念**。小而完整的链路比覆盖许多概念、却没有可审核证据更适合并行开发和课程验收。为避免多人同时修改同一个大 JSON，新模块应拥有自己的 knowledge、chunk、manifest 与 diagnostic template 文件；由 `data/course_modules.json` 统一登记路径。新增 registry entry 属于公共架构边界，提交前应请 owner review。

1. **阅读课程材料。** 先确认允许使用的课程来源、物理页和概念边界；不要用 chunk 摘要替代对原课件的内容审核。
2. **定义知识点。** 在已有 registry 规则下设计稳定、可读的 concept ID、中文/英文名称、说明、先修关系、目标和常见误解。concept ID 在整门课程内必须唯一；推荐以模块前缀命名（如 `ml_foundations__loss_function`），避免与其他成员碰撞。先修 ID 必须是现有或同批定义的有效 ID。
3. **设计 reviewed diagnostics。** 先写人工可审核的题干、唯一正确答案、合理干扰项、concept mapping、误解映射、教学支持和正负例；不要让 AI 直接把生成题投入 production。
4. **确认 expected answers。** 每道题都要明确其题型与可验证答案，并由课程 owner 审核题干、选项、答案和课程证据。未完成审核的内容只能留在候选/评审材料中，不能进入 production registry。
5. **接入已有 scorer。** 优先使用现有 `single_choice_v1` 或 `multiple_choice_v1`。题型、`deterministic_scorer` 与 expected answer 格式必须相互匹配；若需要新题型，先提出 architecture review，而不是在 UI 中临时判分。
6. **写功能测试。** 至少验证 loader/validator、模板选择、正确与错误答案、误解规则、evidence gate、学习状态隔离和 UI 提交的 choice ID/text 映射。测试使用合成 learner、临时目录和 fake adapter，不依赖真实 PDF、API 或个人数据库。
7. **提交 GitHub PR。** 在 PR 中说明课程证据、人工审核结论、受影响 concept、模板/测试范围与不触及的共享语义；通过项目质量门后再由 owner 决定 promotion。

### 模块注册与命名边界

每个 module entry 目前只登记实际接入所需的信息：`module_id`、中英文显示名、`unit_ids`、knowledge/chunk/template/manifest 文件路径，以及默认诊断 concept IDs。若模块已有开放式形成性轨道或知识图谱，可额外登记成对的相关文件；没有这些可选资产的模块仍可先提供受控 verification。

- `module_id`：稳定、全课程唯一，用于 UI 选择和服务组合；
- `unit_id`：保持现有 Search 的 `search_algorithms` 不变；新单元必须在全课程内唯一，避免迁移旧数据；
- `concept_id` 与 template ID：同样必须全课程唯一，因为 learner state、evidence persistence 与重复题保护按这些稳定 ID 工作；
- course material manifest：每个模块独立白名单 PDF basename、角色与物理页范围；不要散落修改旧 Search 白名单。

模块 owner 可以准备自己的数据、题目、测试与文档；涉及 registry schema、共享 service 接口、跨模块 prerequisite、推荐/证据语义或新 scorer 时，必须先做 architecture review。

## 6. Data Schema Guide

不要自行猜测字段。提交前请以 loader、validator 与现有 production JSON 为准。

### 知识点：模块自己的 knowledge 文件

顶层有课程元数据和 `knowledge_points` 列表，文件路径由 `data/course_modules.json` 指向。每个当前知识点使用：

```text
id, title_zh, title_en, module, description, prerequisites,
learning_objectives, common_misconceptions, mastery_criteria
```

`id` 是跨模板、推荐、图谱与 learner state 使用的稳定键；不要因文案修改而随意改名。`prerequisites` 不是展示标签，而是 recommendation 会实际读取的依赖关系。

### 正式诊断模板：模块自己的 template 文件

当前模板 schema version 为 1。每个模块可独立维护模板文件，registry loader 会聚合校验跨模块 template ID 是否重复。生产模板包含：

```text
id, schema_version, review_status, purpose, concept_ids,
eligible_intents, selection_priority, question_type, prompt, choices,
expected_answer, deterministic_scorer, misconception_rules,
teaching_support, benchmark_case_ids
```

正式模板必须是 `review_status="human_verified"` 且 `purpose="mastery_verification"`。template loader 会拒绝未知 concept、重复 template ID、空 choice text、无效 expected answer、未知 scorer 或 question type 不匹配等情况。

每个 `choice` 只有稳定的 `id` 和学生可见的 `text`。UI 显示 `text`，提交与 scorer 比较 `id`；二者都不能省略。当前生产中：

- `single_choice_v1` 对应 `single_choice`；
- `multiple_choice_v1` 对应 `multiple_choice`。

不要往 JSON 里添加“看起来有用”但 loader 不认识的字段；若确需扩展 schema，应先完成共享接口的架构评审与迁移计划。

### Learner state 与证据

`learner.py` 当前要求 learner state 至少有：

```text
student_id, course_id, mastery, learning_evidence, preferred_style
```

`mastery` 是 `concept_id → 0.0..1.0` 的 mapping；缺失值按未追踪处理。`misconceptions` 是当前实现允许的附加记录。开发者不应直接写入数据库或拼造 evidence summary；应通过已验证的 verification → integration 边界生成更新。

### 课程 chunk 与 citation

现有 course chunk 记录带有稳定 `id`、`source_file`、`page_start`、`page_end`、`section_title`、`topic_ids`、`content`、`source_role`、`review_status` 等信息。引用与预览只接受受控来源和有效物理页；新模块需要保持这一来源可追溯性，而不是把整份 PDF 或私人路径写进代码和测试。

## 7. What Developers MUST NOT Change

以下属于共享架构，未经 architecture review 不得在单元 PR 中修改：

- mastery 的证据语义、更新公式、assistance/repeat 的正式证据边界；
- learner state schema、SQLite persistence、learner UUID/profile 隔离规则；
- `recommend_next_concept()` 与 prerequisite-aware recommendation 逻辑；
- QA、diagnostic、integration、template-selection 等共享服务接口；
- production template 的审核、promotion、exposure 与 evidence gate 规则；
- 课程材料 manifest、安全来源白名单与 citation preview 的路径保护；
- `docs/evaluation/` 中的 P6/P6b/P7 测量与外部评估设计。

尤其要注意：P7 文件是研究准备和离线评估资料，并不授权招募参与者、采集真人数据或宣称已完成人体研究验证。若新单元确实需要改变上述任一边界，请在实施前提出 architecture review，明确问题、替代方案、迁移影响和测试计划。

## 8. AI/Codex Development Workflow

推荐的分工是：

- **人负责课程理解与内容责任**：阅读课件、界定概念、审核题干/答案/干扰项、确认课程证据；
- **AI/Codex 协助工程实现**：查找接口、生成受限的实现草案、补测试、运行离线验证、整理 diff；
- **人负责最终验证与批准**：确认内容没有超出课程、唯一正确答案成立、测试覆盖真实风险，并决定是否进入 production。

不要把 AI 自动生成的题目、rubric、答案或课程页码直接放入 production。对模型相关改动同样保持最小权限：不让模型决定 mastery、pass/fail、recommendation 或 learner state，不在日志/测试中暴露 API key、课程 PDF 或学生内容。

## 9. First Mini Unit Acceptance Checklist

在提交 PR 前逐项确认：

- [ ] 已定义 3–5 个稳定 knowledge points，并核对先修关系；
- [ ] 已识别可追溯的课程证据与物理页；
- [ ] 每道 diagnostic question 已完成人工内容审核；
- [ ] expected answers、选项文本与 concept mapping 已核对；
- [ ] 复用了已审核 deterministic scorer，或已获得新题型的 architecture review；
- [ ] loader、selector、scorer、integration 边界和 UI 映射的测试通过；
- [ ] 没有让 QA、开放式反馈、重复练习或辅助作答伪造正式 mastery evidence；
- [ ] 没有修改共享 mastery、recommendation、learner state 或研究评估语义；
- [ ] PR 说明了课程审核证据、测试结果和需要 owner review 的事项。

如有疑问，优先阅读相关模块的测试与 `docs/diagnostics/`、`docs/evaluation/` 中的既有决策记录，再向架构 owner 提出具体问题。这个项目的目标是让每个 Mini Unit 都能以同一套可解释、可测试、可审核的方式接入，而不是追求一次性堆叠功能。
