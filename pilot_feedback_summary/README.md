# Pilot Feedback Summary

本目录用于保存 IntroAI Tutor 内测反馈的本地离线汇总结果。

运行命令：

    PYTHONPATH=src python tools/summarize_pilot_feedback.py pilot_feedback_inbox --output-dir pilot_feedback_summary

将生成：

- pilot_feedback_summary.json
- pilot_feedback_ratings.csv
- pilot_feedback_summary.md

实际反馈汇总文件属于本地产物，不应提交至 Git。仓库仅追踪本说明文件。
