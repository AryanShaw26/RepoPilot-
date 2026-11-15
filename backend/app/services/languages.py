from typing import Optional, Set

LANGUAGE_EXTENSIONS = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".pyw": "python",
    # JavaScript & TypeScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    # Java & JVM
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # C / C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    # C#
    ".cs": "csharp",
    # Ruby
    ".rb": "ruby",
    # PHP
    ".php": "php",
    # Swift
    ".swift": "swift",
    # Web & Markup
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "scss",
    ".less": "less",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".dockerfile": "dockerfile",
}

TREE_SITTER_SUPPORTED_LANGUAGES: Set[str] = {
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
}


def detect_language(path: str) -> Optional[str]:
    lower_path = path.lower()
    if lower_path.endswith("dockerfile") or "/dockerfile" in lower_path:
        return "dockerfile"
    for ext, lang in LANGUAGE_EXTENSIONS.items():
        if lower_path.endswith(ext):
            return lang
    return None


def is_tree_sitter_supported(language: Optional[str]) -> bool:
    return bool(language and language in TREE_SITTER_SUPPORTED_LANGUAGES)
