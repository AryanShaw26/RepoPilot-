from unittest.mock import AsyncMock, Mock
import uuid
import pytest
from types import SimpleNamespace
import json
import tarfile
from io import BytesIO
from pathlib import Path
import respx
import httpx
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
from app.services.ingest import safe_extract_tarball, scan_repository_files
from app.services.planner import render_plan_markdown
from app.services.secrets import should_exclude_path
from app.services.github import GitHubService
from app.services.search import search_ripgrep


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


def test_capabilities_report_gemini_llm_as_available(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "configured-test-key")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")

    res = client.get("/api/v1/meta/capabilities")

    assert res.status_code == 200
    assert res.json()["llm_available"] is True
    assert res.json()["llm_provider"] == "gemini"
    assert res.json()["llm_unavailable_reason"] is None


def test_unsupported_llm_provider_has_capability_reason(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "configured-test-key")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "custom-provider")
    response = client.get("/api/v1/meta/capabilities")
    assert response.json()["llm_available"] is False
    assert response.json()["llm_unavailable_reason"] == "Unsupported LLM provider: custom-provider"


def test_unsupported_embedding_provider_disables_semantic_capability(monkeypatch):
    monkeypatch.setattr(settings, "FEATURE_SEMANTIC_SEARCH", True)
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", "configured-test-key")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "custom-provider")
    monkeypatch.setattr(app.state, "semantic_enabled", True, raising=False)
    response = client.get("/api/v1/meta/capabilities")
    assert response.json()["semantic_search"] is False


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
async def test_unsupported_llm_provider_logs_once_and_never_calls_network(monkeypatch, caplog):
    service = LLMService()
    service.settings = SimpleNamespace(LLM_PROVIDER="unsupported-test-provider", LLM_API_KEY="test-key")

    def network_is_forbidden(**_kwargs):
        raise AssertionError("unsupported providers must not make network calls")

    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", network_is_forbidden)

    with pytest.raises(AppError) as error:
        await service._call_provider("system", "user")

    assert error.value.code == "LLM_UNAVAILABLE"
    assert error.value.status_code == 503
    assert caplog.text.count("Unsupported LLM provider configured") == 1


@pytest.mark.asyncio
@respx.mock
async def test_gemini_llm_json_response_and_schema_validation(monkeypatch):
    class Output(__import__("pydantic").BaseModel):
        value: str

    route = respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent").mock(
        return_value=httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"value":"ok"}'}]}}]})
    )
    service = LLMService()
    service.settings = SimpleNamespace(LLM_PROVIDER="gemini", LLM_API_KEY="mock-key", LLM_MODEL="gemini-test", LLM_MAX_OUTPUT_TOKENS=40, LLM_TEMPERATURE=0)
    result = await service.complete_json("system", "user", Output)
    assert result.value == "ok"
    assert route.call_count == 1
    payload = json.loads(route.calls[0].request.content)
    assert payload["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.asyncio
@respx.mock
async def test_gemini_json_parse_failure_uses_exactly_one_repair_call():
    class Output(__import__("pydantic").BaseModel):
        value: str

    route = respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent").mock(
        side_effect=[
            httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}),
            httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"value":"repaired"}'}]}}]}),
        ]
    )
    service = LLMService()
    service.settings = SimpleNamespace(LLM_PROVIDER="gemini", LLM_API_KEY="mock-key", LLM_MODEL="gemini-test", LLM_MAX_OUTPUT_TOKENS=40, LLM_TEMPERATURE=0)
    result = await service.complete_json("system", "user", Output)
    assert result.value == "repaired"
    assert route.call_count == 2
    assert "previous response was not valid JSON" in json.loads(route.calls[1].request.content)["contents"][0]["parts"][0]["text"]


@pytest.mark.asyncio
@respx.mock
async def test_gemini_never_retries_permanent_http_errors():
    route = respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent").mock(return_value=httpx.Response(403))
    service = LLMService()
    service.settings = SimpleNamespace(LLM_PROVIDER="gemini", LLM_API_KEY="mock-key", LLM_MODEL="gemini-test", LLM_MAX_OUTPUT_TOKENS=40, LLM_TEMPERATURE=0)
    with pytest.raises(AppError):
        await service._call_provider("system", "user")
    assert route.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,url,body",
    [
        ("openai", "https://api.openai.com/v1/chat/completions", {"choices": [{"message": {"content": '{"ok":true}'}}]}),
        ("anthropic", "https://api.anthropic.com/v1/messages", {"content": [{"text": '{"ok":true}'}]}),
    ],
)
@respx.mock
async def test_existing_llm_providers_still_parse_responses(provider, url, body):
    route = respx.post(url).mock(return_value=httpx.Response(200, json=body))
    service = LLMService()
    service.settings = SimpleNamespace(LLM_PROVIDER=provider, LLM_API_KEY="mock-key", LLM_MODEL="test", LLM_MAX_OUTPUT_TOKENS=50, LLM_TEMPERATURE=0)
    assert await service._call_provider("system", "user") == '{"ok":true}'
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_gemini_embedding_requests_configured_dimension():
    route = respx.post("https://generativelanguage.googleapis.com/v1beta/models/text-embedding-test:batchEmbedContents").mock(
        return_value=httpx.Response(200, json={"embeddings": [{"values": [0.1, 0.2]}]})
    )
    service = EmbeddingService()
    service.settings = SimpleNamespace(FEATURE_SEMANTIC_SEARCH=True, EMBEDDING_API_KEY="mock-key", EMBEDDING_PROVIDER="gemini", EMBEDDING_MODEL="text-embedding-test", EMBEDDING_DIM=2)
    assert await service.embed_texts(["sample"]) == [[0.1, 0.2]]
    assert json.loads(route.calls[0].request.content)["requests"][0]["outputDimensionality"] == 2
    assert route.calls[0].request.headers["x-goog-api-key"] == "mock-key"


