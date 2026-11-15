import io
import os
import tarfile
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest

from app.core.errors import AppError
from app.core.security import parse_github_issue_url, parse_github_url
from app.services.graph import GraphService, tarjan_scc_iterative
from app.services.imports import resolve_js_ts_import, resolve_python_import
from app.services.ingest import safe_extract_tarball, scan_repository_files
from app.services.languages import detect_language
from app.services.parser import extract_symbols_and_imports
from app.services.planner import render_plan_markdown
from app.services.secrets import scan_for_secrets, should_exclude_path
from app.services.validator import validate_hypotheses, validate_plan_steps
from app.workers.jobs import has_vector_storage


def test_parse_github_url():
    # Valid
    owner, repo, branch = parse_github_url("https://github.com/fastapi/fastapi")
    assert owner == "fastapi"
    assert repo == "fastapi"
    assert branch is None

    owner, repo, branch = parse_github_url("https://github.com/torvalds/linux/tree/master")
    assert owner == "torvalds"
    assert repo == "linux"
    assert branch == "master"

    # With .git
    owner, repo, branch = parse_github_url("https://github.com/owner/my-repo.git")
    assert repo == "my-repo"

    # Invalid / SSRF attempts
    invalid_urls = [
        "http://localhost:8000",
        "https://evil-github.com/owner/repo",
        "https://github.com.evil.com/owner/repo",
        "https://github.com/owner",
        "ftp://github.com/owner/repo",
        "javascript:alert(1)",
    ]
    for url in invalid_urls:
        with pytest.raises(AppError) as exc_info:
            parse_github_url(url)
        assert exc_info.value.code == "INVALID_URL"


def test_parse_github_issue_url():
    owner, repo, num = parse_github_issue_url("https://github.com/tiangolo/fastapi/issues/1234")
    assert owner == "tiangolo"
    assert repo == "fastapi"
    assert num == 1234

    with pytest.raises(AppError):
        parse_github_issue_url("https://github.com/tiangolo/fastapi/pull/1234")


def test_secrets_scanner():
    # Negative cases
    assert not scan_for_secrets("def hello(): return 'world'", "test.py")

    # Positive cases
    assert scan_for_secrets("AWS_KEY = 'AKIA1234567890ABCDEF'", "config.py")
    assert scan_for_secrets("TOKEN = 'ghp_123456789012345678901234567890123456'", "creds.py")
    assert scan_for_secrets("-----BEGIN RSA PRIVATE KEY-----\nMIIE...", "key.pem")

    # Exclusions
    assert should_exclude_path(".env")
    assert should_exclude_path(".env.production")
    assert should_exclude_path("node_modules/express/index.js")
    assert should_exclude_path("dist/bundle.js")
    assert should_exclude_path("secret.pem")
    assert not should_exclude_path("src/components/Button.tsx")


def test_language_detection():
    assert detect_language("app/main.py") == "python"
    assert detect_language("src/index.ts") == "typescript"
    assert detect_language("src/App.jsx") == "javascript"
    assert detect_language("cmd/main.go") == "go"
    assert detect_language("src/Main.java") == "java"
    assert detect_language("Dockerfile") == "dockerfile"


def test_python_ast_parser():
    code = """
import os
from app.core import config

class AuthManager:
    \"\"\"Manages authentication.\"\"\"
    def verify_token(self, token: str) -> bool:
        return True

def standalone_func():
    pass
"""
    symbols, imports = extract_symbols_and_imports("python", code.encode("utf-8"))
    assert len(imports) == 2
    raw_specs = [imp.raw_specifier for imp in imports]
    assert "os" in raw_specs
    assert "app.core" in raw_specs

    sym_names = [s.name for s in symbols]
    assert "AuthManager" in sym_names
    assert "verify_token" in sym_names
    assert "standalone_func" in sym_names

    # Check method parent
    verify_sym = [s for s in symbols if s.name == "verify_token"][0]
    assert verify_sym.kind == "method"
    assert verify_sym.parent_name == "AuthManager"


@pytest.mark.parametrize(
    ("language", "source"),
    [
        (
            "javascript",
            b"import { helper } from './helper.js';\nexport function analyze() { return helper(); }\n",
        ),
        (
            "typescript",
            b"import { helper } from './helper';\nexport function analyze(): string { return helper(); }\n",
        ),
    ],
)
def test_tree_sitter_javascript_typescript_parser(language, source):
    symbols, imports = extract_symbols_and_imports(language, source)
    assert any(symbol.name == "analyze" for symbol in symbols)
    assert imports


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [True, False])
async def test_vector_storage_availability(available):
    db = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = available
    db.execute.return_value = result

    assert await has_vector_storage(db) is available


def test_safe_extract_zipslip_protection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = os.path.join(tmp_dir, "test.tar.gz")
        dest_dir = os.path.join(tmp_dir, "extracted")

        # Create tar with a zip-slip path '../evil.txt'
        with tarfile.open(tar_path, "w:gz") as tar:
            f1 = tarfile.TarInfo("root-repo/valid.txt")
            data1 = b"normal file content"
            f1.size = len(data1)
            tar.addfile(f1, io.BytesIO(data1))

            f_evil = tarfile.TarInfo("root-repo/../../evil.txt")
            data_evil = b"evil content"
            f_evil.size = len(data_evil)
            tar.addfile(f_evil, io.BytesIO(data_evil))

            f_link = tarfile.TarInfo("root-repo/linked.txt")
            f_link.type = tarfile.SYMTYPE
            f_link.linkname = "../../outside.txt"
            tar.addfile(f_link)

        extracted_root = safe_extract_tarball(tar_path, dest_dir)
        assert os.path.exists(os.path.join(extracted_root, "valid.txt"))
        # Ensure evil.txt was NOT extracted outside dest_dir
        assert not os.path.exists(os.path.join(tmp_dir, "evil.txt"))
        assert not os.path.lexists(os.path.join(extracted_root, "linked.txt"))


