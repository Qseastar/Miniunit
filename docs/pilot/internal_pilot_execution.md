# P4b/P4d 六人组内内测执行流程

本执行包只用于 Search Algorithms 黄金范式的离线、下载式内测。Pilot mode 默认关闭，负责人应在 WSL/Ubuntu 的仓库根目录运行：

```bash
PYTHONPATH=src python tools/pilot_preflight.py --strict --host 127.0.0.1 --db-path /tmp/introai-pilot.sqlite3
scripts/run_internal_pilot.sh --host 127.0.0.1 --port 8503 --db-path /tmp/introai-pilot.sqlite3
```

负责人需要把 `INTROAI_PILOT_ACCESS_CODE` 通过独立私密渠道发送给受邀测试者。默认 loopback 启动且未配置访问码时，预检会给出“仅本机负责人模式”的 WARN；若绑定局域网或代理地址（例如 `0.0.0.0`），必须配置有效访问码，否则 `--strict` 会失败。访问码不会写入 URL、SQLite、反馈文件或日志。完整边界见 [controlled_access.md](controlled_access.md)。

预检不发起网络请求，也不创建正式学习证据。`--strict` 在关键检查出现 FAIL 时返回非零；WARN 只提示可控降级（例如未配置 API key 或本地 PDF 不在当前环境），不会伪装成 PASS。端口被占用时由负责人决定，不自动结束未知进程。

六名测试者都完成 P4a 的六项核心任务，再分别关注 role_a–role_f 的重点方向。角色只用于分工；应用生成的 `G-XXXXXX` 是匿名反馈文件编号，二者不能互相替代。

## 启动和收集

启动后在“内测任务与反馈”页完成任务、填写反馈并下载 JSON。把下载文件放入 `pilot_feedback_inbox/`，再运行：

```bash
PYTHONPATH=src python tools/summarize_pilot_feedback.py \
  pilot_feedback_inbox --output-dir pilot_feedback_summary
```

反馈不自动上传、不写入 learner SQLite，不收集姓名、UUID、IP、浏览器指纹、题目、回答、课件正文或 prompt。

## 退出码

- `0`：没有 FAIL；WARN 可能仍需负责人确认。
- `1`：`--strict` 检测到一个或多个 FAIL，应停止启动。
- `2`：命令参数或输入文件无效。

预检状态的 check ID 是稳定接口；会议记录应保留状态和复现步骤，而不是复制敏感日志。

P4d.1 远程内测由负责人优先使用 `scripts/remote_pilot_ctl.sh start|status|url|logs|restart|stop|doctor` 管理；不要手工查 PID 或按端口杀进程。操作指南见 [remote_pilot_operator_guide.md](remote_pilot_operator_guide.md)。

## P4d 异地临时交付

异地六人内测仍复用同一套任务、角色、下载式反馈和 SQLite learner profile。负责人已自行准备 `cloudflared` 时，可改用：

```bash
scripts/run_remote_pilot.sh --port 8504 \
  --db-path ~/introai_pilot_artifacts/p4d/introai-pilot.sqlite3
```

远程启动会强制有效访问码，并继续将 Streamlit 绑定在 `127.0.0.1`；Quick Tunnel URL 仅从当前终端复制。URL 与访问码必须分开发送，内测结束后按 `Ctrl+C` 关闭。详见 [remote_pilot_delivery.md](remote_pilot_delivery.md)。