@pytest.mark.asyncio
@respx.mock
async def test_embedding_never_retries_permanent_http_errors():
    route = respx.post("https://api.openai.com/v1/embeddings").mock(return_value=httpx.Response(401))
    service = EmbeddingService()
    service.settings = SimpleNamespace(FEATURE_SEMANTIC_SEARCH=True, EMBEDDING_API_KEY="mock-key", EMBEDDING_PROVIDER="openai", EMBEDDING_MODEL="test")
    with pytest.raises(FeatureDisabled):
        await service.embed_texts(["sample"])
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_llm_retries_only_transient_statuses(monkeypatch):
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=[httpx.Response(503), httpx.Response(429), httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})]
    )
    monkeypatch.setattr("app.services.llm.asyncio.sleep", AsyncMock())
    service = LLMService()
    service.settings = SimpleNamespace(LLM_PROVIDER="openai", LLM_API_KEY="mock-key", LLM_MODEL="test", LLM_MAX_OUTPUT_TOKENS=10, LLM_TEMPERATURE=0)
    assert await service._call_provider("system", "user") == "{}"
    assert route.call_count == 3


@pytest.mark.asyncio
async def test_hybrid_search_does_not_embed_when_pgvector_disabled(monkeypatch):
    monkeypatch.setattr(RetrievalService, "semantic_storage_available", AsyncMock(return_value=False))
    monkeypatch.setattr("app.services.retrieval.search_database_keyword", AsyncMock(return_value=[]))
    monkeypatch.setattr("app.services.retrieval.search_symbols", AsyncMock(return_value=[]))
    embed = AsyncMock(side_effect=AssertionError("embedding must not be called"))
    monkeypatch.setattr(EmbeddingService, "embed_query", embed)
    await RetrievalService.hybrid_search(AsyncMock(), uuid.uuid4(), "investigation question")
    embed.assert_not_awaited()


@pytest.mark.asyncio
@respx.mock
async def test_secret_filter_end_to_end_with_mocked_github_tarball(tmp_path, caplog):
    secrets = ["FAKE_GHP_123456789012345678901234567890123456", "PRIVATE_KEY_MATERIAL_XYZ"]
    archive_buffer = BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        entries = {
            "fixture/.env": "API_KEY='DOTENV_SECRET_VALUE_123456789'",
            "fixture/cert.pem": "-----BEGIN PRIVATE KEY-----\nPRIVATE_KEY_MATERIAL_XYZ\n",
            "fixture/config.py": "token = 'FAKE_GHP_123456789012345678901234567890123456'\ndef safe(): return 1\n",
            "fixture/app.py": "def clean(): return 'clean'\n",
        }
        for name, text_value in entries.items():
            raw = text_value.encode()
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, BytesIO(raw))
    archive_buffer.seek(0)
    respx.get("https://api.github.com/repos/owner/repo/tarball/main").mock(
        return_value=httpx.Response(200, content=archive_buffer.read(), headers={"content-type": "application/gzip"})
    )
    service = GitHubService()
    tar_path = tmp_path / "fixture.tar.gz"
    await service.download_tarball("owner", "repo", "main", str(tar_path))
    await service.close()
    snapshot = safe_extract_tarball(str(tar_path), str(tmp_path / "unpacked"))
    files = scan_repository_files(snapshot)
    assert not any(f.repo_relative_path in {".env", "cert.pem"} for f in files)
    assert next(f for f in files if f.repo_relative_path == "config.py").content is None
    indexed_content = "\n".join(f.content or "" for f in files)
    search_results = await search_ripgrep(snapshot, "FAKE_GHP_123456789012345678901234567890123456")
    search_results.extend(await search_ripgrep(snapshot, "DOTENV_SECRET_VALUE_123456789"))
    search_results.extend(await search_ripgrep(snapshot, "PRIVATE_KEY_MATERIAL_XYZ"))
    safe_results = await search_ripgrep(snapshot, "clean")
    assert safe_results and all(item.file_path == "app.py" for item in safe_results)
    assert not await search_ripgrep(snapshot, "safe")
    simulated_search = [result.model_dump() for result in search_results]
    evidence = "\n".join(item.snippet for item in safe_results)
    llm_prompt = f"Evidence: {evidence}"
    plan_export = render_plan_markdown({"summary": {"text": llm_prompt}, "steps": [], "impacted_files": [], "risks": [], "validation_checklist": [], "tests": {}})
    logs = caplog.text
    for secret in ["DOTENV_SECRET_VALUE_123456789", *secrets]:
        assert secret not in indexed_content + repr(simulated_search) + evidence + llm_prompt + plan_export + logs


def test_invalid_github_url_rejection():
    res = client.post("/api/v1/repositories", json={"url": "https://malicious.com/owner/repo"})
    assert res.status_code == 400
    data = res.json()
    assert data["error"]["code"] == "INVALID_ARGUMENT"
