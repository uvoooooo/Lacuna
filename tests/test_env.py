"""Tests for .env loading."""

import os

from narrative_audit.env import load_dotenv


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-shell")

    load_dotenv()

    assert os.environ["OPENROUTER_API_KEY"] == "from-shell"


def test_load_dotenv_sets_missing_keys(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('OPENROUTER_API_KEY="from-file"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    path = load_dotenv()

    assert path == env_file
    assert os.environ["OPENROUTER_API_KEY"] == "from-file"
