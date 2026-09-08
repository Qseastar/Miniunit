# Learner-state persistence

v1 现已使用本地 SQLite 与 URL 中的匿名 UUID 恢复 learner state。刷新、同一 URL 的新连接和 Streamlit 服务重启后，会恢复 mastery、已跟踪知识点与最小 reviewed-verification 审计记录；不会恢复未完成诊断或其他 UI 瞬态状态。

默认数据库为 `~/.introai_tutor/learner_state.sqlite3`，可通过 `INTROAI_STATE_DB` 覆盖。清空学习记录只清空当前 UUID 的本地档案；创建新档案不会删除旧档案。

仍未支持账号、云端备份、多设备同步、浏览器 cookie 身份、跨设备隐私边界或历史问题/回答保存。数据库不可用时，应用会降级为当前 session 内状态并显示提示。
