# Reviewed Diagnostic Template 贡献指南

## 目标与非目标

贡献者提交的是可人工审核的 candidate，不是生产题、更不是自动 mastery 规则。候选只能
位于 `data/candidate_templates/`，状态必须为 `candidate_draft`；只有负责人批准后才可
独立 promotion 为 `human_verified`。

## 最小流程

1. 从现有知识图选择一个真实 `concept_id`，并写清楚单一能力切片。
2. 用当前精简 PDF 的物理页码定位课程原文；记录 chunk、文件、页码与证据强度。
3. 设计一个封闭、唯一答案的题面。题面应声明所有会影响唯一性的条件。
4. 优先复用现有 `single_choice_v1` 或 `multiple_choice_v1`；不得为一题扩张 UI。
5. 使用稳定 choice ID；调整显示位置时只移动 choice object，不改 ID 或答案。
6. 写学生可见的 hint / explanation，并写明不测什么。
7. 增加 correct、wrong、malformed acceptance case、source 解析与位置断言。
8. 写候选审核卡，负责人决定留空；通过自动测试后等待人工课程审核。

## 选择 concept 与课程证据

- 一个 candidate 默认只写一个主要 `concept_id`；supporting concept 不写入 evidence。
- `direct`：页面直接给出规则；`supported_inference`：题面给出封闭情境，仅做有限推断；
  `insufficient`：不能起草为可晋级候选。
- 不用 chunk 摘要代替 PDF 页面，不用 prerequisite support 替代 AI 主课件定义。
- 不要从常见教材、网络或个人记忆补足课件没有说出的 algorithm contract。
- `context_only` 只能标记章节标题或连续上下文页；不得用它绕过 primary concept topic
  coverage，也不得标记核心证据页。若需明确核心来源，可用 `primary_evidence=true`，但它
  必须是非 context、topic-matching 的 source ref。

## 唯一答案与 scorer

- `single_choice_v1`：一个 choice ID 唯一正确；拒绝未知或非字符串答案。
- `multiple_choice_v1`：只有 exact-match 合理时才使用；所有正确项和错误项都必须由课程
  直接排除或支持。
- 不要把“答案看起来合理”当作可评分条件。并列、tie、未说明图搜索时点或实现细节时，
  要么补题面条件，要么标记 `REVISE` / `BLOCKED`。
- 不创建未经审核的 misconception ID；不唯一的错误只给 reviewed hint。

## 位置、反馈与能力边界

- 先保证内容正确，再按 `diagnostic_answer_position_policy.md` 规划静态位置；禁止 runtime
  shuffle。
- Hint 只帮助学生重新思考；Explanation 说明本题为什么成立，不能声称学生完整掌握
  整个 concept、算法最优性或所有实现。
- 明确写出本题不测的相邻能力，例如 “单边 consistency 不证明全局 consistency”。

## 必须 BLOCKED 的情况

- 找不到直接或可明确限定的课程证据；
- 有第二合理答案且无法通过题面消除；
- 必须新增 production schema、scorer、UI 或 learner-state 语义；
- 必须使用开放式自然语言或 LLM 评分才能可靠计分；
- 为了凑覆盖数而重复既有 production capability。

## 不得进入 production 的情况

- `candidate_draft` 尚未负责人 approve；
- source page、answer、hint、explanation 或 concept mapping 未签署；
- acceptance、source、malformed、position 或 isolation 测试缺失；
- 候选要求修改 mastery、recommendation、P5B、evidence gate 或全局 selector。

## 虚构示例（不可进入 production）

“给一张未提供课程来源的复杂随机图，让学生写任意最短路径”应标记 `BLOCKED`：它没有
明确多解/tie 规则，要求新的图路径 scorer 和 UI，也无法由单一 source page 审核。

## 团队节奏

- 每周轻检查：新增 candidate 的 source、唯一答案、acceptance case 和审核卡。
- 每两周正式验收：负责人逐题填写 approve/revise/reject，再用独立 promotion 变更处理
  已批准模板。

## P2g 工具链

在提交 candidate 前，先阅读并运行：

- [质量门禁设计](verification_quality_gate_design.md)；
- [质量门禁使用说明](verification_quality_gate_usage.md)；
- `python tools/verification_quality_gate.py --lint-candidate ...`；
- [审核包](generated/search_algorithms_template_review_packet.md)；
- [intent 矩阵](template_intent_coverage_matrix.md)；
- [source traceability](../reports/verification_source_traceability.md)；
- [capability coverage](../reports/search_algorithms_capability_coverage.md)；
- [故障排查](verification_quality_gate_troubleshooting.md)；
- [CI/local parity](ci_local_parity.md)；
- `tests/verification_benchmark_manifest.py`（由现有 acceptance contracts 派生）。
- [source-role contract](source_evidence_role_contract.md) 与
  `python tools/source_role_inventory.py ...`。

这些工具只做结构和证据元数据检查；候选仍必须保持 `candidate_draft`，直到负责人完成内容审核与独立 promotion。
