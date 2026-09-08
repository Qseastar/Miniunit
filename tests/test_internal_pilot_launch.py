from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_launch_script_is_fail_closed_and_does_not_kill_unknown_processes():
    script = (ROOT / "scripts" / "run_internal_pilot.sh").read_text(encoding="utf-8")
    assert "INTROAI_PILOT_MODE=1" in script
    assert "INTROAI_PILOT_HOST" in script
    assert 'PYTHONPATH="src' in script
    assert "tools/pilot_preflight.py" in script
    assert "--strict" in script
    assert "--server.fileWatcherType none" in script
    assert "--headless" in script
    assert "--server.headless true" in script
    assert "streamlit_args=(python -m streamlit run app.py" in script
    assert 'exec "${streamlit_args[@]}"' in script
    assert "--server.address \"$host\"" in script
    assert "kill " not in script
    assert "source .env" not in script
    assert "Authorization" not in script


def test_launch_script_supports_port_and_database_overrides_without_printing_configuration():
    script = (ROOT / "scripts" / "run_internal_pilot.sh").read_text(encoding="utf-8")
    assert "--port" in script and "--db-path" in script
    assert "INTROAI_STATE_DB" in script
    assert "API Key" not in script
    assert "--host" in script
    assert "INTROAI_PILOT_ACCESS_CODE" in script
    assert all(
        "INTROAI_PILOT_ACCESS_CODE" not in line
        for line in script.splitlines()
        if "printf" in line
    )


def test_launch_script_preserves_controller_injected_access_code_over_dotenv_value():
    script = (ROOT / "scripts" / "run_internal_pilot.sh").read_text(encoding="utf-8")
    assert '"$key" == "INTROAI_PILOT_ACCESS_CODE"' in script
    assert "-v INTROAI_PILOT_ACCESS_CODE" in script
