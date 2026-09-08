# P2g coverage execution counts

来源为 `tools/p2g_execution_counts.py` 的真实 scorer 枚举与 production
session 状态探索；完整机器可读数据见
`reports/p2g_coverage_execution_counts.json`。

- Single choice：17 个 production、0 个 candidate；实际执行 66 次合法 choice 评分。
- Multiple choice：3 个 production、0 个 candidate；实际执行 173 个非空子集和 124 次 expected-set permutation 检查。
- Synthetic contract：numeric 14 例、ordering 14 例。
- Mutation：定义 45 项，当前实际执行 42 项；未直接执行的项仍在隔离/边界测试中，不能声称完整矩阵。
- Selector：67 个 positive intent、20 个 negative intent、20 个 unknown concept。
- State explorer：9 类动作、最大深度 4、105 条路径、105 个签名状态、30 个拒绝转换。
- Service replay：20 个模板各覆盖 correct/wrong/malformed/hint/reveal；5 个 serialization replay。
- AppTest：20 个 production、0 个 candidate；17 单选、3 多选、4 个 A/B/C/D 位置路径、2 个 rerun。
- Tamper：17 个代表字段变异；12 个经真实 restore/revalidation 拒绝，5 个经 state integration 在 learner state 写入前拒绝。它仍不是原始提示列出的全部字段矩阵。
