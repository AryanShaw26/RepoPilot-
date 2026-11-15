import hashlib
import json
import os
import posixpath
import re
import tarfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.services.languages import detect_language
from app.services.secrets import scan_for_secrets, should_exclude_path

TEST_PATH_PATTERNS = [
    re.compile(r"(?:^|/)(?:tests?|__tests__|spec)/", re.IGNORECASE),
    re.compile(r"test_[^/]+\.py$", re.IGNORECASE),
    re.compile(r"[^/]+_test\.(?:py|go)$", re.IGNORECASE),
    re.compile(r"[^/]+\.(?:test|spec)\.(?:js|jsx|ts|tsx)$", re.IGNORECASE),
    re.compile(r"[^/]+Test(?:s)?\.java$", re.IGNORECASE),
]

ENTRY_POINT_HEURISTICS = [
    re.compile(r"(?:^|/)(?:main|app|server|index)\.(?:py|js|ts|go)$", re.IGNORECASE),
    re.compile(r"^src/main\.[a-z]+$", re.IGNORECASE),
]


@dataclass
class ExtractedFileInfo:
    repo_relative_path: str
    directory: str
    language: Optional[str]
    size_bytes: int
    line_count: Optional[int]
    is_test: bool
    is_entry_point: bool
    content: Optional[str]
    sha1: Optional[str]


def safe_extract_tarball(tar_path: str, dest_dir: str) -> str:
    """
    Extracts tarball safely into dest_dir.
    Guards against zip-slip, symlinks, device files, and oversized files.
    Strips top-level directory if present.
    Returns the real path to the root of the extracted repo.
    """
    max_single_file = settings.MAX_FILE_BYTES * 20
    os.makedirs(dest_dir, exist_ok=True)
    dest_real = os.path.realpath(dest_dir)

    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        # GitHub tarballs put everything inside a single top-level folder e.g. owner-repo-sha/
        first_member = members[0].name.split("/")[0] if members else ""
        has_common_prefix = all(
            m.name == first_member or m.name.startswith(first_member + "/")
            for m in members
            if m.name
        )

        for m in members:
            # Skip symlinks, hardlinks, devices
            if m.issym() or m.islnk() or m.isdev():
                continue

            # Strip common prefix if present
            if has_common_prefix and (m.name == first_member or m.name.startswith(first_member + "/")):
                rel_parts = m.name.split("/")[1:]
                if not rel_parts:
                    continue
                member_clean_name = "/".join(rel_parts)
            else:
                member_clean_name = m.name

            target = os.path.realpath(os.path.join(dest_real, member_clean_name))
            if not target.startswith(dest_real + os.sep) and target != dest_real:
                # Zip-slip attempt!
                logger.warning("Blocked potential zip-slip member: %s", m.name)
                continue

            if m.isfile():
                if m.size > max_single_file:
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with tar.extractfile(m) as src, open(target, "wb") as dst:
                    if src:
                        dst.write(src.read())
            elif m.isdir():
                os.makedirs(target, exist_ok=True)

    return dest_real


def is_binary_content(data: bytes) -> bool:
    # NUL byte in first 8 KB indicates binary
    return b"\x00" in data[:8192]


def check_is_test(path: str) -> bool:
    norm = path.replace("\\", "/")
    return any(pattern.search(norm) for pattern in TEST_PATH_PATTERNS)


def check_is_entry_point(path: str) -> bool:
    norm = path.replace("\\", "/")
    return any(pattern.search(norm) for pattern in ENTRY_POINT_HEURISTICS)


