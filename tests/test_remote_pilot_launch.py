import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_remote_pilot.sh"
TEST_CODE = "remote-launch-test-code"


def _fake_cloudflared(tmp_path):
    directory = tmp_path / "bin"
    directory.mkdir(exist_ok=True)
    binary = directory / "cloudflared"
    binary.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    return directory


def _environment(tmp_path, *, include_cloudflared=True):
    environment = os.environ.copy()
    environment.pop("DEEPSEEK_API_KEY", None)
    environment.pop("INTROAI_PILOT_MODE", None)
    environment.pop("INTROAI_PILOT_ACCESS_CODE", None)
    environment["HOME"] = str(tmp_path / "home")
    environment["INTROAI_PILOT_ACCESS_CODE"] = TEST_CODE
    if include_cloudflared:
        fake_bin = _fake_cloudflared(tmp_path)
        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    else:
        empty_bin = tmp_path / "empty-bin"
        empty_bin.mkdir(exist_ok=True)
        # Keep only synthetic interpreter shims while excluding every host
        # directory that may contain cloudflared; this test is deterministic.
        (empty_bin / "bash").symlink_to("/usr/bin/bash")
        python = Path(os.environ.get("PYTHON", "")) if os.environ.get("PYTHON") else Path(shutil.which("python") or "/usr/bin/python3")
        (empty_bin / "python").symlink_to(python)
        environment["PATH"] = str(empty_bin)
    return environment


def test_remote_launcher_is_loopback_only_and_has_owned_child_cleanup():
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'port="8504"' in script
    assert 'INTROAI_PILOT_HOST=127.0.0.1' in script
    assert 'run_internal_pilot.sh --host 127.0.0.1' in script
    assert ' --headless >"$streamlit_log"' in script
    assert "--managed-by-controller" in script
    assert 'cloudflared tunnel --url "http://127.0.0.1:${port}" --no-autoupdate' in script
    assert "command -v cloudflared" in script
    assert "kill \"$app_pid\"" in script
    assert "trap cleanup EXIT" in script
    assert "trap on_signal INT TERM" in script
    assert "wait_for_local_ready" in script
    assert "_stcore/health" in script
    assert "ProxyHandler({})" in script
    assert "if ! wait_for_local_ready" in script
    assert '>>"$tunnel_log" 2>&1' in script
    assert "--no-autoupdate" in script
    assert "pkill" not in script
    assert "killall" not in script
    assert "fuser" not in script
    assert "sudo" not in script
    assert "eval" not in script
    assert "INTROAI_PILOT_ACCESS_CODE" not in script


def test_managed_launcher_does_not_run_its_legacy_health_cleanup_watchdog(tmp_path):
    root = tmp_path / "fixture-root"
    scripts = root / "scripts"
    tools = root / "tools"
    scripts.mkdir(parents=True)
    tools.mkdir()
    launcher = scripts / "run_remote_pilot.sh"
    launcher.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    launcher.chmod(0o755)
    (scripts / "run_internal_pilot.sh").write_text(
        "#!/usr/bin/env bash\ntrap 'exit 0' TERM INT\nwhile :; do sleep 0.1; done\n",
        encoding="utf-8",
    )
    (scripts / "run_internal_pilot.sh").chmod(0o755)
    (tools / "pilot_preflight.py").write_text("print('synthetic preflight')\n", encoding="utf-8")
    fake_bin = root / "bin"
    fake_bin.mkdir()
    (fake_bin / "cloudflared").write_text(
        "#!/usr/bin/env bash\ntrap 'exit 0' TERM INT\nwhile :; do sleep 0.1; done\n",
        encoding="utf-8",
    )
    (fake_bin / "cloudflared").chmod(0o755)
    runtime = root / "runtime"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    process = subprocess.Popen(
        [
            str(launcher), "--managed-by-controller", "--port", "18504",
            "--db-path", str(root / "state.sqlite3"), "--runtime-dir", str(runtime),
        ],
        cwd=root,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        import time
        time.sleep(0.35)
        assert process.poll() is None
        assert (runtime / "cloudflared.log").exists()
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_remote_launcher_documents_fail_closed_readiness_and_runtime_permissions():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "umask 077" in script
    assert 'chmod 700 "$runtime_dir"' in script
    assert "本地 Streamlit 未在限定时间内就绪" in script
    assert "未启动 Streamlit 或隧道" in script
    assert "cloudflared 日志" in script


def test_remote_launcher_help_and_dry_run_do_not_start_children_or_create_runtime(tmp_path):
    help_result = subprocess.run(
        [str(SCRIPT), "--help"],
        cwd=ROOT,
        env=_environment(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "--dry-run" in help_result.stderr

    runtime = tmp_path / "runtime"
    database = tmp_path / "state.sqlite3"
    result = subprocess.run(
        [
            str(SCRIPT),
            "--dry-run",
            "--port",
            "18504",
            "--db-path",
            str(database),
            "--runtime-dir",
            str(runtime),
        ],
        cwd=ROOT,
        env=_environment(tmp_path),
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Dry run" in output
    assert "127.0.0.1:18504" in output
    assert TEST_CODE not in output
    assert not runtime.exists()
    assert not database.exists()


def test_missing_cloudflared_fails_before_runtime_or_app_start(tmp_path):
    runtime = tmp_path / "runtime"
    result = subprocess.run(
        [str(SCRIPT), "--dry-run", "--runtime-dir", str(runtime)],
        cwd=ROOT,
        env=_environment(tmp_path, include_cloudflared=False),
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "cloudflared" in output
    assert TEST_CODE not in output
    assert not runtime.exists()