def test_repository_scan_excludes_secret_files_and_content():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = os.path.join(tmp_dir, "fixture.tar.gz")
        dest_dir = os.path.join(tmp_dir, "extracted")
        with tarfile.open(tar_path, "w:gz") as tar:
            members = {
                "fixture/.env.production": b"FAKE_KEY=DO_NOT_INDEX_TEST_VALUE",
                "fixture/src/settings.py": b"TOKEN = 'ghp_123456789012345678901234567890123456'\n",
                "fixture/src/app.py": b"def run():\n    return True\n",
            }
            for name, content in members.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                tar.addfile(member, io.BytesIO(content))

        extracted_root = safe_extract_tarball(tar_path, dest_dir)
        files = scan_repository_files(extracted_root)

    paths = {file.repo_relative_path for file in files}
    assert ".env.production" not in paths
    settings_file = next(file for file in files if file.repo_relative_path == "src/settings.py")
    assert settings_file.content is None
    assert all(
        "DO_NOT_INDEX_TEST_VALUE" not in (file.content or "")
        and "ghp_123456789012345678901234567890123456" not in (file.content or "")
        for file in files
    )
    assert next(file for file in files if file.repo_relative_path == "src/app.py").content


def test_tarjan_scc_cycles():
    # Graph with cycle: A -> B -> C -> A
    adj = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A", "D"],
        "D": [],
    }
    cycles = tarjan_scc_iterative(adj)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B", "C"}


def test_file_graph_aggregates_duplicate_import_edges():
    source_id = uuid.uuid4()
    target_id = uuid.uuid4()
    files = [
        SimpleNamespace(
            id=source_id,
            path="src/source.py",
            language="python",
            is_entry_point=False,
        ),
        SimpleNamespace(
            id=target_id,
            path="src/target.py",
            language="python",
            is_entry_point=False,
        ),
    ]
    imports = [
        SimpleNamespace(
            source_file_id=source_id,
            target_file_id=target_id,
            is_external=False,
            package_name=None,
        )
        for _ in range(2)
    ]

    graph = GraphService._build_file_graph(files, imports, False, None)

    assert len(graph.edges) == 1
    assert graph.edges[0].weight == 2
    assert graph.stats.total_edges == 1
    assert graph.stats.internal_imports == 2
    assert graph.nodes[0].out_degree == 2


def test_validator_rules():
    valid_eids = {"E1", "E2"}

    hypotheses = [
        {"id": "h1", "text": "Supported hypothesis", "confidence": "high", "evidence_refs": ["E1", "E99"]},
        {"id": "h2", "text": "Unsupported hypothesis", "confidence": "high", "evidence_refs": ["E99"]},
    ]

    validated = validate_hypotheses(hypotheses, valid_eids)
    assert len(validated) == 2

    # h1 has E99 removed but E1 kept, stays supported
    assert validated[0].evidence_refs == ["E1"]
    assert not validated[0].unsupported
    assert validated[0].kind == "hypothesis"

    # h2 has E99 removed -> 0 valid refs -> downgraded to low and marked unsupported
    assert validated[1].evidence_refs == []
    assert validated[1].confidence == "low"
    assert validated[1].unsupported


def test_plan_steps_validator():
    valid_repo_paths = {"src/auth.py", "src/models.py"}
    steps = [
        {"order": 1, "title": "Check auth", "files": ["src/auth.py", "nonexistent/file.py"]},
    ]
    validated = validate_plan_steps(steps, valid_repo_paths)
    assert validated[0]["files"] == ["src/auth.py"]
    assert validated[0]["kind"] == "hypothesis"


def test_render_plan_markdown():
    plan = {
        "summary": {"text": "Fix authentication expiration bug.", "kind": "hypothesis"},
        "steps": [
            {
                "order": 1,
                "title": "Update token refresh logic",
                "description": "Modify token expiration check.",
                "files": ["src/auth.py"],
                "kind": "hypothesis",
            }
        ],
        "impacted_files": [{"path": "src/api.py", "reason": "imports src/auth.py", "kind": "fact"}],
        "risks": [{"text": "May cause session logout", "confidence": "low", "kind": "hypothesis"}],
        "validation_checklist": ["Run pytest locally"],
        "tests": {
            "existing": [{"path": "tests/test_auth.py", "method": "name_convention", "kind": "fact"}],
            "recommended": [{"scenario": "Expired token refresh", "kind": "hypothesis"}],
        },
    }
    md = render_plan_markdown(plan)
    assert "# RepoPilot Contribution Plan" in md
    assert "[Verified]" in md
    assert "[Hypothesis]" in md
    assert "RepoPilot did not execute any code or tests." in md
    assert "test passed" not in md.lower()
