import re
from typing import Optional, Tuple
from app.core.logging import logger

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Access Key
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),  # GitHub Tokens
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI / Anthropic-like keys
    re.compile(r"-----BEGIN [A-Z0-9_-]*\s*PRIVATE KEY-----"),  # Private Keys
    re.compile(r"""(?i)(?:api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['"][^'"]{12,}['"]"""),  # Generic secrets
]

EXCLUDED_FILENAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.staging",
    ".env.test",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
}

EXCLUDED_EXTENSIONS = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".keystore",
    ".jks",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".7z",
    ".rar",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".min.js",
    ".min.css",
}

EXCLUDED_DIRECTORIES = {
    ".git",
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    ".idea",
    ".vscode",
}


def should_exclude_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = normalized.split("/")
    filename = parts[-1] if parts else ""

    # Check directory components
    for dir_name in parts[:-1]:
        if dir_name in EXCLUDED_DIRECTORIES:
            return True

    # Check file patterns
    if filename in EXCLUDED_FILENAMES or filename.startswith(".env."):
        return True

    if filename.startswith("secrets.") or filename.startswith("credentials."):
        return True

    for ext in EXCLUDED_EXTENSIONS:
        if filename.endswith(ext):
            return True

    return False


def scan_for_secrets(content: str, file_path: str) -> bool:
    """
    Returns True if a secret pattern is detected.
    Never logs secret values.
    """
    if not content:
        return False

    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            logger.warning("Secret detected in %s; content redacted.", file_path)
            return True
    return False
