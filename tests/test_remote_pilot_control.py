"""Offline operator-control tests with synthetic supervisors and processes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import pytest

from tools.remote_pilot_control import (
    PENDING_TUNNEL_EXIT_CODE,
    OperatorConfig,
    ProcessInfo,
    RemotePilotOperator,
    load_simple_env,
)
import tools.remote_pilot_control as remote_control


ROOT = Path(__file__).resolve().parents[1]
TEST_CODE = "operator-test-code-2026"


def _fake_runner(
    tmp_path: Path,
    *,
    url: str | None = "https://pilot-one.trycloudflare.com",
    url_delay: float = 0.0,
    split_url: bool = False,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "fake_run_remote_pilot.sh"
    if url:
        if split_url:
            midpoint = len(url) // 2
            output = (
                f"sleep {url_delay}\n"
                f"printf '%s' '{url[:midpoint]}' >>\"$runtime_dir/cloudflared.log\"\n"
                "sleep 0.05\n"
                f"printf '%s\\n' '{url[midpoint:]}' >>\"$runtime_dir/cloudflared.log\"\n"
            )
        else:
            output = f"sleep {url_delay}\nprintf '%s\\n' '{url}' >>\"$runtime_dir/cloudflared.log\"\n"
    else:
        output = ""
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "trap 'exit 0' TERM INT\n"
        "runtime_dir=''\n"
        "managed_by_controller=0\n"
        "while (($#)); do\n"
        "  case \"$1\" in\n"
        "    --runtime-dir) runtime_dir=\"$2\"; shift 2 ;;\n"
        "    --managed-by-controller) managed_by_controller=1; shift ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "mkdir -p \"$runtime_dir\"\n"
        "printf 'fake_pilot_mode=%s\\n' \"${INTROAI_PILOT_MODE:-missing}\"\n"
        "printf 'fake_managed_by_controller=%s\\n' \"$managed_by_controller\"\n"
        + output
        + "while :; do sleep 0.1; done\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _operator(
    tmp_path: Path,
    *,
    runner: Path | None = None,
    url: str | None = "https://pilot-one.trycloudflare.com",
    health=None,
    env=None,
    include_access_code=True,
    preflight_runner=None,
):
    runtime = tmp_path / "artifacts" / "runtime"
    database = tmp_path / "artifacts" / "state.sqlite3"
    config = OperatorConfig(root=ROOT, runtime_dir=runtime, db_path=database, runner_path=runner or _fake_runner(tmp_path, url=url))
    health_checker = health or (lambda _config: _metadata_pid_alive(runtime / "runtime_metadata.json"))
    operator = RemotePilotOperator(
        config,
        env=({"INTROAI_PILOT_ACCESS_CODE": TEST_CODE} if include_access_code else {}) | (env or {}),
        load_env_file=False,
        preflight_runner=preflight_runner or (lambda _config, _env: {"summary": {"fail": 0}, "checks": []}),
        health_checker=health_checker,
        port_probe=lambda _config: True,
        tunnel_probe=lambda _pid: True,
    )
    return operator


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _metadata_pid_alive(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _pid_alive(data.get("supervisor_pid"))
    except (OSError, ValueError, TypeError):
        return False


def test_start_status_url_logs_stop_and_stop_is_idempotent(tmp_path, capsys):
    operator = _operator(tmp_path)
    assert operator.start(timeout=3) == 0
    metadata = json.loads(operator.metadata_path.read_text(encoding="utf-8"))
    assert _pid_alive(metadata["supervisor_pid"])
    assert operator.status() == 0
    assert operator.url() == 0
    assert operator.logs(lines=20) == 0
    assert operator.stop(timeout=3) == 0
    assert operator.stop(timeout=3) == 0
    assert not operator.url_path.exists()
    output = capsys.readouterr().out
    assert "pilot-one.trycloudflare.com" in output
    assert TEST_CODE not in output


def test_doctor_and_start_enable_pilot_mode_without_mutating_parent_environment(tmp_path):
    received_environments = []

    def preflight_runner(_config, environment):
        received_environments.append(dict(environment))
        return {
            "summary": {"fail": 0},
            "checks": [
                {"status": "PASS", "check_id": "pilot_mode_config", "message": "pilot mode enabled"},
                {"status": "PASS", "check_id": "remote_pilot_mode", "message": "remote Pilot mode is enabled"},
            ],
        }

    operator = _operator(tmp_path, preflight_runner=preflight_runner)
    assert "INTROAI_PILOT_MODE" not in operator.env
    assert operator.doctor() == 0
    assert operator.start(timeout=3) == 0
    assert [item["INTROAI_PILOT_MODE"] for item in received_environments] == ["1", "1"]
    assert "INTROAI_PILOT_MODE" not in operator.env
    assert "fake_pilot_mode=1" in operator.remote_log_path.read_text(encoding="utf-8")
    assert "fake_managed_by_controller=1" in operator.remote_log_path.read_text(encoding="utf-8")
    assert operator.stop(timeout=3) == 0


def test_doctor_uses_real_remote_strict_preflight_with_pilot_mode_enabled(tmp_path, capsys):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cloudflared = fake_bin / "cloudflared"
    cloudflared.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    cloudflared.chmod(0o755)
    environment = dict(os.environ)
    environment.pop("INTROAI_PILOT_MODE", None)
    environment["INTROAI_PILOT_ACCESS_CODE"] = TEST_CODE
    environment["PATH"] = f"{fake_bin}:{environment.get('PATH', '')}"
    environment["PYTHONPATH"] = str(ROOT / "src")
    config = OperatorConfig(
        root=ROOT,
        runtime_dir=tmp_path / "artifacts" / "runtime",
        db_path=tmp_path / "artifacts" / "state.sqlite3",
        runner_path=_fake_runner(tmp_path),
        port=18504,
    )
    operator = RemotePilotOperator(
        config,
        env=environment,
        load_env_file=False,
        port_probe=lambda _config: True,
    )
    assert operator.doctor() == 0
    output = capsys.readouterr().out
    assert "[PASS] pilot_mode_config: pilot mode enabled" in output
    assert "[PASS] remote_pilot_mode: remote Pilot mode is enabled" in output
    assert "[PASS] production_template_count: production templates=28" in output
    assert "[PASS] active_candidate_count: active candidates=0" in output
    assert "[PASS] blocked_slot_count: blocked slots=1" in output
    assert "[PASS] concept_count: concept registry count checked" in output
    assert "[PASS] sqlite_schema_initialization: SQLite schema=3 initialized" in output
    assert TEST_CODE not in output
    assert "INTROAI_PILOT_MODE" not in operator.env


def test_missing_access_code_fails_closed_without_tty_and_interactive_doctor_injects_only_operator_env(tmp_path, monkeypatch, capsys):
    operator = _operator(tmp_path, include_access_code=False)
    assert operator.doctor() == 1
    assert "缺少有效访问码" in capsys.readouterr().err

    class TtyInput:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(remote_control.sys, "stdin", TtyInput())
    monkeypatch.setattr(remote_control.getpass, "getpass", lambda _prompt: TEST_CODE)
    assert operator.doctor() == 0
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert TEST_CODE not in output
    assert operator.env["INTROAI_PILOT_ACCESS_CODE"] == TEST_CODE


def test_restart_and_read_only_commands_do_not_require_parent_pilot_mode(tmp_path):
    received_environments = []

    def preflight_runner(_config, environment):
        received_environments.append(dict(environment))
        return {"summary": {"fail": 0}, "checks": []}

    operator = _operator(tmp_path, preflight_runner=preflight_runner)
    assert "INTROAI_PILOT_MODE" not in operator.env
    assert operator.start(timeout=3) == 0
    initial_log = operator.remote_log_path.read_text(encoding="utf-8")
    assert operator.status() == 0
    assert operator.url() == 0
    assert operator.logs(lines=10) == 0
    assert operator.remote_log_path.read_text(encoding="utf-8") == initial_log
    assert operator.restart(timeout=3) == 0
    assert operator.stop(timeout=3) == 0
    assert operator.status() == 0
    assert [item["INTROAI_PILOT_MODE"] for item in received_environments] == ["1", "1"]
    assert "INTROAI_PILOT_MODE" not in operator.env


def test_second_start_reuses_healthy_instance_without_duplicate_launch(tmp_path):
    operator = _operator(tmp_path)
    assert operator.start(timeout=3) == 0
    assert operator.start(timeout=3) == 0
    assert operator.tunnel_log_path.read_text(encoding="utf-8").count("trycloudflare.com") == 1
    assert operator.stop(timeout=3) == 0


def test_restart_preserves_database_and_access_code_but_updates_url(tmp_path):
    first_runner = _fake_runner(tmp_path, url="https://first.trycloudflare.com")
    operator = _operator(tmp_path, runner=first_runner)
    assert operator.start(timeout=3) == 0
    first_metadata = json.loads(operator.metadata_path.read_text(encoding="utf-8"))
    first_db = operator.config.db_path
    assert operator.stop(timeout=3) == 0
    second_runner = _fake_runner(tmp_path, url="https://second.trycloudflare.com")
    operator.config = OperatorConfig(
        root=ROOT, runtime_dir=operator.config.runtime_dir, db_path=first_db,
        runner_path=second_runner,
    )
    assert operator.start(timeout=3) == 0
    second_metadata = json.loads(operator.metadata_path.read_text(encoding="utf-8"))
    assert operator._read_url() == "https://second.trycloudflare.com"
    assert second_metadata["run_id"] != first_metadata["run_id"]
    assert operator.env["INTROAI_PILOT_ACCESS_CODE"] == TEST_CODE
    assert operator.config.db_path == first_db
    assert operator.stop(timeout=3) == 0


def test_stale_pid_is_cleaned_without_killing_unknown_process(tmp_path):
    operator = _operator(tmp_path)
    operator.config.runtime_dir.mkdir(parents=True)
    operator.supervisor_pid_path.write_text("999999\n", encoding="ascii")
    operator.metadata_path.write_text(json.dumps({"schema_version": 1, "supervisor_pid": 999999}), encoding="utf-8")
    assert operator.start(timeout=3) == 0
    assert operator.stop(timeout=3) == 0


def test_pid_identity_mismatch_refuses_start_and_stop(tmp_path):
    operator = _operator(tmp_path)
    operator.config.runtime_dir.mkdir(parents=True)
    current = os.getpid()
    operator.supervisor_pid_path.write_text(f"{current}\n", encoding="ascii")
    operator.metadata_path.write_text(json.dumps({"schema_version": 1, "supervisor_pid": current}), encoding="utf-8")
    assert operator.start(timeout=1) == 1
    assert operator.stop(timeout=1) == 1


def test_unknown_port_conflict_fails_closed(tmp_path, capsys):
    operator = _operator(tmp_path)
    operator._port_probe = lambda _config: False
    assert operator.start(timeout=1) == 1
    assert "未自动终止未知进程" in capsys.readouterr().err


def test_local_health_timeout_cleans_supervisor_but_url_timeout_does_not(tmp_path):
    operator = _operator(tmp_path, health=lambda _config: False)
    assert operator.start(timeout=0.3) == 1
    assert not operator.supervisor_pid_path.exists()
    assert not operator.metadata_path.exists()

    no_url = _operator(tmp_path / "no-url", url=None)
    assert no_url.start(timeout=0.3) == PENDING_TUNNEL_EXIT_CODE
    assert no_url.supervisor_pid_path.exists()
    assert no_url.status() == 0
    assert no_url.stop(timeout=3) == 0


def test_healthy_app_with_delayed_url_remains_managed_then_becomes_running(tmp_path, capsys):
    runner = _fake_runner(
        tmp_path,
        url="https://delayed.trycloudflare.com",
        url_delay=0.35,
    )
    operator = _operator(tmp_path, runner=runner)
    assert operator.start(app_timeout=0.2, tunnel_timeout=0.05) == PENDING_TUNNEL_EXIT_CODE
    metadata = json.loads(operator.metadata_path.read_text(encoding="utf-8"))
    assert _pid_alive(metadata["supervisor_pid"])
    assert not operator.url_path.exists()
    assert remote_control._read_process(metadata["supervisor_pid"]) is not None
    assert TEST_CODE not in remote_control._read_process(metadata["supervisor_pid"]).command
    assert operator.status() == 0
    assert "状态：STARTING" in capsys.readouterr().out
    import time
    time.sleep(0.45)
    assert operator.status() == 0
    assert not operator.url_path.exists()
    assert operator.url() == 0
    assert operator._read_url() == "https://delayed.trycloudflare.com"
    assert operator.stop(timeout=3) == 0


def test_old_tunnel_log_url_is_not_reused_and_split_new_url_is_parsed(tmp_path):
    runtime = tmp_path / "artifacts" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "cloudflared.log").write_text("https://old.trycloudflare.com\n", encoding="utf-8")
    runner = _fake_runner(
        tmp_path,
        url="https://split-new.trycloudflare.com",
        url_delay=0.1,
        split_url=True,
    )
    operator = _operator(tmp_path, runner=runner)
    assert operator.start(app_timeout=0.2, tunnel_timeout=1) == 0
    assert operator._read_url() == "https://split-new.trycloudflare.com"
    assert operator.stop(timeout=3) == 0


def test_tunnel_exit_before_url_fails_closed_and_cleans_managed_supervisor(tmp_path, monkeypatch):
    monkeypatch.setattr(remote_control, "TUNNEL_START_GRACE_SECONDS", 0.01)
    operator = _operator(tmp_path, url=None)
    operator._tunnel_probe = lambda _pid: False
    assert operator.start(app_timeout=0.2, tunnel_timeout=0.2) == 1
    assert not operator.supervisor_pid_path.exists()
    assert not operator.metadata_path.exists()


def test_loopback_health_check_ignores_ambient_http_proxy(tmp_path, monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Opener:
        def open(self, url, *, timeout):
            assert url == "http://127.0.0.1:18504/_stcore/health"
            assert timeout == 1.0
            return Response()

    captured = []
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setattr(remote_control, "build_opener", lambda handler: (captured.append(handler), Opener())[1])
    config = OperatorConfig(
        root=ROOT,
        runtime_dir=tmp_path / "artifacts" / "runtime",
        db_path=tmp_path / "artifacts" / "state.sqlite3",
        runner_path=_fake_runner(tmp_path),
        port=18504,
    )
    assert remote_control._health_check(config) is True
    assert len(captured) == 1
    assert captured[0].proxies == {}


def test_real_minimal_streamlit_health_bypasses_invalid_proxy(tmp_path, monkeypatch):
    """Exercise Streamlit's actual health endpoint without app/.env/network use."""
    minimal_app = tmp_path / "minimal_streamlit.py"
    minimal_app.write_text("import streamlit as st\nst.write('pilot health fixture')\n", encoding="utf-8")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
    except PermissionError:
        pytest.skip("sandbox does not permit loopback sockets")
    environment = os.environ.copy()
    environment.update({
        "HTTP_PROXY": "http://127.0.0.1:1",
        "HTTPS_PROXY": "http://127.0.0.1:1",
        "ALL_PROXY": "http://127.0.0.1:1",
        "http_proxy": "http://127.0.0.1:1",
        "https_proxy": "http://127.0.0.1:1",
        "all_proxy": "http://127.0.0.1:1",
    })
    process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(minimal_app),
            "--server.address", "127.0.0.1", "--server.port", str(port),
            "--server.headless", "true", "--server.fileWatcherType", "none",
        ],
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    config = OperatorConfig(
        root=ROOT,
        runtime_dir=tmp_path / "artifacts" / "runtime",
        db_path=tmp_path / "artifacts" / "state.sqlite3",
        runner_path=_fake_runner(tmp_path),
        port=port,
    )
    try:
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline and process.poll() is None:
            if remote_control._health_check(config):
                break
            time.sleep(0.1)
        assert process.poll() is None
        assert remote_control._health_check(config) is True
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_controller_managed_launcher_real_streamlit_delayed_tunnel_lifecycle(tmp_path):
    """Controller → managed launcher → Streamlit → delayed URL → stop, offline."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
    except PermissionError:
        pytest.skip("sandbox does not permit loopback sockets")
    fixture_root = tmp_path / "fixture-root"
    scripts = fixture_root / "scripts"
    tools = fixture_root / "tools"
    scripts.mkdir(parents=True)
    tools.mkdir()
    runner = scripts / "run_remote_pilot.sh"
    runner.write_text((ROOT / "scripts" / "run_remote_pilot.sh").read_text(encoding="utf-8"), encoding="utf-8")
    runner.chmod(0o755)
    (fixture_root / "minimal_streamlit.py").write_text("import streamlit as st\nst.write('pilot lifecycle fixture')\n", encoding="utf-8")
    (scripts / "run_internal_pilot.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "root=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/..\" && pwd)\"\n"
        "port=8504\n"
        "while (($#)); do\n"
        "  if [[ \"$1\" == --port ]]; then port=\"$2\"; shift 2; else shift; fi\n"
        "done\n"
        "exec python -m streamlit run \"$root/minimal_streamlit.py\" --server.address 127.0.0.1 --server.port \"$port\" --server.headless true --server.fileWatcherType none\n",
        encoding="utf-8",
    )
    (scripts / "run_internal_pilot.sh").chmod(0o755)
    (tools / "pilot_preflight.py").write_text("print('synthetic preflight')\n", encoding="utf-8")
    fake_bin = fixture_root / "bin"
    fake_bin.mkdir()
    (fake_bin / "cloudflared").write_text(
        "#!/usr/bin/env bash\n"
        "trap 'exit 0' TERM INT\n"
        "sleep 1.5\n"
        "printf '%s\\n' 'https://delayed-lifecycle.trycloudflare.com'\n"
        "while :; do sleep 0.1; done\n",
        encoding="utf-8",
    )
    (fake_bin / "cloudflared").chmod(0o755)
    environment = os.environ.copy()
    environment.update({
        "INTROAI_PILOT_ACCESS_CODE": TEST_CODE,
        "PATH": f"{fake_bin}:{environment['PATH']}",
        "HTTP_PROXY": "http://127.0.0.1:1",
        "HTTPS_PROXY": "http://127.0.0.1:1",
        "ALL_PROXY": "http://127.0.0.1:1",
    })
    config = OperatorConfig(
        root=fixture_root,
        runtime_dir=tmp_path / "artifacts" / "runtime",
        db_path=tmp_path / "artifacts" / "state.sqlite3",
        runner_path=runner,
        port=port,
    )
    operator = RemotePilotOperator(
        config,
        env=environment,
        load_env_file=False,
        preflight_runner=lambda _config, _env: {"summary": {"fail": 0}, "checks": []},
    )
    try:
        assert operator.start(app_timeout=12, tunnel_timeout=0.1) == PENDING_TUNNEL_EXIT_CODE
        assert operator._inspect()["state"] == "STARTING"
        assert operator._health_checker(config) is True
        assert not operator.url_path.exists()
        time.sleep(1.6)
        assert operator.status() == 0
        assert operator._inspect()["state"] == "RUNNING"
        assert operator.url() == 0
        assert operator._read_url() == "https://delayed-lifecycle.trycloudflare.com"
    finally:
        assert operator.stop(timeout=8) == 0


def test_unexpected_supervisor_exit_is_not_reported_as_running(tmp_path):
    runner = tmp_path / "exit_runner.sh"
    runner.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    runner.chmod(0o755)
    operator = _operator(tmp_path, runner=runner)
    assert operator.start(timeout=0.3) == 1
    assert operator.status() == 0


def test_url_is_not_valid_after_stop(tmp_path, capsys):
    operator = _operator(tmp_path)
    assert operator.start(timeout=3) == 0
    assert operator.stop(timeout=3) == 0
    assert operator.url() == 1
    assert "没有可确认有效" in capsys.readouterr().err


def test_legacy_cleanup_dry_run_and_confirm_only_exact_matches(tmp_path):
    operator = _operator(tmp_path)
    fake_streamlit = ProcessInfo(
        pid=5001, uid=os.getuid(),
        argv=("python", "-m", "streamlit", "run", "app.py", "--server.address", "127.0.0.1", "--server.port", "8504"),
        cwd=ROOT,
    )
    fake_cloudflared = ProcessInfo(
        pid=5002, uid=os.getuid(),
        argv=("cloudflared", "tunnel", "--url", "http://127.0.0.1:8504", "--no-autoupdate"),
        cwd=ROOT,
    )
    unrelated = ProcessInfo(
        pid=5003, uid=os.getuid(),
        argv=("python", "-m", "streamlit", "run", "other.py", "--server.address", "127.0.0.1", "--server.port", "8504"),
        cwd=ROOT,
    )
    processes = [fake_streamlit, fake_cloudflared, unrelated]
    signals = []
    operator._process_reader = lambda: list(processes)
    operator._signaler = lambda pid, sig: (signals.append((pid, sig)), processes.remove(next(item for item in processes if item.pid == pid)))
    assert operator.cleanup_legacy(port=8504, confirm=False) == 0
    assert signals == []
    assert operator.cleanup_legacy(port=8504, confirm=True) == 0
    assert [pid for pid, _sig in signals] == [5002, 5001]
    assert unrelated in processes


def test_legacy_cleanup_rejects_other_port_and_other_repository(tmp_path):
    operator = _operator(tmp_path)
    other = ProcessInfo(
        pid=5004, uid=os.getuid(),
        argv=("cloudflared", "tunnel", "--url", "http://127.0.0.1:9999", "--no-autoupdate"),
        cwd=ROOT,
    )
    operator._process_reader = lambda: [other]
    assert operator.cleanup_legacy(port=8504, confirm=True) == 0


def test_malformed_pid_and_metadata_are_stale_not_running(tmp_path):
    operator = _operator(tmp_path)
    operator.config.runtime_dir.mkdir(parents=True)
    operator.supervisor_pid_path.write_text("not-a-pid", encoding="ascii")
    operator.metadata_path.write_text("{broken", encoding="utf-8")
    assert operator.status() == 1
    assert operator.stop(timeout=1) == 0


def test_env_parser_does_not_execute_shell_and_does_not_expose_values(tmp_path):
    marker = tmp_path / "must-not-exist"
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "INTROAI_PILOT_ACCESS_CODE='" + TEST_CODE + "'\n"
        + "MALICIOUS=$(touch " + str(marker) + ")\n",
        encoding="utf-8",
    )
    values = load_simple_env(dotenv)
    assert values["INTROAI_PILOT_ACCESS_CODE"] == TEST_CODE
    assert values["MALICIOUS"].startswith("$(touch")
    assert not marker.exists()


def test_cli_argument_error_and_shell_syntax_check():
    result = subprocess.run(
        ["bash", "scripts/remote_pilot_ctl.sh", "unknown"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    syntax = subprocess.run(
        ["bash", "-n", "scripts/remote_pilot_ctl.sh"],
        cwd=ROOT, check=False,
    )
    assert syntax.returncode == 0


def test_every_cli_subcommand_has_config_attributes_and_cleanup_defaults_are_safe(tmp_path):
    parser = remote_control._build_parser()
    for command in ("doctor", "start", "status", "url", "logs", "restart", "stop", "cleanup-legacy"):
        args = parser.parse_args([command])
        config = remote_control._parse_config(args)
        assert config.port == remote_control.DEFAULT_PORT
        assert config.runtime_dir == remote_control.DEFAULT_RUNTIME
        assert config.db_path == remote_control.DEFAULT_DB
    cleanup = parser.parse_args([
        "cleanup-legacy", "--port", "18504", "--runtime-dir", str(tmp_path / "runtime"),
        "--db-path", str(tmp_path / "state.sqlite3"), "--confirm",
    ])
    config = remote_control._parse_config(cleanup)
    assert cleanup.confirm is True
    assert config.port == 18504
    assert config.runtime_dir == (tmp_path / "runtime").resolve()
    assert config.db_path == (tmp_path / "state.sqlite3").resolve()


def test_cleanup_legacy_cli_uses_no_dotenv_and_dry_runs_without_traceback(monkeypatch, capsys):
    created = []

    class FakeOperator:
        def __init__(self, config, *, env, load_env_file):
            created.append((config, dict(env or {}), load_env_file))

        def cleanup_legacy(self, *, port, confirm):
            assert port == remote_control.DEFAULT_PORT
            assert confirm is False
            print("没有发现精确匹配的旧版 Pilot 进程。")
            return 0

    monkeypatch.setattr(remote_control, "RemotePilotOperator", FakeOperator)
    assert remote_control.main(["cleanup-legacy", "--port", "8504"]) == 0
    output = capsys.readouterr().out
    assert "Traceback" not in output
    assert created[0][1] == {}
    assert created[0][2] is False


def test_cleanup_legacy_cli_confirm_parses_and_internal_errors_are_safe(monkeypatch, capsys):
    class ExplodingOperator:
        def __init__(self, *_args, **_kwargs):
            raise AttributeError("synthetic internal failure")

    monkeypatch.setattr(remote_control, "RemotePilotOperator", ExplodingOperator)
    assert remote_control.main(["cleanup-legacy", "--confirm"]) == 1
    error = capsys.readouterr().err
    assert "Traceback" not in error
    assert "控制器内部错误" in error
    assert TEST_CODE not in error


def test_metadata_contains_no_secret_or_learner_data(tmp_path):
    operator = _operator(tmp_path)
    assert operator.start(timeout=3) == 0
    text = operator.metadata_path.read_text(encoding="utf-8")
    assert TEST_CODE not in text
    assert "learner" not in text.casefold()
    assert operator.stop(timeout=3) == 0
