# Deterministic Scorer Contract

## 1. 职责边界

Deterministic scorer 只判断一个 reviewed mastery-verification template 的受控答案。

它负责：

- 校验本题的 expected-answer 配置；
- 校验学生答案的类型、稳定 ID 和数值边界；
- 返回确定性的二元评分；
- 对错误答案返回模板中已经审核的 hint。

它不负责：

- 选择 concept 或 template；
- 理解自由自然语言；
- 调用 LLM、网络或环境配置；
- 直接创建 learner-state observation；
- 修改 learner state、mastery、recommendation 或 assistance provenance；
- 绕过 `evidence_eligible` gate；
- 计算部分分。

## 2. Registry 与通用调用约定

运行时 registry 位于 `VerificationDiagnosticService`，按模板字段
`deterministic_scorer` 查找 scorer：

```text
scorer(template: dict, answer: JSON-safe value) -> {
  "score": 0.0 | 1.0,
  "passed": bool,
  "misconception_ids": list[str],
  "feedback": list[str]
}
```

当前 registry 名称：

- `single_choice_v1`
- `multiple_choice_v1`
- `numeric_answer_v1`
- `ordering_v1`

`score` 与 `passed` 必须一致：

- 正确：`score=1.0`、`passed=true`；
- 错误：`score=0.0`、`passed=false`。

未知 scorer、question type/scorer 不匹配、非法 expected answer 或非法 scorer 返回值都会 fail closed。

## 3. Common template boundary

现有 template 顶层 schema 不变。新 scorer 继续使用：

- `review_status="human_verified"`；
- `purpose="mastery_verification"`；
- `question_type`；
- `choices`；
- `expected_answer`；
- `deterministic_scorer`；
- `misconception_rules`；
- `teaching_support`。

P2b 没有定义新 scorer 的 misconception-rule predicate schema。为避免 silently ignored configuration：

- `single_choice_v1` 保留现有 choice-to-misconception rules；
- `multiple_choice_v1`、`numeric_answer_v1`、`ordering_v1` 当前要求 `misconception_rules=[]`；
- 新题仍可用 reviewed hint/explanation；
- 将来如需组合选择或数值区间 misconception，必须单独版本化规则 schema。

所有 template、answer、session 和 history 数据必须能用标准 JSON 序列化，且不得包含 NaN 或 Infinity。

## 4. `single_choice_v1`

现有 contract 保持不变：

```json
{
  "question_type": "single_choice",
  "choices": [
    {"id": "option_a", "text": "虚构选项 A"},
    {"id": "option_b", "text": "虚构选项 B"}
  ],
  "expected_answer": {"choice_id": "option_a"},
  "deterministic_scorer": "single_choice_v1"
}
```

学生答案为一个非空 choice-ID string。未知 ID、空字符串和非字符串拒绝，不创建 attempt。

旧 history 继续保存：

- `selected_choice_id`
- `expected_choice_id`

## 5. `multiple_choice_v1`

### Template schema

```json
{
  "question_type": "multiple_choice",
  "choices": [
    {"id": "option_a", "text": "虚构选项 A"},
    {"id": "option_b", "text": "虚构选项 B"},
    {"id": "option_c", "text": "虚构选项 C"}
  ],
  "expected_answer": {
    "choice_ids": ["option_a", "option_c"]
  },
  "deterministic_scorer": "multiple_choice_v1",
  "misconception_rules": []
}
```

### Student answer

```json
["option_c", "option_a"]
```

### Correctness

- 以集合完全相等判断，提交顺序无关；
- 少选、多选或选错已知选项均为 `0.0/false`；
- 不提供部分分。

### Malformed input

以下情况抛出 `VerificationDiagnosticError`，不创建 attempt：

- 非 list 或空 list；
- 重复 ID；
- 未知 ID；
- 非字符串或空白 ID。

Expected `choice_ids` 必须是非空、唯一且全部来自 `choices` 的 list。

## 6. `numeric_answer_v1`

### Template schema

精确匹配：

```json
{
  "question_type": "numeric_answer",
  "choices": [],
  "expected_answer": {"value": 12},
  "deterministic_scorer": "numeric_answer_v1",
  "misconception_rules": []
}
```

带 absolute tolerance：

```json
{
  "expected_answer": {
    "value": 12.5,
    "absolute_tolerance": 0.1
  }
}
```

`value` 和 `absolute_tolerance` 必须是有限 JSON number；bool 不属于 number。Tolerance 缺省为 0，且不得为负。

### Student answer

支持：

- 有限 `int`；
- 有限 `float`；
- 可安全解析的普通十进制 string，例如 `"12.50"`、`"-2"`、`".5"`。

内部使用 `Decimal` 比较：

```text
abs(student - expected) <= absolute_tolerance
```

### Malformed input

拒绝：

- 空字符串；
- bool；
- NaN、Infinity；
- 数学表达式，例如 `"1+1"`；
- 科学计数字符串，例如 `"1e2"`；
- 单位、分数、根式或符号代数；
- 非数值对象。

不使用 `eval`，不提供 relative tolerance 或单位换算。

## 7. `ordering_v1`

### Template schema

```json
{
  "question_type": "ordering",
  "choices": [
    {"id": "item_a", "text": "虚构步骤 A"},
    {"id": "item_b", "text": "虚构步骤 B"},
    {"id": "item_c", "text": "虚构步骤 C"},
    {"id": "unused_d", "text": "虚构干扰项 D"}
  ],
  "expected_answer": {
    "ordered_choice_ids": ["item_a", "item_b", "item_c"]
  },
  "deterministic_scorer": "ordering_v1",
  "misconception_rules": []
}
```

### Student answer

```json
["item_a", "item_b", "item_c"]
```

### Correctness

- list 长度和每个位置必须完全相等；
- 少项、多项、交换或逆序均为 `0.0/false`；
- 不提供邻接、编辑距离、Kendall tau 或部分顺序得分。

### Malformed input

非 list、空 list、重复 ID、未知 ID、非字符串 ID 均拒绝且不创建 attempt。Expected sequence 也必须非空、唯一并引用已定义 choices。

## 8. History 与向后兼容

- 三个现有生产模板无需迁移，继续写 legacy choice fields。
- 新 scorer 的 history 写：
  - `submitted_answer`
  - `expected_answer`
- 两种 history schema 都由当前 template 的 scorer 类型严格验证。
- Session 恢复时会重新运行对应 deterministic scorer，拒绝分数、答案或 misconception evidence 被篡改的 history。
- 新旧 history 都保持 JSON serializable。

## 9. Evidence gate

Scorer 返回值先进入 verification attempt/history。只有：

1. verification session completed；
2. summary 明确 `purpose="mastery_verification"`；
3. summary 明确 `evidence_eligible=true`；
4. `DiagnosticStateIntegrationService` 验证 summary；

才可能更新 mastery。

现有安全语义不变：

- 未完成 attempt 不产生 completed summary；
- malformed answer 不产生 attempt；
- reveal-only 不产生 observation；
- hint-assisted correct 可推进题目，但 P5B 仍选择最后一次 unassisted observation；
- formative/open response 不能进入 P5B；
- scorer 从不接收 learner state。

## 10. 当前不支持

- 新 scorer 的组合/区间 misconception predicates；
- partial credit；
- relative tolerance；
- 单位、表达式或符号计算；
- fuzzy text matching；
- 重复 ordering items；
- drag-and-drop UI；
- small-graph path scoring；
- LLM 评分。

本文件中的全部 template 示例均为虚构 contract 数据，不属于生产题库。