def scan_repository_files(snapshot_dir: str) -> List[ExtractedFileInfo]:
    results: List[ExtractedFileInfo] = []

    for root, dirs, files in os.walk(snapshot_dir):
        # Filter directories in-place to avoid descending into ignored folders
        dirs[:] = [d for d in dirs if not should_exclude_path(os.path.join(root, d))]

        for file in files:
            if len(results) >= settings.MAX_FILES:
                logger.warning("Reached MAX_FILES limit (%d)", settings.MAX_FILES)
                return results

            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, snapshot_dir).replace("\\", "/")

            if should_exclude_path(rel_path):
                continue

            try:
                stat = os.stat(full_path)
                file_size = stat.st_size
            except Exception:
                continue

            language = detect_language(rel_path)
            directory = posixpath.dirname(rel_path) or "."
            is_test = check_is_test(rel_path)
            is_entry = check_is_entry_point(rel_path)

            # Read file if within size limit
            content: Optional[str] = None
            line_count: Optional[int] = None
            sha1: Optional[str] = None

            if file_size <= settings.MAX_FILE_BYTES:
                try:
                    with open(full_path, "rb") as f:
                        raw_bytes = f.read()

                    if not is_binary_content(raw_bytes):
                        sha1 = hashlib.sha1(raw_bytes).hexdigest()
                        decoded_content = raw_bytes.decode("utf-8", errors="replace")

                        # Secret scan
                        if scan_for_secrets(decoded_content, rel_path):
                            content = None
                        else:
                            content = decoded_content
                            line_count = len(decoded_content.splitlines())
                except Exception as e:
                    logger.debug("Failed to read file %s: %s", rel_path, e)

            results.append(
                ExtractedFileInfo(
                    repo_relative_path=rel_path,
                    directory=directory,
                    language=language,
                    size_bytes=file_size,
                    line_count=line_count,
                    is_test=is_test,
                    is_entry_point=is_entry,
                    content=content,
                    sha1=sha1,
                )
            )

    return results


def detect_frameworks_and_meta(files: List[ExtractedFileInfo]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    frameworks: List[Dict[str, Any]] = []
    entry_points: List[Dict[str, Any]] = []
    readme_excerpt: Optional[str] = None

    seen_frameworks = set()

    for f in files:
        # Check README
        if not readme_excerpt and f.repo_relative_path.lower().startswith("readme") and f.content:
            readme_excerpt = f.content[:1500].strip()

        # Check Entry points
        if f.is_entry_point:
            entry_points.append({"path": f.repo_relative_path, "reason": "Common entry point heuristic"})

        # Check package.json
        if f.repo_relative_path.endswith("package.json") and f.content:
            try:
                pkg_data = json.loads(f.content)
                deps = {}
                deps.update(pkg_data.get("dependencies", {}))
                deps.update(pkg_data.get("devDependencies", {}))

                known_node = {
                    "react": "React",
                    "next": "Next.js",
                    "vue": "Vue",
                    "express": "Express",
                    "fastify": "Fastify",
                    "@nestjs/core": "NestJS",
                    "svelte": "Svelte",
                    "@angular/core": "Angular",
                    "tailwindcss": "Tailwind CSS",
                    "prisma": "Prisma",
                }
                for dep, name in known_node.items():
                    if dep in deps and name not in seen_frameworks:
                        frameworks.append({"name": name, "evidence": f.repo_relative_path})
                        seen_frameworks.add(name)

                # Check main/start script for entry points
                main_field = pkg_data.get("main")
                if main_field:
                    entry_points.append({"path": main_field, "reason": "package.json main field"})

            except Exception:
                pass

        # Check Python manifests
        if (f.repo_relative_path.endswith("requirements.txt") or f.repo_relative_path.endswith("pyproject.toml")) and f.content:
            content_lower = f.content.lower()
            known_py = {
                "fastapi": "FastAPI",
                "django": "Django",
                "flask": "Flask",
                "sqlalchemy": "SQLAlchemy",
                "pydantic": "Pydantic",
                "celery": "Celery",
                "pytest": "pytest",
            }
            for kw, name in known_py.items():
                if kw in content_lower and name not in seen_frameworks:
                    frameworks.append({"name": name, "evidence": f.repo_relative_path})
                    seen_frameworks.add(name)

        # Check Go manifests
        if f.repo_relative_path.endswith("go.mod") and f.content:
            content_lower = f.content.lower()
            known_go = {
                "gin-gonic/gin": "Gin",
                "gofiber/fiber": "Fiber",
                "labstack/echo": "Echo",
                "gorm.io/gorm": "GORM",
            }
            for kw, name in known_go.items():
                if kw in content_lower and name not in seen_frameworks:
                    frameworks.append({"name": name, "evidence": f.repo_relative_path})
                    seen_frameworks.add(name)

        # Check Java manifests
        if f.repo_relative_path.endswith("pom.xml") and f.content:
            content_lower = f.content.lower()
            if "spring-boot" in content_lower and "Spring Boot" not in seen_frameworks:
                frameworks.append({"name": "Spring Boot", "evidence": f.repo_relative_path})
                seen_frameworks.add("Spring Boot")

    return frameworks, entry_points, readme_excerpt
