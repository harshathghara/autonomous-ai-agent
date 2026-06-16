"""Tests for production startup helpers."""

from unittest.mock import patch

from api.startup import auto_migrate_enabled, validate_env


def test_validate_env_reports_missing(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    missing = validate_env()
    assert "GROQ_API_KEY" in missing


def test_auto_migrate_enabled_defaults_true(monkeypatch):
    monkeypatch.delenv("AUTO_MIGRATE", raising=False)
    assert auto_migrate_enabled() is True


def test_auto_migrate_can_be_disabled(monkeypatch):
    monkeypatch.setenv("AUTO_MIGRATE", "false")
    assert auto_migrate_enabled() is False
