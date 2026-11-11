"""Configuration management for Pronote MCP Server."""

import os
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class PronoteSettings(BaseSettings):
    """Pydantic Settings for Pronote authentication and runtime parameters."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH) if _ENV_PATH.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Pronote instance URL
    url: str = Field(
        ...,
        validation_alias="PRONOTE_URL",
        description="Full URL to Pronote web space (eleve.html or parent.html)",
    )

    # Standard authentication
    username: Optional[str] = Field(
        default=None,
        validation_alias="PRONOTE_USERNAME",
        description="Username / identifier for Pronote or ENT",
    )
    password: Optional[SecretStr] = Field(
        default=None,
        validation_alias="PRONOTE_PASSWORD",
        description="Password for Pronote or ENT",
    )

    # ENT provider
    ent: Optional[str] = Field(
        default=None,
        validation_alias="PRONOTE_ENT",
        description="Name of the ENT provider (e.g. ile_de_france, monbureaunumerique)",
    )

    # QR Code / Token authentication
    token: Optional[SecretStr] = Field(
        default=None,
        validation_alias="PRONOTE_TOKEN",
        description="64-character token exported from Pronote mobile QR code",
    )
    uuid: Optional[str] = Field(
        default=None,
        validation_alias="PRONOTE_UUID",
        description="Client UUID for token authentication",
    )

    # Account context
    account_type: Literal["student", "parent"] = Field(
        default="student",
        validation_alias="PRONOTE_ACCOUNT_TYPE",
        description="Account type: 'student' or 'parent'",
    )
    child_name: Optional[str] = Field(
        default=None,
        validation_alias="PRONOTE_CHILD_NAME",
        description="Default child name to target for parent accounts",
    )

    # 2FA PIN / Device verification
    account_pin: Optional[SecretStr] = Field(
        default=None,
        validation_alias="PRONOTE_ACCOUNT_PIN",
        description="4-digit PIN code for new device authentication",
    )
    device_name: Optional[str] = Field(
        default="MCP GEMINI",
        validation_alias="PRONOTE_DEVICE_NAME",
        description="Name of the registered device in Pronote",
    )
    session_file: Optional[str] = Field(
        default=".session_cache.pkl",
        validation_alias="PRONOTE_SESSION_FILE",
        description="Path to cache file for persisting active Pronote session across runs",
    )

    # Runtime options
    cache_ttl: int = Field(
        default=180,
        validation_alias="PRONOTE_CACHE_TTL",
        description="In-memory cache time-to-live in seconds",
    )
    timeout: int = Field(
        default=30,
        validation_alias="PRONOTE_TIMEOUT",
        description="Pronote request timeout in seconds",
    )

    @property
    def is_token_auth(self) -> bool:
        """Check if token-based authentication is enabled."""
        return bool(self.token)

    @property
    def is_password_auth(self) -> bool:
        """Check if username/password authentication is enabled."""
        return bool(self.username and self.password)

    @model_validator(mode="after")
    def validate_credentials(self) -> "PronoteSettings":
        """Ensure either direct credentials or token credentials are provided."""
        has_direct = bool(self.username and self.password)
        has_token = bool(self.token)

        if not has_direct and not has_token:
            raise ValueError(
                "Missing Pronote credentials. You must provide either "
                "(PRONOTE_USERNAME and PRONOTE_PASSWORD) or (PRONOTE_TOKEN)."
            )
        return self
