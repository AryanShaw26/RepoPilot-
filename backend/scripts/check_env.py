import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import asyncpg
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import (
    BASE_DIR,
    database_url_overridden,
    database_url_shape,
    settings,
    settings_diagnostics,
)
from app.db.session import dispose_engine, get_engine


ROOT_DIR = BASE_DIR.parent
SECRET_KEY_NAMES = {
    "GITHUB_TOKEN",
    "LLM_API_KEY",
    "EMBEDDING_API_KEY",
    "DATABASE_URL",
    "POSTGRES_PASSWORD",
}
REQUIRED_ENV_KEYS = {
    "backend": {"DATABASE_URL"},
    "frontend": {"VITE_API_BASE_URL"},
}


def parse_env(path: Path) -> Tuple[Dict[str, str], List[str], List[str], str]:
    raw = path.read_bytes()
    text_value = raw.decode("utf-8-sig")
    values: Dict[str, str] = {}
    duplicates: List[str] = []
    quoted: List[str] = []
    for line in text_value.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            quoted.append(key)
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        if key in values:
            duplicates.append(key)
        values[key] = value
    line_ending = (
        "mixed"
        if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b"")
        else "CRLF"
        if b"\r\n" in raw
        else "LF"
        if b"\n" in raw
        else "none"
    )
    return values, duplicates, quoted, line_ending


def ignored(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT_DIR)
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(relative)],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
        )
        return result.returncode == 0
    except (OSError, ValueError):
        return False


def inspect_env_file(folder: Path) -> Tuple[bool, List[str]]:
    env_path = folder / ".env"
    example_path = folder / ".env.example"
    issues: List[str] = []
    if not example_path.is_file():
        print(f"{example_path.relative_to(ROOT_DIR)}: missing")
        return False, ["missing env example"]
    if not env_path.is_file():
        print(f"{env_path.relative_to(ROOT_DIR)}: missing")
        return False, ["missing env file"]

    raw = env_path.read_bytes()
    values, duplicates, quoted, line_ending = parse_env(env_path)
    expected, _, _, example_line_ending = (
        parse_env(example_path) if example_path.is_file() else ({}, [], [], "unknown")
    )
    missing = sorted(set(expected) - set(values))
    empty = sorted(key for key, value in values.items() if not value)
    unknown = sorted(set(values) - set(expected))
    non_vite = sorted(
        key for key in values if folder.name == "frontend" and not key.startswith("VITE_")
    )
    secret_keys = sorted(set(values) & SECRET_KEY_NAMES) if folder.name == "frontend" else []
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    ignored_file = ignored(env_path)
    line_anomaly = line_ending not in ("none", example_line_ending)

    def show(items: List[str]) -> str:
        return ", ".join(items) if items else "none"

    print(f"{env_path.relative_to(ROOT_DIR)}:")
    print(f"  missing keys: {show(missing)}")
    print(f"  empty keys: {show(empty)}")
    print(f"  unknown keys: {show(unknown)}")
    print(f"  duplicate keys: {show(sorted(set(duplicates)))}")
    print(f"  surrounding quotes: {show(sorted(set(quoted)))}")
    print(
        f"  BOM: {'yes' if has_bom else 'no'}; line endings: {line_ending} "
        f"(example: {example_line_ending}{', anomaly' if line_anomaly else ''})"
    )
    print(f"  git-ignored: {'yes' if ignored_file else 'no'}")
    if folder.name == "frontend":
        print(f"  non-VITE keys: {show(non_vite)}")
        print(f"  secret-key names: {show(secret_keys)}")

    if REQUIRED_ENV_KEYS.get(folder.name, set()) & (set(missing) | set(empty)):
        issues.append("required env value missing")
    if unknown:
        issues.append("unknown env keys")
    if duplicates:
        issues.append("duplicate env keys")
    if not ignored_file:
        issues.append("env file is not git-ignored")
    if non_vite or secret_keys:
        issues.append("frontend env contains disallowed keys")
    return not issues, issues


