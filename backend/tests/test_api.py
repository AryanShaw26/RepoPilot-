from unittest.mock import AsyncMock, Mock
import uuid
import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.errors import AppError
from app.core.config import settings
from app.api.v1 import investigations as investigations_api
from app.main import app
from app.db.session import get_db
from app.services.embeddings import EmbeddingService, FeatureDisabled
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService


async def override_get_db():
    mock_session = AsyncMock()
    mock_session.add = Mock()
    mock_session.execute.return_value = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    yield mock_session


app.state.testing = True
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app, raise_server_exceptions=False)


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["ok", "degraded"]
    assert data["db"] is False
    assert data["migrated"] is False
    assert "llm_configured" in data
    assert "github_token_configured" in data
    assert "version" in data


def test_health_is_degraded_when_schema_is_not_migrated(monkeypatch):
    monkeypatch.setattr(app.state, "db", True, raising=False)
    monkeypatch.setattr(app.state, "migrated", False, raising=False)
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "degraded"
    assert res.json()["db"] is True
    assert res.json()["migrated"] is False


def test_capabilities_report_unsupported_llm_provider_as_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "configured-test-key")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")

    res = client.get("/api/v1/meta/capabilities")

    assert res.status_code == 200
    assert res.json()["llm_available"] is False
    assert res.json()["llm_provider"] == "gemini"


def test_database_unavailable_error_envelope(monkeypatch):
    async def unavailable_db():
        raise AppError(
            code="DATABASE_UNAVAILABLE",
            message="Database unavailable.",
            status_code=503,
        )
        yield

    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = unavailable_db
    try:
        res = client.post(
            "/api/v1/repositories",
            json={"url": "https://github.com/owner/repo"},
        )
    finally:
        app.dependency_overrides[get_db] = original

    assert res.status_code == 503
    assert res.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_cors_preflight_allows_frontend_session_header():
    res = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type,x-session-id",
        },
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
    allowed_headers = res.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed_headers
    assert "x-session-id" in allowed_headers


def test_cors_exposes_session_header_to_frontend():
    res = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert res.status_code == 200
    assert res.headers["access-control-expose-headers"].lower() == "x-session-id"


def test_rate_limit_returns_standard_error_envelope():
    original_limiter = app.state.limiter
    app.state.limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["1/minute"],
    )
    try:
        assert client.get("/api/v1/meta/capabilities").status_code == 200
        res = client.get("/api/v1/meta/capabilities")
    finally:
        app.state.limiter = original_limiter

    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_investigation_worker_uses_an_independent_database_session(monkeypatch):
    worker_session = AsyncMock()
    worker_session.__aenter__.return_value = worker_session
    worker_session.__aexit__.return_value = None
    run_investigation = AsyncMock()
    monkeypatch.setattr(
        investigations_api, "get_worker_session", lambda: worker_session
    )
    monkeypatch.setattr(
        investigations_api.InvestigateService,
        "run_investigation",
        run_investigation,
    )
    investigation_id = uuid.uuid4()

    await investigations_api._run_investigation_background(
        investigation_id,
        "snapshot",
    )

    run_investigation.assert_awaited_once_with(
        db=worker_session,
        investigation_id=investigation_id,
        snapshot_dir="snapshot",
    )


@pytest.mark.asyncio
async def test_semantic_storage_requires_pgvector_and_embedding_column(monkeypatch):
    monkeypatch.setattr(settings, "FEATURE_SEMANTIC_SEARCH", True)
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", "test-key")
    db = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = False
    db.execute.return_value = result

    assert await RetrievalService.semantic_storage_available(db) is False
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_embedding_provider_errors_do_not_log_response_body(monkeypatch, caplog):
    class Response:
        status_code = 401
        text = "provider response contains sensitive data"

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return Response()

    service = EmbeddingService()
    service.settings = SimpleNamespace(
        FEATURE_SEMANTIC_SEARCH=True,
        EMBEDDING_API_KEY="test-key",
        EMBEDDING_MODEL="test-model",
    )
    monkeypatch.setattr(
        "app.services.embeddings.httpx.AsyncClient",
        lambda **_kwargs: Client(),
    )
    monkeypatch.setattr(
        "app.services.embeddings.asyncio.sleep",
        AsyncMock(),
    )

    with pytest.raises(FeatureDisabled):
        await service.embed_texts(["sample"])

    assert "sensitive data" not in caplog.text


@pytest.mark.asyncio
async def test_llm_provider_errors_do_not_expose_response_body(monkeypatch):
    class Response:
        status_code = 401
        text = "provider response contains sensitive data"

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return Response()

    service = LLMService()
    service.settings = SimpleNamespace(
        LLM_PROVIDER="openai",
        LLM_API_KEY="test-key",
        LLM_MODEL="test-model",
        LLM_MAX_OUTPUT_TOKENS=100,
        LLM_TEMPERATURE=0,
    )
    monkeypatch.setattr(
        "app.services.llm.httpx.AsyncClient",
        lambda **_kwargs: Client(),
    )

    with pytest.raises(AppError) as error:
        await service._call_provider("system", "user")

    assert "sensitive data" not in error.value.message


@pytest.mark.asyncio
async def test_unsupported_llm_provider_returns_unavailable_without_network_call():
    service = LLMService()
    service.settings = SimpleNamespace(LLM_PROVIDER="gemini", LLM_API_KEY="test-key")

    with pytest.raises(AppError) as error:
        await service._call_provider("system", "user")

    assert error.value.code == "LLM_UNAVAILABLE"
    assert error.value.status_code == 503


def test_invalid_github_url_rejection():
    res = client.post("/api/v1/repositories", json={"url": "https://malicious.com/owner/repo"})
    assert res.status_code == 400
    data = res.json()
    assert data["error"]["code"] == "INVALID_ARGUMENT"
