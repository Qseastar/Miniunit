#!/usr/bin/env bash
# Start the six-person internal pilot only after the offline preflight passes.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

host="127.0.0.1"
port="8503"
db_path=""
headless=0
usage() {
  printf '%s\n' '用法：scripts/run_internal_pilot.sh [--host HOST] [--port PORT] [--db-path PATH] [--headless]' >&2
}
while (($#)); do
  case "$1" in
    --host)
      (($# >= 2)) || { usage; exit 2; }
      host="$2"
      shift 2
      ;;
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
    --headless)
      headless=1
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

# Read only simple KEY=value assignments from .env. Do not source it: a
# project .env is configuration, not executable shell code, and values are
# never echoed by this script.
load_dotenv() {
  local dotenv="$root/.env" line key value
  [[ -f "$dotenv" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"
    # A controller may have injected a one-run access code after an
    # interactive prompt.  Keep that value in preference to an absent or
    # stale dotenv entry; never write either value back to disk.
    if [[ "$key" == "INTROAI_PILOT_ACCESS_CODE" && -v INTROAI_PILOT_ACCESS_CODE ]]; then
      continue
    fi
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < "$dotenv"
}
load_dotenv
export INTROAI_PILOT_MODE=1
export INTROAI_PILOT_HOST="$host"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
if [[ -n "$db_path" ]]; then
  export INTROAI_STATE_DB="$db_path"
fi

preflight_args=(--strict --host "$host" --port "$port")
if [[ -n "$db_path" ]]; then
  preflight_args+=(--db-path "$db_path")
fi
printf '%s\n' '正在执行离线内测预检（不会调用网络或 API）……'
python tools/pilot_preflight.py "${preflight_args[@]}"
printf 'Pilot mode 已启用。Bind host: %s\nLocal URL: http://localhost:%s\n' "$host" "$port"
if [[ "$host" != "127.0.0.1" && "$host" != "localhost" && "$host" != "::1" ]]; then
  printf '%s\n' '警告：局域网/代理访问只适合短期负责人托管；不要把裸端口长期暴露在公共互联网。' >&2
fi
streamlit_args=(python -m streamlit run app.py --server.address "$host" --server.port "$port" --server.fileWatcherType none)
if ((headless)); then
  streamlit_args+=(--server.headless true)
fi
exec "${streamlit_args[@]}"
