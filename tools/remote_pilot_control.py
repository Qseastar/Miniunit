#!/usr/bin/env python3
"""Safe, offline-aware operator control for the remote Pilot supervisor.

The command-line wrapper is intentionally small; process identity, metadata,
and legacy matching live here so they can be tested without a real tunnel.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from typing import Any, Callable, Iterable, Mapping
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8504  # P4d's existing launcher/documentation default.
DEFAULT_ARTIFACTS = Path.home() / "introai_pilot_artifacts" / "p4d"
DEFAULT_RUNTIME = DEFAULT_ARTIFACTS / "runtime"
DEFAULT_DB = DEFAULT_ARTIFACTS / "introai-pilot.sqlite3"
METADATA_SCHEMA_VERSION = 1
URL_PATTERN = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?")
PID_PATTERN = re.compile(r"^[1-9][0-9]*$")
DEFAULT_APP_TIMEOUT = 45.0
DEFAULT_TUNNEL_TIMEOUT = 120.0
PENDING_TUNNEL_EXIT_CODE = 3
TUNNEL_START_GRACE_SECONDS = 5.0


class RemotePilotControlError(ValueError):
    """Raised for invalid operator input or an unsafe process transition."""


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    uid: int
    argv: tuple[str, ...]
    cwd: Path | None

    @property
    def command(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class OperatorConfig:
    root: Path = ROOT
    runtime_dir: Path = DEFAULT_RUNTIME
    db_path: Path = DEFAULT_DB
    port: int = DEFAULT_PORT
    host: str = "127.0.0.1"
    runner_path: Path = ROOT / "scripts" / "run_remote_pilot.sh"

    def __post_init__(self) -> None:
        if self.host != "127.0.0.1":
            raise RemotePilotControlError("远程 Pilot 只允许绑定 127.0.0.1。")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise RemotePilotControlError("端口必须是 1–65535 的整数。")
        root = self.root.resolve()
        runtime = self.runtime_dir.expanduser().resolve()
        db = self.db_path.expanduser().resolve()
        if _inside(runtime, root) or _inside(db, root):
            raise RemotePilotControlError("runtime 和 SQLite 必须位于仓库之外。")
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "runtime_dir", runtime)
        object.__setattr__(self, "db_path", db)
        object.__setattr__(self, "runner_path", self.runner_path.expanduser().resolve())


def load_simple_env(path: str | Path) -> dict[str, str]:
    """Parse simple KEY=value lines without executing shell syntax."""
    path = Path(path)
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RemotePilotControlError("无法读取配置文件。") from error
    for raw in lines:
        line = raw.rstrip("\r")
        match = re.match(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


class RemotePilotOperator:
    """Control one owner-managed supervisor and nothing else."""

    def __init__(
        self,
        config: OperatorConfig,
        *,
        env: Mapping[str, str] | None = None,
        load_env_file: bool = True,
        preflight_runner: Callable[[OperatorConfig, Mapping[str, str]], dict[str, Any]] | None = None,
        health_checker: Callable[[OperatorConfig], bool] | None = None,
        port_probe: Callable[[OperatorConfig], bool] | None = None,
        tunnel_probe: Callable[[int], bool] | None = None,
        process_reader: Callable[[], Iterable[ProcessInfo]] | None = None,
        signaler: Callable[[int, int], None] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        merged = dict(os.environ if env is None else env)
        if load_env_file:
            merged.update(load_simple_env(config.root / ".env"))
        self.env = merged
        self._preflight_runner = preflight_runner or _run_preflight
        self._health_checker = health_checker or _health_check
        self._port_probe = port_probe or _port_available
        self._tunnel_probe = tunnel_probe or _tunnel_running
        self._process_reader = process_reader or _read_processes
        self._signaler = signaler or os.kill
        self._sleep = sleeper

    @property
    def metadata_path(self) -> Path:
        return self.config.runtime_dir / "runtime_metadata.json"

    @property
    def supervisor_pid_path(self) -> Path:
        return self.config.runtime_dir / "supervisor.pid"

    @property
    def url_path(self) -> Path:
        return self.config.runtime_dir / "public_url.txt"

    @property
    def remote_log_path(self) -> Path:
        return self.config.runtime_dir / "remote_pilot.log"

    @property
    def tunnel_log_path(self) -> Path:
        return self.config.runtime_dir / "cloudflared.log"

    @property
    def streamlit_log_path(self) -> Path:
        return self.config.runtime_dir / "streamlit.log"

    def start(
        self,
        *,
        timeout: float | None = None,
        app_timeout: float | None = None,
        tunnel_timeout: float | None = None,
    ) -> int:
        app_timeout, tunnel_timeout = _readiness_timeouts(timeout, app_timeout, tunnel_timeout)
        if not self._ensure_access_code():
            return 1
        inspection = self._inspect()
        if inspection["state"] == "RUNNING":
            _print_running(self.config, inspection.get("url"), self.env)
            return 0
        if inspection["state"] in {"STARTING", "DEGRADED"}:
            metadata = self._read_metadata() or {}
            pid = inspection.get("pid")
            if not isinstance(pid, int):
                print("受管远程内测状态无效；未重复启动。", file=sys.stderr)
                return 1
            if not inspection.get("health"):
                app_result = self._await_local_health(pid, app_timeout)
                if app_result != "ready":
                    print("已有受管远程内测的本地应用尚未健康；未重复启动。", file=sys.stderr)
                    return 1
            tunnel_result = self._await_tunnel_url(pid, tunnel_timeout, metadata=metadata)
            if tunnel_result == "ready":
                _print_running(self.config, self._read_url(), self.env)
                return 0
            if tunnel_result == "pending":
                print("远程内测仍在等待 Quick Tunnel URL；受管本地应用保持运行。", file=sys.stderr)
                return PENDING_TUNNEL_EXIT_CODE
            print("已有受管远程内测未能完成隧道就绪；未重复启动。", file=sys.stderr)
            return 1
        if inspection["state"] == "STALE":
            if inspection.get("identity_mismatch"):
                print("发现 PID 身份不匹配；未终止任何进程，请人工检查。", file=sys.stderr)
                return 1
            self._clear_transient()
        if inspection["state"] == "PORT_CONFLICT":
            print(inspection["message"], file=sys.stderr)
            return 1
        if not self._port_probe(self.config):
            print(self._port_conflict_message(), file=sys.stderr)
            return 1
        try:
            report = self._preflight_runner(self.config, self._remote_pilot_env())
            if report.get("summary", {}).get("fail", 0):
                print("远程严格预检失败，未启动内测。", file=sys.stderr)
                return 1
        except (OSError, RemotePilotControlError, ValueError):
            print("远程严格预检失败，未启动内测。", file=sys.stderr)
            return 1

        self.config.runtime_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.config.runtime_dir, 0o700)
        self._clear_transient()
        log_offset = self.remote_log_path.stat().st_size if self.remote_log_path.exists() else 0
        tunnel_log_offset = self.tunnel_log_path.stat().st_size if self.tunnel_log_path.exists() else 0
        try:
            if self.remote_log_path.exists():
                os.chmod(self.remote_log_path, 0o600)
            with self.remote_log_path.open("a", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [
                        str(self.config.runner_path.resolve()),
                        "--port", str(self.config.port),
                        "--db-path", str(self.config.db_path),
                        "--runtime-dir", str(self.config.runtime_dir),
                        "--managed-by-controller",
                    ],
                    cwd=self.config.root,
                    env=self._child_env(),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except (OSError, ValueError):
            print("远程内测启动器无法启动。", file=sys.stderr)
            return 1
        self._write_metadata(
            process.pid,
            public_url=None,
            log_offset=log_offset,
            tunnel_log_offset=tunnel_log_offset,
        )
        self.supervisor_pid_path.write_text(f"{process.pid}\n", encoding="ascii")
        os.chmod(self.supervisor_pid_path, 0o600)
        os.chmod(self.remote_log_path, 0o600)
        app_result = self._await_local_health(process.pid, app_timeout)
        if app_result != "ready":
            self._terminate_verified(process.pid)
            self._clear_transient()
            print("本地 Streamlit 未在限定时间内就绪；已清理本轮启动器。", file=sys.stderr)
            return 1
        tunnel_result = self._await_tunnel_url(
            process.pid,
            tunnel_timeout,
            metadata=self._read_metadata() or {},
        )
        if tunnel_result == "ready":
            url = self._read_url()
            _print_running(self.config, url, self.env)
            return 0
        if tunnel_result == "pending":
            print(
                "本地 Streamlit 已健康，但仍在等待 Quick Tunnel URL；受管实例保持运行。"
                "稍后运行 status 或 url。",
                file=sys.stderr,
            )
            return PENDING_TUNNEL_EXIT_CODE
        self._terminate_verified(process.pid)
        self._clear_transient()
        print("Quick Tunnel 未能启动或 supervisor 已退出；已清理本轮启动器。", file=sys.stderr)
        return 1

    def status(self) -> int:
        inspection = self._inspect()
        state = inspection["state"]
        print(f"状态：{state}")
        print(f"supervisor PID：{inspection.get('pid', '无')}（{inspection.get('pid_status', '不存在')}）")
        print(f"PID 身份：{'匹配' if inspection.get('identity') else '不匹配/未知'}")
        print(f"Streamlit health：{'通过' if inspection.get('health') else '未通过'}")
        port_available = self._port_probe(self.config)
        print(f"端口监听：{'否' if port_available else '是或被占用'}")
        print(f"cloudflared：{'运行中' if inspection.get('tunnel') else '未确认'}")
        print(f"公网 URL：{'已获取' if inspection.get('url') else '未获取'}")
        present, valid = _access_status(self.env)
        print(f"访问码：present={str(present).lower()} valid={str(valid).lower()}")
        print(f"SQLite：{self.config.db_path}")
        print(f"runtime：{self.config.runtime_dir}")
        return 0 if state in {"RUNNING", "STARTING", "STOPPED"} else 1

    def url(self, *, wait: float = 0.0) -> int:
        wait = _wait_timeout(wait)
        inspection = self._inspect()
        url = inspection.get("url")
        if inspection["state"] == "RUNNING" and url:
            if self._read_url() != url:
                self._write_url(url)
            print(url)
            return 0
        if wait and inspection["state"] in {"STARTING", "DEGRADED"} and isinstance(inspection.get("pid"), int):
            result = self._await_tunnel_url(
                inspection["pid"],
                wait,
                metadata=self._read_metadata() or {},
            )
            if result == "ready":
                print(self._read_url())
                return 0
        if inspection["state"] == "STARTING":
            print("本地应用正在运行，仍在等待 Quick Tunnel URL。", file=sys.stderr)
            return PENDING_TUNNEL_EXIT_CODE
        print("当前没有可确认有效的公网 URL。", file=sys.stderr)
        return 1

    def logs(self, *, lines: int = 100, follow: bool = False) -> int:
        if isinstance(lines, bool) or not isinstance(lines, int) or not 1 <= lines <= 10000:
            print("日志行数必须是 1–10000 的整数。", file=sys.stderr)
            return 2
        paths = [path for path in (self.remote_log_path, self.streamlit_log_path, self.tunnel_log_path) if path.is_file()]
        if not paths:
            print("当前没有远程内测日志。")
            return 0
        if follow:
            process: subprocess.Popen[str] | None = None
            try:
                process = subprocess.Popen(
                    ["tail", "-n", str(lines), "-f", *(str(path) for path in paths)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    print(_redact_text(line.rstrip("\n"), self._secret_values()))
            except KeyboardInterrupt:
                if process is not None:
                    process.terminate()
                return 130
            except (OSError, subprocess.SubprocessError):
                return 1
            return 0
        output: list[str] = []
        for path in paths:
            try:
                content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                print("无法读取远程内测日志。", file=sys.stderr)
                return 1
            output.append(f"--- {path.name} ---")
            output.extend(content[-lines:])
        print(_redact_text("\n".join(output), self._secret_values()))
        return 0

    def stop(self, *, timeout: float = 15.0) -> int:
        timeout = _timeout(timeout)
        inspection = self._inspect()
        state = inspection["state"]
        pid = inspection.get("pid")
        if state == "STOPPED":
            self._clear_transient()
            print("当前没有运行中的远程内测。")
            return 0
        if state == "STALE" and not inspection.get("identity_mismatch"):
            self._clear_transient()
            print("已清理失效的远程内测运行元数据；没有终止未知进程。")
            return 0
        if not isinstance(pid, int) or not inspection.get("identity"):
            print("受管 PID 身份无法验证；未终止进程。", file=sys.stderr)
            return 1
        self._terminate_verified(pid, timeout=timeout)
        deadline = time.monotonic() + timeout
        while _pid_alive(pid) and time.monotonic() < deadline:
            self._sleep(0.1)
        if _pid_alive(pid):
            print("受管 supervisor 未能退出；未清理其余进程。", file=sys.stderr)
            return 1
        self._clear_transient()
        if self._health_checker(self.config) or not self._port_probe(self.config):
            print("supervisor 已退出，但 health/端口仍需人工确认；未终止未知进程。", file=sys.stderr)
            return 1
        print("远程内测已停止；SQLite 学习记录已保留。")
        return 0

    def restart(
        self,
        *,
        timeout: float | None = None,
        app_timeout: float | None = None,
        tunnel_timeout: float | None = None,
    ) -> int:
        app_timeout, tunnel_timeout = _readiness_timeouts(timeout, app_timeout, tunnel_timeout)
        if not self._ensure_access_code():
            return 1
        if self.stop(timeout=min(app_timeout, 15.0)) not in {0}:
            return 1
        return self.start(app_timeout=app_timeout, tunnel_timeout=tunnel_timeout)

    def doctor(self) -> int:
        if not self._ensure_access_code():
            return 1
        try:
            report = self._preflight_runner(self.config, self._remote_pilot_env())
        except Exception:
            print("doctor：远程严格预检无法完成。", file=sys.stderr)
            return 1
        for item in report.get("checks", []):
            if isinstance(item, dict):
                print(f"[{item.get('status', 'UNKNOWN')}] {item.get('check_id', 'unknown')}: {item.get('message', '')}")
        status_code = self.status()
        return 1 if report.get("summary", {}).get("fail", 0) or status_code else 0

    def cleanup_legacy(self, *, port: int, confirm: bool = False) -> int:
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            print("端口必须是 1–65535 的整数。", file=sys.stderr)
            return 2
        matches = [item for item in self._process_reader() if _legacy_match(item, self.config.root, port)]
        if not matches:
            print("没有发现精确匹配的旧版 Pilot 进程。")
            return 0
        for item in matches:
            print(f"匹配 PID {item.pid}：{_safe_command(item.command, self._secret_values())}")
        if not confirm:
            print("未执行清理；如确认这些进程属于本仓库旧版 Pilot，请加 --confirm。")
            return 0
        # cloudflared first, then Streamlit; every signal is revalidated.
        ordered = sorted(matches, key=lambda item: 0 if _is_legacy_cloudflared(item, port) else 1)
        for item in ordered:
            current = _find_process(item.pid, self._process_reader())
            if current is None or not _legacy_match(current, self.config.root, port):
                continue
            self._signaler(item.pid, signal.SIGTERM)
            self._wait_pid(item.pid, timeout=5.0)
            if _pid_alive(item.pid):
                current = _find_process(item.pid, self._process_reader())
                if current is not None and _legacy_match(current, self.config.root, port):
                    self._signaler(item.pid, signal.SIGKILL)
        if not any(_legacy_match(item, self.config.root, port) for item in self._process_reader()):
            print("旧版 Pilot 进程已处理，未触碰其他进程。")
            return 0
        print("仍有精确匹配进程存活；未继续扩大清理范围。", file=sys.stderr)
        return 1

    def _await_local_health(self, pid: int, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                return "supervisor_exited"
            # A just-exec'd shell may briefly expose an incomplete cmdline;
            # keep waiting rather than treating that harmless transition as
            # a dead or reused PID.
            if not self._identity_matches(pid):
                self._sleep(0.05)
                continue
            if self._health_checker(self.config):
                return "ready"
            self._sleep(0.2)
        return "timeout"

    def _await_tunnel_url(self, pid: int, timeout: float, *, metadata: Mapping[str, Any]) -> str:
        deadline = time.monotonic() + timeout
        started = time.monotonic()
        tunnel_seen = False
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                return "supervisor_exited"
            if not self._identity_matches(pid):
                self._sleep(0.05)
                continue
            if not self._health_checker(self.config):
                return "app_lost"
            tunnel = self._tunnel_probe(pid)
            tunnel_seen = tunnel_seen or tunnel
            url = self._refresh_url(metadata, persist=True)
            if url:
                return "ready"
            if (tunnel_seen or time.monotonic() - started >= TUNNEL_START_GRACE_SECONDS) and not tunnel:
                return "tunnel_exited"
            self._sleep(0.2)
        if self._health_checker(self.config) and self._tunnel_probe(pid):
            return "pending"
        return "tunnel_exited"

    def _inspect(self) -> dict[str, Any]:
        metadata = self._read_metadata()
        pid = _read_pid(self.supervisor_pid_path)
        pid_file_exists = self.supervisor_pid_path.exists()
        metadata_file_exists = self.metadata_path.exists()
        if pid is None and isinstance(metadata, dict):
            raw = metadata.get("supervisor_pid")
            pid = raw if isinstance(raw, int) and not isinstance(raw, bool) else None
        if pid is None:
            if pid_file_exists or metadata_file_exists:
                return {"state": "STALE", "pid_status": "元数据无效", "identity": False, "identity_mismatch": False}
            if not self._port_probe(self.config):
                return {"state": "PORT_CONFLICT", "message": self._port_conflict_message()}
            return {"state": "STOPPED", "pid_status": "不存在", "health": False, "tunnel": False}
        alive = _pid_alive(pid)
        identity = alive and self._identity_matches(pid)
        if not alive:
            return {"state": "STALE", "pid": pid, "pid_status": "已退出", "identity": False, "identity_mismatch": False}
        if not identity:
            return {"state": "STALE", "pid": pid, "pid_status": "存活", "identity": False, "identity_mismatch": True}
        health = self._health_checker(self.config)
        tunnel = self._tunnel_probe(pid)
        url = self._refresh_url(metadata)
        if health and tunnel and url:
            state = "RUNNING"
        elif health or tunnel or url:
            state = "STARTING"
        else:
            state = "DEGRADED"
        return {
            "state": state, "pid": pid, "pid_status": "存活", "identity": True,
            "health": health, "tunnel": tunnel, "url": url,
        }

    def _identity_matches(self, pid: int) -> bool:
        info = _read_process(pid)
        if info is None or info.uid != os.getuid():
            return False
        metadata = self._read_metadata()
        if not isinstance(metadata, dict):
            return False
        if metadata.get("supervisor_pid") != pid:
            return False
        if metadata.get("host") != self.config.host or metadata.get("port") != self.config.port:
            return False
        if metadata.get("db_path") != str(self.config.db_path) or metadata.get("runtime_dir") != str(self.config.runtime_dir):
            return False
        expected = str(self.config.runner_path.resolve())
        if expected not in info.argv:
            return False
        pairs = {
            "--port": str(self.config.port),
            "--db-path": str(self.config.db_path),
            "--runtime-dir": str(self.config.runtime_dir),
        }
        return all(_argv_pair(info.argv, key, value) for key, value in pairs.items())

    def _terminate_verified(self, pid: int, *, timeout: float = 15.0) -> None:
        if not self._identity_matches(pid):
            return
        try:
            self._signaler(pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            return
        deadline = time.monotonic() + _timeout(timeout)
        while _pid_alive(pid) and time.monotonic() < deadline:
            self._sleep(0.1)
        if _pid_alive(pid) and self._identity_matches(pid):
            try:
                self._signaler(pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass

    def _wait_pid(self, pid: int, *, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while _pid_alive(pid) and time.monotonic() < deadline:
            self._sleep(0.1)

    def _child_env(self) -> dict[str, str]:
        environment = self._remote_pilot_env()
        source = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = f"src{os.pathsep}{source}" if source else "src"
        return environment

    def _remote_pilot_env(self) -> dict[str, str]:
        """Return a child-only environment for remote Pilot operations."""
        environment = dict(self.env)
        environment.update({
            "INTROAI_PILOT_MODE": "1",
            "INTROAI_PILOT_HOST": "127.0.0.1",
            "INTROAI_STATE_DB": str(self.config.db_path),
        })
        return environment

    def _read_metadata(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or data.get("schema_version") != METADATA_SCHEMA_VERSION:
            return None
        return data

    def _write_metadata(
        self,
        pid: int,
        *,
        public_url: str | None,
        log_offset: int = 0,
        tunnel_log_offset: int = 0,
    ) -> None:
        payload = {
            "schema_version": METADATA_SCHEMA_VERSION,
            "supervisor_pid": pid,
            "host": self.config.host,
            "port": self.config.port,
            "db_path": str(self.config.db_path),
            "runtime_dir": str(self.config.runtime_dir),
            "started_at_utc": _utc_now(),
            "run_id": os.urandom(12).hex(),
            "public_url": public_url,
            "log_offset": log_offset,
            "tunnel_log_offset": tunnel_log_offset,
        }
        _atomic_json(self.metadata_path, payload)

    def _write_url(self, url: str) -> None:
        self.url_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.url_path.with_name(f".{self.url_path.name}.tmp-{os.getpid()}")
        temporary.write_text(url + "\n", encoding="ascii")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.url_path)
        metadata = self._read_metadata()
        if metadata is not None:
            metadata["public_url"] = url
            _atomic_json(self.metadata_path, metadata)

    def _read_url(self) -> str | None:
        try:
            value = self.url_path.read_text(encoding="ascii").strip()
        except OSError:
            return None
        return value if URL_PATTERN.fullmatch(value) else None

    def _refresh_url(self, metadata: Mapping[str, Any], *, persist: bool = False) -> str | None:
        existing = self._read_url()
        if existing:
            return existing
        raw_offset = metadata.get("tunnel_log_offset", 0)
        offset = raw_offset if isinstance(raw_offset, int) and raw_offset >= 0 else 0
        url = self._url_from_log(self.tunnel_log_path, offset=offset)
        if url and persist:
            self._write_url(url)
        return url

    def _url_from_log(self, path: Path, *, offset: int = 0) -> str | None:
        try:
            with path.open("rb") as stream:
                stream.seek(max(0, offset))
                text = stream.read().decode("utf-8", "replace")
        except OSError:
            return None
        matches = URL_PATTERN.findall(text)
        return matches[-1] if matches else None

    def _clear_transient(self) -> None:
        for path in (self.supervisor_pid_path, self.metadata_path, self.url_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

    def _port_conflict_message(self) -> str:
        owner = _port_owner_summary(self.config.port, self._secret_values())
        return f"端口 {self.config.port} 已被占用；未自动终止未知进程。{owner}"

    def _secret_values(self) -> tuple[str, ...]:
        values = []
        for key in ("INTROAI_PILOT_ACCESS_CODE", "DEEPSEEK_API_KEY"):
            value = self.env.get(key)
            if isinstance(value, str) and value:
                values.append(value)
        return tuple(values)

    def _ensure_access_code(self) -> bool:
        present, valid = _access_status(self.env)
        if present and valid:
            return True
        if not sys.stdin.isatty():
            print("缺少有效访问码；非交互模式不会读取或回显秘密。", file=sys.stderr)
            return False
        try:
            value = getpass.getpass("请输入本轮远程内测访问码：")
        except (EOFError, KeyboardInterrupt):
            print("未获取访问码；未启动或修改远程内测。", file=sys.stderr)
            return False
        self.env["INTROAI_PILOT_ACCESS_CODE"] = value
        _present, valid = _access_status(self.env)
        if not valid:
            self.env.pop("INTROAI_PILOT_ACCESS_CODE", None)
            print("访问码格式无效；未启动或修改远程内测。", file=sys.stderr)
            return False
        return True


def _run_preflight(config: OperatorConfig, env: Mapping[str, str]) -> dict[str, Any]:
    command = [
        sys.executable, "tools/pilot_preflight.py", "--strict", "--format", "json",
        "--remote", "--tunnel-provider", "cloudflared", "--host", config.host,
        "--port", str(config.port), "--db-path", str(config.db_path),
    ]
    result = subprocess.run(command, cwd=config.root, env=dict(env), capture_output=True, text=True, check=False)
    try:
        report = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        raise RemotePilotControlError("远程严格预检没有返回有效报告。") from None
    if not isinstance(report, dict):
        raise RemotePilotControlError("远程严格预检报告格式无效。")
    return report


def _health_check(config: OperatorConfig) -> bool:
    try:
        # A remote Pilot health probe is strictly loopback-only.  Explicitly
        # disable ambient HTTP(S) proxies so a developer's proxy environment
        # cannot make a healthy local Streamlit server look unavailable.
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"http://{config.host}:{config.port}/_stcore/health", timeout=1.0) as response:
            return 200 <= response.status < 300
    except (OSError, URLError, TimeoutError):
        return False


def _port_available(config: OperatorConfig) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((config.host, config.port))
    except OSError:
        return False
    return True


def _tunnel_running(supervisor_pid: int) -> bool:
    for child in _descendants(supervisor_pid):
        if any(token == "cloudflared" or Path(token).name == "cloudflared" for token in child.argv):
            return True
    return False


def _read_processes() -> Iterable[ProcessInfo]:
    proc = Path("/proc")
    try:
        entries = list(proc.iterdir())
    except OSError:
        return []
    result: list[ProcessInfo] = []
    for entry in entries:
        if entry.name.isdigit():
            item = _read_process(int(entry.name))
            if item is not None:
                result.append(item)
    return result


def _read_process(pid: int) -> ProcessInfo | None:
    if pid <= 0:
        return None
    base = Path("/proc") / str(pid)
    try:
        raw = (base / "cmdline").read_bytes()
        argv = tuple(item.decode("utf-8", "replace") for item in raw.split(b"\0") if item)
        status = (base / "status").read_text(encoding="utf-8", errors="replace")
        uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
        uid = int(uid_line.split()[1])
        cwd = (base / "cwd").resolve()
    except (OSError, ValueError, StopIteration):
        return None
    return ProcessInfo(pid=pid, uid=uid, argv=argv, cwd=cwd)


def _descendants(pid: int) -> list[ProcessInfo]:
    result: list[ProcessInfo] = []
    queue = [pid]
    seen = {pid}
    while queue:
        parent = queue.pop(0)
        try:
            children = (Path("/proc") / str(parent) / "task" / str(parent) / "children").read_text().split()
        except OSError:
            continue
        for raw in children:
            if not raw.isdigit() or int(raw) in seen:
                continue
            child_pid = int(raw)
            seen.add(child_pid)
            info = _read_process(child_pid)
            if info is not None:
                result.append(info)
                queue.append(child_pid)
    return result


def _pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text()
        state = stat.split(")", 1)[1].split()[0]
        return state != "Z"
    except (OSError, IndexError):
        return True


def _read_pid(path: Path) -> int | None:
    try:
        value = path.read_text(encoding="ascii").strip()
    except OSError:
        return None
    return int(value) if PID_PATTERN.fullmatch(value) else None


def _argv_pair(argv: tuple[str, ...], key: str, value: str) -> bool:
    return any(argv[index] == key and index + 1 < len(argv) and argv[index + 1] == value for index in range(len(argv)))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0 or value > 300:
        raise RemotePilotControlError("timeout 必须在 0 和 300 秒之间。")
    return float(value)


def _wait_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 300:
        raise RemotePilotControlError("wait 必须在 0 和 300 秒之间。")
    return float(value)


def _readiness_timeouts(
    timeout: float | None,
    app_timeout: float | None,
    tunnel_timeout: float | None,
) -> tuple[float, float]:
    """Resolve the legacy combined timeout without coupling readiness states."""
    if timeout is not None:
        shared = _timeout(timeout)
        if app_timeout is None:
            app_timeout = shared
        if tunnel_timeout is None:
            tunnel_timeout = shared
    return (
        _timeout(DEFAULT_APP_TIMEOUT if app_timeout is None else app_timeout),
        _timeout(DEFAULT_TUNNEL_TIMEOUT if tunnel_timeout is None else tunnel_timeout),
    )


def _access_status(env: Mapping[str, str]) -> tuple[bool, bool]:
    value = env.get("INTROAI_PILOT_ACCESS_CODE", "")
    if not isinstance(value, str):
        return False, False
    present = bool(value.strip())
    valid = 12 <= len(value.strip()) <= 128 and all(c.isprintable() and c not in "\r\n\t" for c in value.strip())
    return present, valid


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _print_running(config: OperatorConfig, url: str | None, env: Mapping[str, str]) -> None:
    print("远程内测已经运行。")
    print(f"本地 URL：http://127.0.0.1:{config.port}")
    print(f"公网 HTTPS URL：{url or '尚未获取；稍后运行 url'}")
    print(f"SQLite：{config.db_path}")
    print(f"runtime：{config.runtime_dir}")
    present, valid = _access_status(env)
    print(f"访问码：{'已配置' if present and valid else '未配置或格式无效'}")
    print("后续命令：status / url / logs / stop / restart")


def _safe_command(command: str, secrets: Iterable[str] = ()) -> str:
    result = re.sub(r"\s+", " ", command).strip()[:240]
    return _redact_text(result, secrets)


def _redact_text(text: str, secrets: Iterable[str]) -> str:
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[已隐藏]")
    return result


def _port_owner_summary(port: int, secrets: Iterable[str] = ()) -> str:
    for tool in ("ss", "lsof"):
        executable = shutil.which(tool)
        if not executable:
            continue
        try:
            if tool == "ss":
                result = subprocess.run([executable, "-ltnp"], capture_output=True, text=True, check=False, timeout=2)
                lines = [line for line in result.stdout.splitlines() if f":{port} " in line or f":{port}\n" in line]
            else:
                result = subprocess.run([executable, "-nP", "-iTCP:" + str(port), "-sTCP:LISTEN"], capture_output=True, text=True, check=False, timeout=2)
                lines = result.stdout.splitlines()
            if lines:
                return "占用摘要：" + _safe_command(lines[-1], secrets)
        except (OSError, subprocess.SubprocessError):
            continue
    return "未能安全确定占用者 PID。"


def _legacy_match(item: ProcessInfo, root: Path, port: int) -> bool:
    if item.uid != os.getuid():
        return False
    return _is_legacy_streamlit(item, root, port) or _is_legacy_cloudflared(item, port)


def _is_legacy_streamlit(item: ProcessInfo, root: Path, port: int) -> bool:
    argv = item.argv
    if "-m" not in argv or "streamlit" not in argv or "run" not in argv or not _argv_pair(argv, "--server.address", "127.0.0.1") or not _argv_pair(argv, "--server.port", str(port)):
        return False
    try:
        app_index = argv.index("run") + 1
        app = Path(argv[app_index])
        if not app.is_absolute():
            app = (item.cwd or Path.cwd()) / app
        return app.resolve() == (root / "app.py").resolve()
    except (ValueError, IndexError, OSError):
        return False


def _is_legacy_cloudflared(item: ProcessInfo, port: int) -> bool:
    argv = item.argv
    return (
        bool(argv)
        and Path(argv[0]).name == "cloudflared"
        and tuple(argv[1:]) == ("tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate")
    )


def _find_process(pid: int, processes: Iterable[ProcessInfo]) -> ProcessInfo | None:
    return next((item for item in processes if item.pid == pid), None)


def _parse_config(args: argparse.Namespace) -> OperatorConfig:
    runtime_dir = getattr(args, "runtime_dir", None)
    db_path = getattr(args, "db_path", None)
    port = getattr(args, "port", None)
    return OperatorConfig(
        runtime_dir=Path(runtime_dir).expanduser() if runtime_dir else DEFAULT_RUNTIME,
        db_path=Path(db_path).expanduser() if db_path else DEFAULT_DB,
        port=port if port is not None else DEFAULT_PORT,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IntroAI Tutor P4d.1 远程内测控制器。")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--port", type=int, default=None)
        command_parser.add_argument("--db-path", default=None)
        command_parser.add_argument("--runtime-dir", default=None)
    for name in ("start", "status", "url", "logs", "restart", "doctor", "stop"):
        item = sub.add_parser(name)
        common(item)
        if name in {"start", "restart"}:
            item.add_argument("--timeout", type=float, default=None, help="兼容参数：同时设置两类等待时间")
            item.add_argument("--app-timeout", type=float, default=None, help=f"本地应用等待秒数（默认 {int(DEFAULT_APP_TIMEOUT)}）")
            item.add_argument("--tunnel-timeout", type=float, default=None, help=f"Quick Tunnel URL 等待秒数（默认 {int(DEFAULT_TUNNEL_TIMEOUT)}）")
        if name == "stop":
            item.add_argument("--timeout", type=float, default=15.0)
        if name == "logs":
            item.add_argument("--lines", type=int, default=100)
            item.add_argument("--follow", action="store_true")
        if name == "url":
            item.add_argument("--wait", type=float, default=0.0)
    legacy = sub.add_parser("cleanup-legacy")
    common(legacy)
    legacy.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = _parse_config(args)
        # cleanup-legacy is an offline process inspection command.  It must
        # not need, parse, or expose any dotenv secrets.
        operator = RemotePilotOperator(
            config,
            env={} if args.command == "cleanup-legacy" else None,
            load_env_file=args.command != "cleanup-legacy",
        )
        if args.command == "start":
            return operator.start(
                timeout=args.timeout,
                app_timeout=args.app_timeout,
                tunnel_timeout=args.tunnel_timeout,
            )
        if args.command == "status":
            return operator.status()
        if args.command == "url":
            return operator.url(wait=args.wait)
        if args.command == "logs":
            return operator.logs(lines=args.lines, follow=args.follow)
        if args.command == "stop":
            return operator.stop(timeout=args.timeout)
        if args.command == "restart":
            return operator.restart(
                timeout=args.timeout,
                app_timeout=args.app_timeout,
                tunnel_timeout=args.tunnel_timeout,
            )
        if args.command == "doctor":
            return operator.doctor()
        return operator.cleanup_legacy(port=config.port, confirm=args.confirm)
    except (RemotePilotControlError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except Exception:
        correlation_id = os.urandom(6).hex()
        print(f"控制器内部错误；未执行不安全操作。参考 ID：{correlation_id}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
