"""Keep Streamlit persistence tests away from a developer's real home directory."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_learner_state_database(tmp_path, monkeypatch):
    monkeypatch.setenv("INTROAI_STATE_DB", str(tmp_path / "learner_state.sqlite3"))
