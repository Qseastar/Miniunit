# 离线反馈汇总

## 命令

```bash
PYTHONPATH=src python tools/summarize_pilot_feedback.py feedback_downloads --output-dir pilot_summary
```

输入目录和输出目录必须不同。工具不访问网络、不读取环境变量、不写入应用 SQLite，也不改变任何 learner state。

## 输出

- `pilot_feedback_summary.json`：可机器读取的汇总；
- `pilot_feedback_ratings.csv`：八项量表的样本数、均值、中位数、范围和分布；
- `pilot_feedback_summary.md`：便于人工查看的完成率、评分与开放反馈。

## 重复与非法文件

文件必须符合反馈 schema。非法 JSON、字段缺失、未知任务 ID、非法评分或额外敏感字段都会记录为拒绝文件，不参与统计。非 JSON 文件会被忽略。除 `generated_at_utc` 外内容相同的 JSON 视为重复；按文件名字典序保留第一个，其他文件在汇总中标记为重复。

汇总只计算内测体验信号，不自动推断课程掌握度，不自动修改模板、评分、推荐或学习记录。
