"""Tests for Gmail tools, token encryption, and recipient resolution."""

import json
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from agent.tools.email import _read_emails, _send_email, resolve_recipient
from auth.token_store import decrypt, encrypt


@pytest.fixture
def fernet_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", key)
    from auth import token_store

    token_store._fernet.cache_clear()
    return key


def test_encrypt_decrypt_roundtrip(fernet_key):
    assert decrypt(encrypt("secret-token")) == "secret-token"


@pytest.mark.parametrize(
    "requested,expected",
    [
        ("me", "user@gmail.com"),
        ("your_email@example.com", "user@gmail.com"),
        ("friend@real.com", "friend@real.com"),
        ("", "user@gmail.com"),
    ],
)
def test_resolve_recipient(requested, expected):
    assert resolve_recipient(requested, "user@gmail.com") == expected


def test_read_emails_returns_metadata(auth_env):
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg-1"}]
    }
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "msg-1",
        "snippet": "Hello there",
        "payload": {"headers": [{"name": "From", "value": "a@b.com"}, {"name": "Subject", "value": "Hi"}]},
    }

    with patch("agent.tools.email._get_gmail_service") as mock_get:
        mock_get.return_value = mock_service
        out = _read_emails(max_results=3, query="is:inbox")

    data = json.loads(out)
    assert data["count"] == 1
    assert data["emails"][0]["subject"] == "Hi"


def test_send_email_returns_message_id(auth_env, monkeypatch):
    monkeypatch.setenv("USER_EMAIL", "real@gmail.com")
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "sent-99"}

    with patch("agent.tools.email._get_gmail_service") as mock_get:
        mock_get.return_value = mock_service
        out = _send_email(to="real@gmail.com", subject="Test", body="Body text")

    data = json.loads(out)
    assert data["status"] == "sent"
    assert data["to"] == "real@gmail.com"
    assert data["message_id"] == "sent-99"


def test_send_email_replaces_placeholder(auth_env, monkeypatch):
    monkeypatch.setenv("USER_EMAIL", "real@gmail.com")
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "sent-100"}

    with patch("agent.tools.email._get_gmail_service") as mock_get:
        mock_get.return_value = mock_service
        out = _send_email(to="your_email@example.com", subject="", body="Summary here")

    data = json.loads(out)
    assert data["to"] == "real@gmail.com"
    assert data["subject"] == "Message from your AI agent"
    assert data["requested_to"] == "your_email@example.com"
