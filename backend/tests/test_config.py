from urllib.parse import parse_qs, urlsplit

import pytest
import asyncpg
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.errors import AppError
import app.db.session as db_session


@pytest.mark.parametrize(
    "url",
    [
        "postgres://user:pass@localhost:5432/repopilot",
        "postgresql://user:pass@localhost:5432/repopilot",
        "postgresql+psycopg://user:pass@localhost:5432/repopilot",
        "postgresql+psycopg2://user:pass@localhost:5432/repopilot",
        "'postgresql+asyncpg://user:pass@localhost:5432/repopilot'",
        '"postgresql+asyncpg://user:pass@localhost:5432/repopilot"',
    ],
)
def test_database_url_schemes_normalize_to_asyncpg(url):
    settings = Settings(DATABASE_URL=url)
    assert urlsplit(settings.DATABASE_URL).scheme == "postgresql+asyncpg"


def test_database_url_translates_sslmode_and_drops_channel_binding():
    settings = Settings(
        DATABASE_URL=(
            "postgresql://user:pass@localhost/repopilot"
            "?sslmode=require&channel_binding=require&application_name=RepoPilot"
        )
    )
    query = parse_qs(urlsplit(settings.DATABASE_URL).query)
    assert query["ssl"] == ["require"]
    assert "sslmode" not in query
    assert "channel_binding" not in query
    assert query["application_name"] == ["RepoPilot"]


def test_database_url_rejects_non_postgresql_schemes():
    with pytest.raises(ValidationError, match="supported PostgreSQL URL scheme"):
        Settings(DATABASE_URL="sqlite:///repopilot.db")


def test_settings_env_file_reads_utf8_bom_and_crlf(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_NAME", raising=False)
    env_file = tmp_path / "windows.env"
    env_file.write_bytes(
        b"\xef\xbb\xbfAPP_NAME=WindowsConfig\r\nAPP_ENV=testing\r\n"
    )
    settings = Settings(_env_file=env_file)
    assert settings.APP_NAME == "WindowsConfig"
    assert settings.APP_ENV == "testing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyError, OSError, TimeoutError, asyncpg.exceptions.InvalidPasswordError],
)
async def test_database_dependency_translates_connection_failures(monkeypatch, error_type):
    class FailedSession:
        def __init__(self):
            self.error_type = error_type

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def execute(self, statement):
            raise self.error_type("database down")

        async def rollback(self):
            return None

        async def close(self):
            return None

    monkeypatch.setattr(
        db_session, "AsyncSessionLocal", lambda: FailedSession()
    )
    with pytest.raises(AppError) as error:
        async for _ in db_session.get_db():
            pytest.fail("A failed database check must not yield a session.")

    assert error.value.code == "DATABASE_UNAVAILABLE"
    assert error.value.status_code == 503
