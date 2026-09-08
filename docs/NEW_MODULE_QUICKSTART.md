# 新模块快速开始

你将为《人工智能导论》开发一个新的课程 Mini Unit。第一阶段不要覆盖整章内容：请选择 **3–5 个核心知识点**，完整接入现有模式。

```text
课程材料 → 知识点 → 人工审核验证题 → 确定性评分 → 正式学习证据
```

自由问答可以帮助学生理解课程内容，但不会更新学习记录；只有已有框架中的正式验证题才能形成 mastery evidence。

## Step 1：理解课程材料

先阅读你负责部分的课程材料，写出一份简短的 module overview，并确定 3–5 个核心 knowledge points。

每个知识点应当：

- 有明确的课程材料依据；
- 有稳定的 concept ID、中文名称与简明说明；
- 能说明与已有知识点的先修关系；
- 不把整章所有术语都当作独立知识点。

不要把私人 PDF、绝对本地路径或课程全文提交到 Git。需要引用页码时，按项目已有的课程材料与 manifest 约定记录可追溯来源。

为减少多人并行修改冲突，请为你的 Mini Unit 单独准备 knowledge、course chunks、course-material manifest 和 diagnostic templates JSON 文件；不要直接把新内容塞进 Search Algorithms 的数据文件。随后在 `data/course_modules.json` 提出一个 module entry：它需要稳定的 `module_id`、全课程唯一的 `unit_id`、中英文显示名、上述文件路径和默认 diagnostic concept IDs。registry entry 需要 owner review；不要自行扩展 registry schema。

## Step 2：设计 diagnostic questions

为每个核心知识点至少准备一道 review question。题目必须：

- 来自已核对的课程材料；
- 有唯一、明确的正确答案；
- 可由已有 deterministic scorer 自动评分；
- 有能体现教学区分的干扰项；
- 经课程内容负责人人工确认。

先在评审材料中完成题干、选项、答案和课程证据的审核，再进入 production template registry。不要让 AI 自动生成的题目未经人工复核直接上线，也不要用开放式 LLM 判分创建正式 mastery evidence。

## Step 3：接入系统

优先复用现有数据格式和服务边界：

- 把 knowledge points 接入知识点 registry；
- 把已审核题目接入 template registry；
- 为每道选择题提供稳定的 choice ID 和学生可见的 choice text；
- 使用与题型匹配的现有 scorer；
- 为 loader、template selection、scorer、正确/错误答案和 UI 提交补充测试。

`concept_id` 与 template ID 会进入 course-wide learner state / evidence persistence，因此必须在整门课程内唯一。建议使用模块前缀，例如 `ml_foundations__loss_function` 与 `verify_ml_foundations_loss_v1`。现有 Search 的 ID 不应改名。

课程模块下拉框、QA 材料范围、citation manifest、diagnostic template selection 都由 module registry 解析；模块 owner 不需要也不应在 `app.py` 里手写新的白名单或切换分支。

不要在新模块中修改 `recommend.py`、mastery 更新语义、learner state schema、evidence gate 或共享 diagnostic 接口。若现有 scorer 无法表达你的题目，应先发起 architecture review。

## Step 4：提交 PR

提交前确认：

- [ ] 没有修改公共框架或已有课程模块的业务语义；
- [ ] 新 knowledge points、题目和 expected answers 已由人工审核；
- [ ] 新增了与功能对应的离线测试；
- [ ] 现有测试没有回归；
- [ ] diff 只包含本 Mini Unit 必需的代码、数据、测试和说明；
- [ ] PR 说明了课程证据、审核结论和需要 owner 决定的事项。

如果不确定某个字段、服务入口或测试方式，先阅读 [DEVELOPER_HANDOFF_GUIDE.md](DEVELOPER_HANDOFF_GUIDE.md)、相邻模块的测试和 `docs/diagnostics/` 中的记录；不要靠猜测添加新 schema 字段。
