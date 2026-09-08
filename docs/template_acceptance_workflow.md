# Reviewed template 验收流程

## 1. 目标与边界

本流程把可自动证明的工程 contract 与必须由课程负责人判断的教学内容分开。
模板只有在两类检查都通过后，才可进入
`data/diagnostic_templates.json` 并成为正式 mastery evidence 来源。

候选材料可以暂存在 `data/candidate_templates/`，但候选状态不等于
`human_verified`。生产 loader、selector、QA handoff 和 verification session
不得读取候选文件。

## 2. A：自动验证

每个拟进入生产的模板必须加入数据驱动的 acceptance case table，并通过以下检查：

- production schema validation；
- template ID 与 choice/item ID 唯一；
- concept ID 存在，且默认只映射一个主要 mastery concept；
- 多 concept 映射具有明确理由和专项测试；
- question type、expected answer 与已注册 deterministic scorer 匹配；
- source chunk、文件和当前课件物理页码可解析；
- 至少一个非 `context_only` source ref 覆盖 primary concept；章节或连续页上下文不能替代
  primary evidence；
-标准正确答案得到 `score=1.0`、`passed=true`；
- 至少一个确定性错误答案得到 `score=0.0`、`passed=false`；
- malformed answer fail closed，且不创建 attempt；
- scorer 和 service 结果可 JSON serialization；
- 相同输入重复执行结果一致；
- completed summary 能通过现有 evidence pipeline；
- incomplete、非法提交和 reveal-only 不产生正 mastery evidence；
- supporting concept 不被误作独立 mastery target；
- unknown concept、unknown scorer 和非法配置继续 fail closed；
- stable choice ID 与 reviewed display order 分离且重复加载顺序一致；
- 相同 choice count 的 single-choice production 答案位置分布通过
  `diagnostic_answer_position_policy.md` 的均衡门禁；
- multiple-choice 正确项不因无教学理由而全部连续集中在列表前部；
- 只有涉及新 eligibility 时，增加 selector / QA handoff 回归测试。

自动测试必须复用现有 template validator、scorer registry、
`VerificationDiagnosticService` 和 `DiagnosticStateIntegrationService`，不得复制第二
套 production pipeline。

## 3. B：人工课程审核

课程负责人只需审核无法由代码证明的内容：

- 题干是否准确、清楚且无歧义；
- 选项是否互斥或符合多选题语义，且不存在意外的第二个正确答案；
- 标准答案是否正确；
- 指定 source、chunk 和页码是否真实支持题目与答案；
- misconception、hint 和 explanation 是否教学上合理；
- mastery concept 映射是否合理，supporting concept 是否被正确排除；
- 正确答案显示位置是否符合当前 production 分布，且选项顺序没有泄露答案；
- 题目难度和表述是否适合目标学生。

审核结论必须由负责人明确填写为 `approve`、`revise` 或 `reject`。Codex 草稿不得
自行标记为 `human_verified`。

## 4. C：UI 人工 smoke test

人工 UI 测试按 question type 和变更风险抽样，不逐题穷举：

- 每种新 question type 第一次接入 UI 时，完整人工测试一次；
- 同题型后续模板主要依靠自动 acceptance tests；
- 每个新增模板批次随机抽查 1—2 道；
- 发布前运行固定跨题型 smoke suite；
- 只有 selector、session、handoff、assistance 或 evidence 行为发生变化时，才重新
  执行对应人工路径。

用户不需要对未来 21 道模板逐题、逐分支手动点击。

发布前固定命令：

```bash
PYTHONPATH=src python -m pytest -m smoke -ra
```

## 5. 候选晋级步骤

1. 在独立候选文件中起草模板与 acceptance cases，使用
   `review_status="candidate_draft"`。
2. 运行候选 schema、source、positive、negative、malformed、JSON 和生产隔离测试。
   `context_only` 页必须说明其上下文用途，且不能代替核心 evidence source。
3. 由课程负责人填写候选审核文档的结论。
4. `revise` 时只修改候选材料并重新审核；`reject` 时不进入生产。
5. 只有 `approve` 后，才在独立变更中把已批准模板复制到
   `data/diagnostic_templates.json`，并显式改为
   `review_status="human_verified"`。
6. 根据当前同 choice-count production 分布确定静态显示位置，并运行答案位置审计；
   不得用运行时 shuffle 或重命名 choice ID 代替。
7. 同步把该模板加入 production acceptance case table；如需新 intent eligibility，
   增加 selector / QA handoff 专项测试。
8. 只有内容审核、expected answer 和位置分布检查均通过后，才执行 production
   promotion。
9. 运行定向测试、固定 smoke suite 和全量测试，再进行该批次 1—2 道 UI 抽查。

候选晋级不是自动操作；审核结论、生产数据变更和测试更新必须在代码审查中可见。
