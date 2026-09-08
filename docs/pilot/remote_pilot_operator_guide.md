# P4d.1 远程内测操作指南

远程六人内测日常只需要使用一个入口：

```bash
scripts/remote_pilot_ctl.sh <command>
```

控制器管理本仓库启动的 supervisor、Streamlit 和 Cloudflare Quick Tunnel。默认配置与 P4d 一致：本地只绑定 `127.0.0.1:8504`，SQLite 位于
`~/introai_pilot_artifacts/p4d/introai-pilot.sqlite3`，运行元数据和日志位于
`~/introai_pilot_artifacts/p4d/runtime`。数据库和运行目录都在仓库外。

远程控制器会在自己的严格预检和受管子进程环境中自动设置 `INTROAI_PILOT_MODE=1`；负责人无需手工 `export` 或给命令添加环境变量前缀。它不会修改当前父 shell、`.env` 或普通 `streamlit run app.py` 的模式。控制器是唯一的 readiness 与生命周期所有者；受管 `run_remote_pilot.sh` 只创建并监督自己启动的 Streamlit、cloudflared 子进程，收到 TERM/INT 时负责清理它们，不再另行执行短时 health/URL timeout。

## 每日命令

```bash
scripts/remote_pilot_ctl.sh doctor
scripts/remote_pilot_ctl.sh start
scripts/remote_pilot_ctl.sh status
scripts/remote_pilot_ctl.sh url
scripts/remote_pilot_ctl.sh logs
scripts/remote_pilot_ctl.sh restart
scripts/remote_pilot_ctl.sh stop
```

`logs --lines 200` 可查看更多 supervisor 与 cloudflared 日志，`logs --follow` 可持续查看。`url` 在实例健康且隧道仍由当前 supervisor 管理时只输出 HTTPS URL，便于复制；它不会输出访问码。若本地应用已健康但 Quick Tunnel URL 仍在生成，`url` 会明确提示等待中；需要等待时可使用 `url --wait 120`。

`status` 显示 `STOPPED` 是正常状态，退出码为 `0`，且不会启动服务，也不会改写 URL 或日志。`doctor` 只在真正的预检 FAIL 时返回非零；`start` 在预检 FAIL 时不会启动 Streamlit 或 cloudflared。

`start` 分别等待本地 Streamlit（默认 45 秒）和本轮 Quick Tunnel URL（默认 120 秒）：

```bash
scripts/remote_pilot_ctl.sh start --app-timeout 45 --tunnel-timeout 120
```

本地应用在第一个期限内未健康时，控制器会安全清理本轮受管 supervisor。反之，若本地应用与 cloudflared 均存活、但 URL 仍未出现，控制器保留受管实例，显示“仍在等待 Quick Tunnel URL”，并以退出码 `3` 区分这种可继续观察的状态；随后使用 `status` 或 `url --wait 120`。这不是需要手工查 PID 或 kill 的错误。远程受管启动会显式采用 headless 模式，不会自动打开本机浏览器。

## 访问码和 URL

访问码来源仍是 `INTROAI_PILOT_ACCESS_CODE`，由负责人在安全环境或项目 `.env` 的简单 `KEY=value` 配置中提供。控制器不会执行 `.env`，不会改写它，也不会自动生成或轮换访问码。六人同一轮内测使用同一个访问码；只有负责人主动更换配置或访问码泄漏、需要切换测试批次时才轮换。

若 `doctor`、`start` 或 `restart` 发现访问码缺失且当前终端是交互式 TTY，会以不回显的方式提示输入，仅放入本轮 controller/受管子进程环境；不会写回 `.env`、shell history、URL、metadata、SQLite 或日志。非交互命令缺少访问码会 fail closed。`status`、`url`、`logs`、`stop` 不会再次要求输入访问码。

URL 和访问码必须通过不同的私密渠道发送，不要放在同一个公开群聊、截图或 URL 查询参数中。Quick Tunnel 重启后 URL 通常会变化，访问码保持不变；因此重启后通常只需重新发送新 URL。

访问码不会进入命令行参数、PID 元数据、SQLite、反馈文件、日志或 Git。控制器状态和诊断只显示“已配置/未配置”或布尔状态。

## 已经运行、端口冲突和旧版进程

如果当前实例已经健康运行，再次执行 `start` 会复用它，不会重复启动，也不会把端口误报成冲突。若运行元数据指向已退出的 supervisor，控制器只清理失效元数据，不会杀死未知进程。

若端口由未知程序占用，`start` 会 fail closed，显示安全裁剪后的占用摘要，不会自动 kill。不要手工查 PID 或输入 `kill <PID>`；其中尖括号只是说明文字，直接输入会被 Bash 解释为重定向语法并产生错误。

处理旧版 P4d launcher 时先 dry-run：

```bash
scripts/remote_pilot_ctl.sh cleanup-legacy --port 8504
scripts/remote_pilot_ctl.sh cleanup-legacy --port 8504 --confirm
```

只有当前用户、当前仓库 `app.py`、精确 loopback host/port 和精确 cloudflared URL 命令全部匹配时，`--confirm` 才会按 cloudflared 再 Streamlit 的顺序处理。其他仓库、端口或用户的进程不会处理。

## 生命周期和故障处理

`restart` 只停止当前受管 supervisor，再启动新的一轮；SQLite 学习记录保留，访问码不变，Quick Tunnel URL 重新获取。重复执行 `stop` 是幂等的。控制器不会使用 `pkill`、`killall`、`fuser -k` 或宽泛正则杀进程。`stop` 同样可安全处理 URL 尚未生成的 `STARTING` 实例。

退出码：`0` 表示成功或正常的 `STOPPED`；`1` 表示预检、受管进程或安全状态失败；`2` 表示参数/配置格式错误；`3` 表示本地应用仍健康、仅等待 Quick Tunnel URL，可继续用 `status` 或 `url --wait`。

按 `Ctrl+C`、关闭负责人的终端或停止 supervisor 会关闭本轮远程入口；不会删除 SQLite。电脑休眠、断网或 cloudflared 退出可能使 URL 暂时不可用，恢复网络后先运行 `status`，必要时执行 `restart`。Quick Tunnel 是临时短期内测通道，不保证长期稳定、固定 URL、高可用、账号体系或细粒度授权。

负责人电脑和网络必须在内测期间保持在线。内测结束后执行 `stop`，并按需要轮换访问码。
