# P3d：人工审核验证题的重复证据政策

## v1 政策

同一匿名 learner profile 对同一 `human_verified` verification template，最多形成一次正式 mastery evidence。template 的稳定 ID 是唯一判断依据；题干、选项展示顺序和浏览器 session 都不参与判断。

- 首次未 exposure 的正式作答，仍按现有 deterministic scorer、assistance provenance 与 P5B 处理。
- 该 template 的首次提交、使用 hint 或展示答案都会创建 exposure。hint/reveal 本身不提高 mastery。
- 后续 session 的同 template 作答是复习练习（`practice_only`）：仍评分、给出已有反馈与解析，但不调用 P5B、不更新 mastery、不更新 recommendation，也不追加正式 evidence event。
- 不同 template 即使映射同一 concept，仍可各自提供一条正式 evidence；planner 在同一 primary concept 的多个模板中优先未 exposure 的模板。

这阻止学生通过立即记住同一道选择题答案反复提高掌握度。v1 不提供 cooldown 或间隔复测；未来需要可靠复测时，应引入不同人工审核 template ID 的 parallel form，或另行设计 spaced-retest policy。

## 持久化与隐私

SQLite 的 `reviewed_template_exposure` 仅保存 learner ID、template ID、首次 exposure 时间、受控 exposure reason 和 schema version。它不保存题干、选项文本、学生答案、自由问答、LLM 输出、课程材料或 API 凭据。

旧 schema 的已知 evidence event 会在迁移时按 learner/template 回填为一条 exposure，保留最早可用事件时间；无法可靠解析 template ID 的旧记录不会猜测。清空 profile 会同时清空 mastery、formal evidence 和 exposure；新 profile 使用新 UUID，因此 exposure 独立。

数据库暂时不可用时，policy 在当前服务生命周期保留保守的内存 exposure，尽量防止当前 session 内重复计入；跨重启保护无法保证，UI 显示持久化降级提示。
