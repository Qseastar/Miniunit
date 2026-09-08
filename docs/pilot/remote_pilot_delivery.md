# P4d 六人异地内测远程交付

P4d 只用于负责人在短时间内托管六人组内测试，不是公开部署、账号系统或长期服务。远程入口由负责人本机的临时进程提供；关闭终端或按 `Ctrl+C` 后入口即失效。

## 调用链与边界

```text
测试者浏览器
  → cloudflared Quick Tunnel 的临时 HTTPS URL
  → cloudflared
  → http://127.0.0.1:8504
  → Streamlit / P4c 访问码页
  → learner profile 初始化
  → QA、审核诊断、知识图谱、下载式反馈
```

Streamlit 始终只绑定 `127.0.0.1`，不直接开放 `0.0.0.0` 或防火墙端口。临时 HTTPS 流量只能经过 Quick Tunnel。即使后端是 loopback，远程模式仍强制要求有效的 `INTROAI_PILOT_ACCESS_CODE`：该访问码是共享的短期 bearer secret，不是身份认证或账号系统。

## 启动前准备

P4d.1 推荐负责人日常只使用 [remote_pilot_operator_guide.md](remote_pilot_operator_guide.md) 中的 `scripts/remote_pilot_ctl.sh`。它负责受管 supervisor 的启动、状态、URL、日志、重启和停止，并验证 PID 身份；本页保留底层 launcher 的边界和兼容说明。

1. 由负责人自行安装 `cloudflared`，并确认 `command -v cloudflared` 能找到一个可执行普通文件。脚本不会下载、安装或配置它。
2. 在安全环境或项目 `.env` 的简单键值配置中提供访问码；不要把访问码写进 URL、命令行参数、截图或反馈文件。
3. 在仓库根目录直接运行控制器：

```bash
scripts/remote_pilot_ctl.sh doctor
scripts/remote_pilot_ctl.sh start
```

控制器会自动在远程预检和受管 supervisor 中启用 Pilot mode；不要求负责人手工设置 `INTROAI_PILOT_MODE=1`，也不会污染普通应用模式。它是唯一 readiness 与生命周期所有者；受管 launcher 仅负责创建自己拥有的子进程并在收到结束信号时清理它们。控制器会先运行严格、离线的预检，再以 headless 模式启动本地 Streamlit，检查不经过环境代理的 loopback health endpoint，最后由 supervisor 运行：

```text
cloudflared tunnel --url http://127.0.0.1:8504 --no-autoupdate
```

启动成功后使用 `scripts/remote_pilot_ctl.sh url` 复制临时 HTTPS URL。URL 会变化且不写入 Git、SQLite、learner state、反馈 JSON 或 Session Pack。`doctor` 不创建目录、不启动子进程或隧道。控制器把本地 health（默认 45 秒）和本轮 URL 获取（默认 120 秒）分开：本地应用已健康而 URL 稍慢时会保留受管实例并进入 `STARTING`，不会为了 URL 延迟关闭本地服务；稍后执行 `status`、`url` 或 `url --wait 120` 即可。

```bash
scripts/remote_pilot_ctl.sh status
scripts/remote_pilot_ctl.sh logs
```

默认 SQLite 位于 `~/introai_pilot_artifacts/p4d/introai-pilot.sqlite3`，运行日志位于 `~/introai_pilot_artifacts/p4d/runtime/streamlit.log`。两者都在仓库外；运行目录以 owner-only 权限创建。

## 六人测试流程

1. 从生成的 Session Pack 分配 `role_a`–`role_f`；每位测试者完成全部六项核心任务，并重点检查自己的角色。
2. 通过不同私密渠道发送 HTTPS URL 与访问码。不要转发 URL、访问码或个人 learner URL，也不要多人共用浏览器 session。
3. 测试者输入访问码后，浏览器会创建自己的 learner profile。相同 SQLite 中的 profile、template exposure 与 evidence event 按 learner UUID 隔离。
4. 测试者完成后下载匿名 feedback JSON，并通过约定渠道回传。反馈不会自动上传，也不应包含姓名、学号、API Key、完整问题或完整回答。
5. 负责人将下载文件放入本地收件箱并运行离线汇总：

```bash
PYTHONPATH=src python tools/summarize_pilot_feedback.py \
  pilot_feedback_inbox --output-dir pilot_feedback_summary
```

同一 reviewed template 的重复完成仍是 practice-only，不会重复形成独立 mastery evidence。

## 停止与人工验收

控制器启动完成后不要求负责人保持启动终端占用。需要查看生命周期时运行 `logs --follow`；停止时使用 `remote_pilot_ctl.sh stop`，它只终止当前经过身份验证的 supervisor 及其子进程，不会按端口或进程名清理其他服务。底层 launcher 的 `Ctrl+C` 兼容行为仍只处理自己创建的 cloudflared 和 Streamlit 子进程。

建议负责人用手机移动网络完成一次验收：

1. 使用错误访问码，确认只显示通用失败提示且不初始化 learner profile。
2. 使用正确访问码，确认 QA、知识图谱、审核诊断与反馈下载正常。
3. 用另一设备或无痕窗口确认 profile 隔离；两人分别完成诊断，状态不串档。
4. 重启 Streamlit 后，用原 learner URL 确认本机 SQLite 持久化；重启远程脚本后确认 Quick Tunnel URL 可能变化、旧 URL 失效。
5. 按 `Ctrl+C`，确认隧道和本轮 Streamlit 均退出，并检查 Git 未追踪 URL、日志、SQLite 或反馈 JSON。

## 故障排查与限制

- **找不到 cloudflared**：脚本会 fail closed，且不会启动 Streamlit 或隧道。由负责人完成安装后再试。
- **预检提示访问码无效**：只通过环境变量重新配置合法访问码；不要把它放到 URL 或 argv。
- **端口被占用**：预检失败。不要自动结束未知进程；改用负责人确认的空闲端口。
- **本地健康检查失败**：启动器会停止本轮子进程；查看仓库外 runtime log 的通用运行信息。
- **模型服务故障**：自由问答可能降级或不可用；本地 reviewed diagnostics、知识图谱和下载式反馈仍不依赖远程模型。
- **短暂断开**：测试者先等待后刷新；不承诺自动重连。

Quick Tunnel 的 HTTPS 由隧道提供商终止；应用本身不管理 TLS、正式账号、细粒度授权、长期 URL、云同步、高可用或生产级运维。负责人电脑、网络和终端必须持续运行。内测结束后关闭隧道，并轮换或删除旧访问码。
