# P3e：外部模型故障降级与审核诊断本地快速通道

## 问题背景

课程自由问答依赖外部模型完成问题理解和课程证据约束回答。模型短暂超时、限流、连接失败或返回无法安全解析的内容时，普通问答必须清楚说明服务状态；同时，学生已经明确提出的审核诊断请求不应因为这一步外部依赖而失去既有的本地 reviewed-template 路径。

## 调用链与本地快速通道

普通路径为：

`app.py → TutorService.ask() → QuestionUnderstandingService → DeepSeekAdapter → retrieval → GroundedAnswerService → DiagnosticHandoffService`

在 `TutorService.ask()` 内，问题校验后、`QuestionUnderstandingService` 调用前，新增受控本地检查：

`DeterministicDiagnosticRequestParser → DiagnosticHandoffService → reviewed production selector`

仅当解析器同时确认强明确的审核诊断意图和课程 registry 内的直接名称/受控缩写，且既有 handoff 找到 human-verified production template 时，才返回 `diagnostic_available`。该路径不调用 adapter、不生成课程答案、不创建 verification session，也不创建 exposure 或 learner-state evidence。

这不是通用中文理解器。普通提问、模糊请求、未知概念、候选题、blocked slot，以及没有 reviewed production template 的概念都会 fail closed，回到原有自由问答路径。

## 故障分类与学生提示

`TutorServiceError` 保留 correlation ID、failure stage 与受控 failure kind：

- `upstream_timeout`
- `upstream_connection`
- `upstream_rate_limited`
- `upstream_server_error`
- `model_configuration`
- `invalid_model_response`
- `internal_application_error`

对 timeout、connection、429 和 5xx，学生看到：

> 模型服务暂时不可用。你的问题已保留，学习记录未受影响。

模型配置错误与模型返回格式异常使用独立、非技术化文案；本地应用错误显示短 correlation ID，且不会伪装为 provider 宕机。日志仅记录错误类别、阶段、correlation ID、异常类和脱敏短消息；不会记录 API Key、Authorization、完整 prompt、完整课程材料、完整学生问题、learner UUID 或数据库内容。

## 手动重试状态

暂时性 provider 故障和安全解析失败会在 session 内保存原始已提交问题及故障类别。页面提供“重新尝试本次问题”按钮；只有明确点击才会重新调用服务。普通 rerun、切换页面、滚动和展开详情都不会自动重试。成功后旧错误和 retry state 会一起清除。该 transient state 不写 SQLite、不写 learner profile，且不会跨新 profile 或服务重启恢复。

## Exposure、mastery 与持久化边界

快速通道只创建计划。实际点击“开始审核诊断”后，才进入既有 P3d exposure policy：未 exposure 的模板可作为 formal 测量，已 exposure 的模板保持 practice-only。自由问答故障、手动 retry 和 handoff 展示都不会创建 observation、formal evidence、recommendation 或 exposure。SQLite schema 保持 version 3，不新增表或 migration。

## 离线测试与人工验收

所有自动化测试均使用 fake adapter 或注入的 sender，不读取 `.env` 且不访问网络。可用本地不可达端口进行人工故障演练（无需修改 `.env`）：

```bash
cd ~/projects/introai-tutor
DEEPSEEK_BASE_URL=http://127.0.0.1:9 \
INTROAI_STATE_DB=/tmp/introai_p3e_manual.sqlite3 \
PYTHONPATH="$PWD/src" \
python -m streamlit run "$PWD/app.py" --server.port 8503 --server.fileWatcherType none
```

1. 提交“请用审核诊断题测试我对一致代价搜索如何选择下一个节点的理解。”：应立即显示 UCS 的 reviewed handoff，不显示模型故障或答案。
2. 提交“为什么一致代价搜索选择累计路径代价最小的节点？”：应显示模型暂时不可用、保留问题和手动重试按钮。
3. 确认知识掌握图谱、已持久化学习记录和已开始的 reviewed diagnostics 仍可使用。

## 剩余限制

普通自由问答仍依赖外部模型；本轮不实现多 provider、用户自填 API、自动网络健康检查、后台任务、自动无限重试或 circuit breaker。长时间 provider 故障期间，只有满足本地快速通道条件的 reviewed diagnostic handoff 可以绕开模型。
