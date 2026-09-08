# Recommendation Evidence-Ceiling Deadlock Fix

## 问题

生产掌握度估计保持 `M_new = 0.65 * M_old + 0.35 * selected_signal`，而同一 reviewed template 的后续作答保持 `practice_only`。因此从零开始连续两次独立正确时，掌握度为 `0.5775`，仍低于 recommendation 的弱项阈值 `0.6`。当一个知识点仅有两道可贡献正式证据的题时，旧 recommendation 仍会反复推荐该低分知识点，尽管不存在新的独立正式 evidence opportunity。

这不是 Demo 特例，也不表示 `0.5775` 应被改写为已掌握；它是数值掌握度与下一步动作可执行性被混用产生的 production deadlock。

## 修复语义

`mastery < 0.6` 仍表示弱项。新的 `ReviewedEvidenceCatalog` 只在 application composition root 注入，并对每个知识点区分：

- `formal_evidence_available`：仍有未使用的 reviewed formal template；继续优先该知识点。
- `evidence_exhausted_strong`：该知识点的当前 reviewed template 都已独立通过，且没有关联未解决 misconception；它仍可低于 `0.6`，但不再阻塞后续仍有正式证据机会的知识点。
- `evidence_exhausted_review`：题目机会用尽，但有错误、未知旧结果或受辅助结果；返回真实的复习／练习建议，不宣称已掌握，也不推进为新的正式 evidence。
- `unresolved_misconception`：关联 misconception 仍在；保留复习／练习动作，不忽略误解。
- `no_formal_template`：当前没有正式验证题；保守地提示结合课件复习，不把知识点自动标为已掌握或跳过。

新完成且含独立 observation 的 summary 会先以最小 `template_outcomes` 进入当前会话 learner state，避免用户不刷新就继续验证时遗漏前一条 evidence；reveal-only summary 仍只作为 transient recommendation context。持久化后，现有 SQLite evidence payload 中已保存的每题 `status` 和 `final_attempt_assistance_level` 会恢复为相同的安全 `template_outcomes`。不保存学生答案、题干、rubric、模型输出或 secret，也不需要 SQLite migration。

## 不变项

- `observation_weight=0.35` 与 mastery 公式不变；
- repeat template 仍为 `practice_only`，不会新增 formal evidence；
- assisted/reveal 结果仍不冒充独立 evidence；
- production template registry、prerequisite graph、P5B 与 recommendation 的 registry 顺序不变；
- 本修复不改变 Study A 的 P0 estimator。Study A 不研究 recommendation effectiveness，因此 recommendation actionability 属于其范围外。

## 断言边界

本修复只保证 recommendation 不会把“当前所有独立正式题已正确完成但数值仍低于阈值”的知识点当成持续的 prerequisite deadlock。它不证明 learner 已掌握该概念，不创建新题，不使错误或受辅助 evidence 自动进阶，也不解决无 formal template 知识点的内容覆盖缺口。
