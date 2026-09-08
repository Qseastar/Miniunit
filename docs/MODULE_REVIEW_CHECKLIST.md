# 模块开发验收 Checklist

本清单用于验收一个新课程 Mini Unit 的 PR。它关注课程内容、确定性证据边界和协作质量；不替代课程内容负责人的人工审核。

## Content Review

- [ ] 知识点均有明确课程材料依据。
- [ ] 知识点数量合理，首批范围控制在 3–5 个核心概念。
- [ ] diagnostic 覆盖核心概念，而非只覆盖边缘术语。
- [ ] 每道题的题干、干扰项、正确答案和课程依据均经过人工确认。
- [ ] 不存在第二个同样合理的正确答案，或已按题型规则妥善处理。

## Technical Review

- [ ] knowledge point 与 diagnostic template 数据格式通过现有 loader/validator。
- [ ] choice ID 稳定、choice text 非空且学生可读。
- [ ] 题型、`expected_answer` 与 deterministic scorer 正确匹配。
- [ ] 正确、错误及关键误解路径有自动化测试。
- [ ] learner state 只由完成的 evidence-eligible reviewed verification 更新。
- [ ] QA、开放式反馈、辅助作答和重复练习没有被伪造为新的独立 mastery evidence。
- [ ] 未修改共享 mastery、recommendation、learner state、evidence gate 或 scoring semantics。

## Git Review

- [ ] 变更通过 GitHub PR 提交，PR 写明课程证据与人工审核结论。
- [ ] 定向测试和项目要求的测试均通过。
- [ ] `git diff --check` 通过，diff 范围与 Mini Unit 目标一致。
- [ ] 未提交课程 PDF、个人数据库、日志、API key、`.env` 或其他运行时产物。
- [ ] 未修改 `docs/evaluation/`、Study A / P7 或 production evaluation 设计；如确有必要，已单独获得 architecture review。
