# Diagnostic Answer Position Policy

## Why answer-position balance matters

受控验证题的正确答案如果长期集中在同一显示位置，学生可能利用位置规律而不是课程
知识作答。这样既削弱题库的人工设计感，也会让 mastery evidence 混入与知识无关的
位置偏差。

位置均衡是题库级质量门禁，不替代课程内容审核。题意正确、答案唯一和课程证据充分
始终优先于位置统计。

## Stable IDs versus display order

- choice ID 表示选项的稳定语义身份。
- `choices` 数组顺序决定学生看到的显示位置。
- `expected_answer` 引用稳定 choice ID，不引用 A/B/C/D 或数组索引。
- 调整显示位置时只移动完整的 choice object，不重命名 ID，也不改变 choice text、
  expected answer、scorer、concept mapping 或 evidence。
- attempt、history 和 reveal 继续记录或解析 choice ID，而不是视觉字母位置。

## No runtime randomization

Production 不在应用启动、页面刷新、attempt 或不同 session 中随机打乱选项。静态、
经过审核的 JSON 顺序可以保证：

- 同一题可复现；
- AppTest、录屏和人工审核一致；
- 刷新和 rerun 后顺序不变；
- history 与显示内容可解释；
- 不需要在 session 中增加随机种子或另一套映射状态。

## Production balance rule

位置按 1-based 计数，分别对应视觉上的 A、B、C、D。

对 choice 数量相同的 production `single_choice_v1` 模板：

- 正确位置应尽量均衡使用所有可用位置；
- 最大使用次数与最小使用次数之差原则上不得超过 1；
- 四选一模板数量达到 4 后，A/B/C/D 原则上都必须至少出现一次；
- 第一位置使用次数不得高于该组均衡分配时的上界；
- 新模板优先使用当前 production 同组中使用次数最少的位置；
- 如课程语义确实要求固定顺序，必须以小型显式 allowlist 记录模板和理由。

当前 production 不需要位置例外。运行时不得为满足该规则自动 shuffle。

## Candidate authoring rule

候选题起草和晋级时：

1. 先保证题意、选项、答案和课程证据正确；
2. 不把“正确答案先写”当作默认写作习惯；
3. 根据当前 production 中相同 choice count 的位置计数安排正确选项；
4. 不通过重命名 choice ID 改变显示位置；
5. 独立课程审核后、production promotion 前重新运行位置审计；
6. acceptance table 同时锁定 stable ID 和 reviewed display order。

## Multiple-choice guidance

多选题不套用单选题的 A/B/C/D 单点均衡规则，因为它有多个正确项，且部分题目可能
需要保留教学上的逻辑顺序。但仍应：

- 避免所有正确项连续集中在最前部；
- 避免所有错误项统一堆在末尾；
- 在不破坏阅读顺序时穿插合理干扰项；
- 确保显示顺序不会暗示正确集合；
- 继续用稳定 choice-ID 集合进行 exact-match scoring。

## Testing requirements

Production promotion 和发布前测试必须验证：

- expected choice ID 存在且 choice IDs 唯一；
- loader 重复加载得到相同显示顺序；
- acceptance table 锁定 reviewed display order 和 expected stable ID；
- 四选一位置计数满足全位置覆盖和最大/最小差不超过 1；
- 第一位置集中度不超过均衡上界；
- known-correct、known-wrong、malformed 和 evidence pipeline 语义不因重排改变；
- Streamlit 显示静态新顺序，但提交、history 和 reveal 仍使用 stable choice ID；
- rerun 不改变顺序，点击第一个错误选项不会被误判为正确。
