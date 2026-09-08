# Search Algorithms Verification Benchmark 规划

## 当前资产与边界

`tests/template_acceptance_cases.py` 是 production template 的 contract table：它验证
correct、wrong、malformed、source 和 display order。`benchmark_case_ids` 目前是追踪
标签，不是独立运行的 verification benchmark。41-case formative benchmark 继续服务于
开放式形成性判题，不能与 mastery-verification accuracy 混合统计。

## 未来独立 benchmark 的最小 schema

每个案例应关联一个 reviewed template，并包含：

- `template_id`、`case_id`、`review_status=human_verified`；
- category：positive、wrong/misconception、malformed、assisted、reveal、evidence、
  source_traceability、intent、selector 或 ui_smoke；
- JSON-safe submitted answer；
- expected score/passed 或 expected exception；
- expected assistance provenance；
- expected summary/evidence eligibility；
- expected primary concept observation，必要时 expected no-observation reason；
- source reference 与 UI display contract。

## 执行原则

1. 复用唯一的 production loader、scorer registry、`VerificationDiagnosticService`、
   `DiagnosticStateIntegrationService` 和 selector。
2. 不创建第二套 loader、平行 evidence pipeline 或独立 mastery 公式。
3. 按 template、concept、question type 输出 exact-match 指标；malformed 与 reveal 不应
   被计为普通错误答案。
4. 统计时明确区分题目 correctness、evidence safety、selector safety 与 UI rendering。
5. 全部离线；任何 live LLM 或开放式 formative 指标单独报告。

## 最小覆盖矩阵

| Category | 目的 | 必须验证 |
| --- | --- | --- |
| positive | 正确答案可得 evidence | score=1、primary concept observation |
| wrong | 错误不获通过 | score=0、reviewed hint，只有明确规则才记 misconception |
| malformed | fail closed | 无 attempt、无 summary |
| assisted | hint 后可推进但不冒充独立 signal | provenance 与 selected signal |
| reveal | 查看答案不产生正 evidence | no observation / all revealed |
| evidence | completed 才调用 integration 一次 | evidence gate、mastery trace |
| source | 课件来源可解析 | chunk/file/current physical pages |
| intent/selector | 只选 reviewed primary-topic template | unknown/unsupported 安全 unavailable |
| UI smoke | 显示 text、提交 ID、rerun 稳定 | choice order 与 answer ID 分离 |

当前不实现 benchmark runner：在没有负责人批准的完整 21-template bank 前，扩建另一套
运行入口会产生平行架构风险。现有 acceptance suite 是正确的单一执行基础。
