#!/usr/bin/env bash
# Start a short, owner-supervised remote Pilot through a Cloudflare Quick Tunnel.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

artifacts_root="${HOME}/introai_pilot_artifacts/p4d"
port="8504"
db_path="${artifacts_root}/introai-pilot.sqlite3"
runtime_dir="${artifacts_root}/runtime"
dry_run=0
managed_by_controller=0
app_pid=""
tunnel_pid=""
cleanup_done=0

usage() {
  printf '%s\n' '用法：scripts/run_remote_pilot.sh [--port PORT] [--db-path PATH] [--runtime-dir PATH] [--managed-by-controller] [--dry-run]' >&2
}

cleanup() {
  if ((cleanup_done)); then
    return
  fi
cleanup_done=1
  if [[ -n "$tunnel_pid" ]] && kill -0 "$tunnel_pid" 2>/dev/null; then
    printf '%s\n' '正在停止本轮启动的 cloudflared 子进程……' >&2
    kill "$tunnel_pid" 2>/dev/null || true
    wait "$tunnel_pid" 2>/dev/null || true
  fi
  if [[ -n "$app_pid" ]] && kill -0 "$app_pid" 2>/dev/null; then
    printf '%s\n' '正在停止本轮启动的本地 Streamlit 子进程……' >&2
    kill "$app_pid" 2>/dev/null || true
    wait "$app_pid" 2>/dev/null || true
  fi
}

on_signal() {
  cleanup
  exit 130
}

while (($#)); do
  case "$1" in
    --port)
      (($# >= 2)) || { usage; exit 2; }
      port="$2"
      shift 2
      ;;
    --db-path)
      (($# >= 2)) || { usage; exit 2; }
      db_path="$2"
      shift 2
      ;;
    --runtime-dir)
      (($# >= 2)) || { usage; exit 2; }
      runtime_dir="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --managed-by-controller)
      managed_by_controller=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65535)); then
  printf '%s\n' '端口必须是 1–65535 的整数。' >&2
  exit 2
fi
if [[ -z "$db_path" || -z "$runtime_dir" ]]; then
  printf '%s\n' '数据库路径和运行目录不能为空。' >&2
  exit 2
fi

export INTROAI_PILOT_MODE=1
export INTROAI_PILOT_HOST=127.0.0.1
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
export INTROAI_STATE_DB="$db_path"

if ! command -v cloudflared >/dev/null 2>&1; then
  printf '%s\n' '未找到 cloudflared；请由负责人自行安装后重新运行。未启动 Streamlit 或隧道。' >&2
  exit 1
fi

preflight_args=(--strict --remote --tunnel-provider cloudflared --host 127.0.0.1 --port "$port" --db-path "$db_path")
printf '%s\n' '正在执行远程 Pilot 离线预检（不会访问 Cloudflare、DeepSeek 或其他网络）……'
python tools/pilot_preflight.py "${preflight_args[@]}"

printf 'Pilot release: p4d\nLocal Streamlit: http://127.0.0.1:%s\nSQLite: %s\nRuntime directory: %s\n' "$port" "$db_path" "$runtime_dir"
printf '%s\n' '访问码已配置（值隐藏）。cloudflared 启动后，请从其终端输出复制 HTTPS URL。'
printf '%s\n' '请通过不同的私密渠道分别发送 URL 与访问码；终端保持运行，Ctrl+C 会关闭本轮远程入口。'

if ((dry_run)); then
  printf '%s\n' 'Dry run：未创建运行目录、未启动 Streamlit、未启动 cloudflared，也未创建 learner profile。'
  printf 'Plan: scripts/run_internal_pilot.sh --host 127.0.0.1 --port %s --db-path <configured>\n' "$port"
  printf 'Plan: cloudflared tunnel --url http://127.0.0.1:%s --no-autoupdate\n' "$port"
  exit 0
fi

umask 077
mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"

trap cleanup EXIT
trap on_signal INT TERM

streamlit_log="$runtime_dir/streamlit.log"
tunnel_log="$runtime_dir/cloudflared.log"
scripts/run_internal_pilot.sh --host 127.0.0.1 --port "$port" --db-path "$db_path" --headless >"$streamlit_log" 2>&1 &
app_pid="$!"

wait_for_local_ready() {
  local attempt
  for attempt in $(seq 1 20); do
    if python - "$port" <<'PY'
import sys
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

port = int(sys.argv[1])
try:
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/_stcore/health", timeout=1.0) as response:
        raise SystemExit(0 if 200 <= response.status < 300 else 1)
except (URLError, OSError, TimeoutError):
    raise SystemExit(1)
PY
    then
      return 0
    fi
    if ! kill -0 "$app_pid" 2>/dev/null; then
      return 1
    fi
    sleep 1
  done
  return 1
}

if ((managed_by_controller)); then
  printf '%s\n' '受管模式：controller 负责本地 health 与 Quick Tunnel URL readiness；launcher 仅监督其创建的子进程。'
else
  if ! wait_for_local_ready; then
    printf '本地 Streamlit 未在限定时间内就绪；已停止本轮子进程。运行日志位于：%s\n' "$streamlit_log" >&2
    exit 1
  fi
fi

printf '%s\n' '正在启动 cloudflared Quick Tunnel；控制器会从本轮 tunnel 日志确认 HTTPS URL。'
printf '%s\n' "cloudflared 日志：$tunnel_log"
cloudflared tunnel --url "http://127.0.0.1:${port}" --no-autoupdate >>"$tunnel_log" 2>&1 &
tunnel_pid="$!"
wait "$tunnel_pid"
