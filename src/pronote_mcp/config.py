"""Configuration management for Pronote MCP Server."""

import os
from pathlib import Path
from typing import Dict, Literal, Optional
from pydantic import Field, SecretStr, ValidationError, model_validator
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
    download_dir: str = Field(
        default="./downloads",
        validation_alias="PRONOTE_DOWNLOAD_DIR",
        description="Directory where downloaded attachments and exports are saved",
    )

    @property
    def resolved_download_dir(self) -> Path:
        """Return the resolved download directory path, creating it if needed."""
        path = Path(self.download_dir).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

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


def load_settings_or_none(env_path: Optional[Path] = None) -> Optional[PronoteSettings]:
    """Load PronoteSettings if valid credentials exist, otherwise return None."""
    target_env = env_path or _ENV_PATH
    try:
        env_arg = str(target_env) if target_env.exists() else None
        return PronoteSettings(_env_file=env_arg)
    except ValidationError:
        return None


def _sanitize_env_value(value: str) -> str:
    """Strip newlines from .env values to prevent line injection."""
    return value.replace("\r", "").replace("\n", "").strip()


def save_env_config(values: Dict[str, str], env_path: Optional[Path] = None) -> Path:
    """Write or update Pronote keys in the local .env file securely."""
    target_env = env_path or _ENV_PATH
    existing_lines: list[str] = []
    if target_env.exists():
        existing_lines = target_env.read_text(encoding="utf-8").splitlines()

    clean_values = {k: _sanitize_env_value(v) for k, v in values.items() if k}
    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in clean_values:
            new_lines.append(f"{key}={clean_values[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)

    for key, val in clean_values.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    target_env.parent.mkdir(parents=True, exist_ok=True)
    target_env.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    try:
        os.chmod(target_env, 0o600)
    except OSError:
        pass
    return target_env