async def check_database() -> Tuple[bool, bool, set, str, str]:
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
            migrated = (
                await connection.execute(
                    text("SELECT to_regclass('public.repositories')")
                )
            ).scalar_one() is not None
            extensions = set(
                (
                    await connection.execute(
                        text("SELECT extname FROM pg_extension WHERE extname IN "
                             "('vector', 'pg_trgm', 'pgcrypto')")
                    )
                ).scalars()
            )
            vector_type = (
                await connection.execute(
                    text(
                        "SELECT format_type(attribute.atttypid, attribute.atttypmod) "
                        "FROM pg_attribute AS attribute "
                        "JOIN pg_class AS relation ON relation.oid = attribute.attrelid "
                        "JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace "
                        "WHERE namespace.nspname = 'public' AND relation.relname = 'code_chunks' "
                        "AND attribute.attname = 'embedding' AND NOT attribute.attisdropped"
                    )
                )
            ).scalar_one_or_none()
        return True, migrated, extensions, vector_type or "", ""
    except (SQLAlchemyError, asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        return False, False, set(), "", "PostgreSQL connection failed."


def test_snapshot_writable() -> bool:
    path = Path(settings.SNAPSHOT_DIR)
    if not path.is_absolute():
        path = BASE_DIR / path
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".repopilot-check-", delete=True):
            pass
        return True
    except OSError:
        return False


async def main() -> int:
    passed = True
    print("RepoPilot environment check (secret values are never displayed)")
    backend_ok, _ = inspect_env_file(BASE_DIR)
    frontend_ok, _ = inspect_env_file(ROOT_DIR / "frontend")
    passed &= backend_ok and frontend_ok

    diagnostics = settings_diagnostics()
    print("\nEffective configuration:")
    for key, diagnostic in diagnostics.items():
        if key == "DATABASE_URL":
            continue
        status = diagnostic["status"]
        if key in SECRET_KEY_NAMES:
            status = "set" if status == "set" else "empty"
        print(f"  {key}: {status} ({diagnostic['source']})")
    shape = database_url_shape(settings.DATABASE_URL)
    print(
        "  DATABASE_URL: "
        f"driver={shape['driver']} host={shape['host']} port={shape['port']} "
        f"db={shape['database']}"
    )
    override = database_url_overridden()
    print(f"  OS DATABASE_URL overrides backend/.env: {'yes' if override else 'no'}")

    db_ok, migrated, extensions, vector_type, db_error = await check_database()
    print(f"\nPostgreSQL connection: {'pass' if db_ok else 'fail'}")
    if not db_ok:
        print(f"  {db_error} Start PostgreSQL and verify DATABASE_URL.")
        passed = False
    print(f"Schema migrations: {'pass' if migrated else 'fail'}")
    if db_ok and not migrated:
        print("  Next action: run `alembic upgrade head` from backend/.")
        passed = False
    for extension, optional in (("pgcrypto", False), ("pg_trgm", False), ("vector", True)):
        installed = extension in extensions
        print(f"  {extension}: {'installed' if installed else 'not installed'}")
        if not installed and not optional and db_ok and migrated:
            print(f"    Next action: ask a PostgreSQL administrator to install {extension}.")
            passed = False
        elif not installed and optional:
            print("    Semantic search is disabled; install pgvector to enable it.")
    if "vector" in extensions:
        expected_vector_type = f"vector({settings.EMBEDDING_DIM})"
        print(f"  embedding column: {vector_type or 'missing'}")
        if vector_type != expected_vector_type:
            print(
                f"    Next action: update the embedding column to {expected_vector_type}; "
                "semantic search is disabled until dimensions match."
            )
            passed = False

    rg_path = shutil.which("rg")
    print(f"\nripgrep: {'available' if rg_path else 'not found'}")
    if not rg_path:
        print("  Keyword search falls back to the database index.")
    writable = test_snapshot_writable()
    print(f"Snapshot directory writable: {'yes' if writable else 'no'}")
    if not writable:
        print("  Next action: grant write access to SNAPSHOT_DIR or choose a writable path.")
        passed = False

    await dispose_engine()
    print(f"\nResult: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
