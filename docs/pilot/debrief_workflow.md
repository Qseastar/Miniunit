# 内测反馈离线汇总与复盘

1. 负责人确认收件箱只包含测试者主动下载的 JSON。
2. 运行现有 `tools/summarize_pilot_feedback.py`，输出目录必须与收件箱不同。
3. 检查 JSON、CSV、Markdown 中的有效样本数、拒绝文件、重复文件、任务完成率、量表均值/分布和开放反馈。
4. 将可复现问题抄入问题分级表，不将自由文本发送给 LLM。
5. 会议前完成 P0/P1 决策；P2 按频率和影响排期；P3 进入 backlog。

内测反馈与 learner state 分离。反馈汇总不产生 mastery、recommendation 或正式 evidence。
