from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import dotenv_values
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_NAME: str = "RepoPilot"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://repopilot:change_me@localhost:5432/repopilot"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10

    # GitHub
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_API_BASE: str = "https://api.github.com"
    GITHUB_REQUEST_TIMEOUT_S: float = 30.0

    # LLM & Embeddings
    LLM_PROVIDER: str = "anthropic"  # anthropic | openai | gemini
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "claude-3-5-sonnet-20241022"
    LLM_MAX_OUTPUT_TOKENS: int = 2000
    LLM_TEMPERATURE: float = 0.2
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    # Feature Flags
    FEATURE_SEMANTIC_SEARCH: bool = True
    FEATURE_AI_ARCH_SUMMARY: bool = True

    # Limits
    MAX_REPO_SIZE_MB: int = 150
    MAX_FILES: int = 5000
    MAX_FILE_BYTES: int = 300000
    MAX_CHUNKS_PER_REPO: int = 20000
    ANALYSIS_TIMEOUT_S: int = 300
    EVIDENCE_TOKEN_BUDGET: int = 12000

    # Storage & Retention
    SNAPSHOT_DIR: str = "./.data/snapshots"
    SNAPSHOT_TTL_HOURS: int = 24
    DATA_RETENTION_HOURS: int = 72

    # Rate Limiting
    RATE_LIMIT_ANALYSE: str = "5/hour"
    RATE_LIMIT_LLM: str = "30/hour"
    RATE_LIMIT_DEFAULT: str = "120/minute"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL.")
        raw_url = value.strip().strip("\"'").strip()
        try:
            parts = urlsplit(raw_url)
            scheme = parts.scheme.lower()
            if scheme in {
                "postgres",
                "postgresql",
                "postgresql+psycopg",
                "postgresql+psycopg2",
            }:
                scheme = "postgresql+asyncpg"
            elif scheme != "postgresql+asyncpg":
                raise ValueError
            if not parts.hostname or not parts.path.strip("/"):
                raise ValueError
            parts.port
            query = [
                (
                    "ssl" if key.lower() == "sslmode" and val.lower() == "require" else key,
                    val,
                )
                for key, val in parse_qsl(parts.query, keep_blank_values=True)
                if key.lower() != "channel_binding"
            ]
            return urlunsplit(
                (scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
            )
        except ValueError as exc:
            raise ValueError(
                "DATABASE_URL must use a supported PostgreSQL URL scheme."
            ) from exc


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def _read_env_file(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    return {
        key: value
        for key, value in dotenv_values(path, encoding="utf-8-sig").items()
        if value is not None
    }


def database_url_shape(url: str) -> Dict[str, Any]:
    parts = urlsplit(url)
    return {
        "driver": parts.scheme,
        "host": parts.hostname or "unknown",
        "port": parts.port or (5432 if parts.scheme.startswith("postgresql") else None),
        "database": parts.path.lstrip("/").split("/", 1)[0] or "unknown",
    }


def database_url_overridden() -> bool:
    os_value = os.environ.get("DATABASE_URL")
    file_value = _read_env_file(BASE_DIR / ".env").get("DATABASE_URL")
    if not os_value or not file_value:
        return False
    try:
        return (
            Settings.normalize_database_url(os_value)
            != Settings.normalize_database_url(file_value)
        )
    except ValueError:
        return True


def settings_diagnostics() -> Dict[str, Dict[str, str]]:
    file_values = _read_env_file(BASE_DIR / ".env")
    diagnostics: Dict[str, Dict[str, str]] = {}
    for name, field in Settings.model_fields.items():
        if name in os.environ:
            source = "OS environment"
            present = bool(os.environ[name].strip())
        elif name in file_values:
            source = ".env file"
            present = bool(file_values[name])
        else:
            source = "default"
            present = field.default is not None
        if source == "default":
            state = "default"
        else:
            state = "set" if present else "not set"
        diagnostics[name] = {"status": state, "source": source, "value": "****"}
    return diagnostics
