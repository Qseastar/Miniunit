# P4c/P4d 受控内测访问边界

P4c 的访问码是负责人托管的短期内测门槛，不是账号系统、身份认证或多租户权限系统。它只保护当前 Pilot 进程，不改变 learner UUID、SQLite schema 或学习记录语义。

## 三种启动模式

| 模式 | 绑定地址 | 访问行为 |
| --- | --- | --- |
| 普通开发 | `127.0.0.1`（默认） | 不显示访问码页面；只适合本机开发。 |
| 负责人本机 Pilot | `127.0.0.1`/`localhost`，`INTROAI_PILOT_MODE=1` | 若未配置访问码，允许负责人本机无码使用，并明确显示仅本机警告；若配置访问码则要求输入。 |
| 受控局域网/代理 | 非 loopback 地址，`INTROAI_PILOT_MODE=1` | 必须配置有效 `INTROAI_PILOT_ACCESS_CODE`；缺失或格式错误时预检失败，应用不会初始化学习档案。 |
| P4d Quick Tunnel | Streamlit 固定 `127.0.0.1`，`INTROAI_PILOT_MODE=1` | 即使后端为 loopback，也必须配置有效访问码；临时 HTTPS URL 与访问码分开发送。 |

启动脚本通过 `--host` 传递绑定地址，并把访问码只留在进程环境和一次性内存比较中：

```bash
INTROAI_PILOT_MODE=1 \
INTROAI_PILOT_ACCESS_CODE='由负责人单独发送的访问码' \
scripts/run_internal_pilot.sh --host 0.0.0.0 --port 8503 --db-path /tmp/introai-pilot.sqlite3
```

不要把访问码放入 URL、反馈 JSON、SQLite、截图、终端输出或聊天记录。负责人应通过与 URL 分开的私密渠道发送访问码；测试者只接收基础 URL 和访问码，不共享个人 learner URL。应用日志和错误页面只显示通用失败提示，不显示访问码、请求头、API Key 或完整 prompt。

该应用不自行提供公网防护、TLS 终止、账号注销、速率限制或云端身份管理。不要把裸 Streamlit 端口长期暴露到公共互联网；结束内测时在启动终端按 `Ctrl+C` 停止进程。访问通过只在当前浏览器 session 生效，退出访问会清理内存中的应用快照但保留本地 learner profile，便于负责人随后重新登录恢复同一档案。

P4d 的 `cloudflared` Quick Tunnel 只转发到本机 loopback；它不是正式公网部署或账号系统。临时 URL、访问码、日志、SQLite 和反馈都不得提交 Git。远程交付的完整流程见 [remote_pilot_delivery.md](remote_pilot_delivery.md)，日常控制命令见 [remote_pilot_operator_guide.md](remote_pilot_operator_guide.md)。
