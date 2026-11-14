"""Unit tests for PronoteSettings configuration."""

import pytest
from pydantic import ValidationError
from edu_mcp.config import PronoteSettings


def test_config_valid_password():
    settings = PronoteSettings(
        _env_file=None,
        url="https://demo.pronote.fr/eleve.html",
        username="user1",
        password="pwd",
    )
    assert settings.url == "https://demo.pronote.fr/eleve.html"
    assert settings.username == "user1"
    assert settings.is_password_auth is True
    assert settings.is_token_auth is False


def test_config_valid_token():
    settings = PronoteSettings(
        _env_file=None,
        url="https://demo.pronote.fr/eleve.html",
        username="user1",
        token="some_token_secret",
    )
    assert settings.is_token_auth is True
    assert settings.is_password_auth is False


def test_config_missing_auth():
    with pytest.raises(ValidationError):
        PronoteSettings(_env_file=None, url="https://demo.pronote.fr/eleve.html")
