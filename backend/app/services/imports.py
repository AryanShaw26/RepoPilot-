import os
import posixpath
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import uuid

Tuple_Resolved = Tuple[Optional[uuid.UUID], bool, Optional[str]]


@dataclass
class ResolvedImport:
    raw_specifier: str
    line: Optional[int]
    target_file_id: Optional[uuid.UUID]
    is_external: bool
    package_name: Optional[str]


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def resolve_js_ts_import(
    raw_specifier: str,
    source_path: str,
    all_files_by_path: Dict[str, uuid.UUID],
) -> Tuple_Resolved:
    spec = raw_specifier.strip().strip("'\"")
    # Check if relative
    if spec.startswith("./") or spec.startswith("../"):
        source_dir = posixpath.dirname(source_path)
        combined = posixpath.normpath(posixpath.join(source_dir, spec))

        # Try exact, extensions, index files
        extensions = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]
        for ext in extensions:
            candidate = combined + ext
            if candidate in all_files_by_path:
                return all_files_by_path[candidate], False, None

        # Try /index.*
        for ext in [".ts", ".tsx", ".js", ".jsx"]:
            candidate = posixpath.join(combined, f"index{ext}")
            if candidate in all_files_by_path:
                return all_files_by_path[candidate], False, None

        return None, False, None
    else:
        # Bare specifier -> external
        if spec.startswith("@"):
            parts = spec.split("/")
            pkg = f"{parts[0]}/{parts[1]}" if len(parts) > 1 else spec
        else:
            pkg = spec.split("/")[0]
        return None, True, pkg


def resolve_python_import(
    raw_specifier: str,
    source_path: str,
    all_files_by_path: Dict[str, uuid.UUID],
    source_roots: List[str],
) -> Tuple_Resolved:
    spec = raw_specifier.strip().strip("'\"")

    # Handle relative imports (e.g. .utils, ..core)
    if spec.startswith("."):
        dots = len(spec) - len(spec.lstrip("."))
        submodule = spec[dots:]
        source_dir = posixpath.dirname(source_path)
        current_dir = source_dir
        for _ in range(dots - 1):
            current_dir = posixpath.dirname(current_dir)

        rel_path = posixpath.join(current_dir, submodule.replace(".", "/")) if submodule else current_dir
        # Check candidates
        candidates = [f"{rel_path}.py", posixpath.join(rel_path, "__init__.py")]
        for c in candidates:
            c_norm = posixpath.normpath(c)
            if c_norm in all_files_by_path:
                return all_files_by_path[c_norm], False, None
        return None, False, None

    # Dotted absolute imports
    as_path = spec.replace(".", "/")
    roots_to_try = ["", "src", "app"] + source_roots

    for root in roots_to_try:
        base = posixpath.join(root, as_path) if root else as_path
        candidates = [f"{base}.py", posixpath.join(base, "__init__.py")]
        for c in candidates:
            c_norm = posixpath.normpath(c)
            if c_norm in all_files_by_path:
                return all_files_by_path[c_norm], False, None

    # If not found internally, assume external top-level package
    pkg = spec.split(".")[0]
    return None, True, pkg


def resolve_go_import(
    raw_specifier: str,
    module_name: Optional[str],
    all_files_by_path: Dict[str, uuid.UUID],
) -> Tuple_Resolved:
    spec = raw_specifier.strip().strip("'\"")
    if module_name and spec.startswith(module_name):
        rel_pkg = spec[len(module_name):].strip("/")
        # Find any file in that package directory
        for p, fid in all_files_by_path.items():
            if posixpath.dirname(p) == rel_pkg:
                return fid, False, None
        return None, False, None

    # External
    parts = spec.split("/")
    pkg = "/".join(parts[:3]) if len(parts) >= 3 else spec
    return None, True, pkg


def resolve_java_import(
    raw_specifier: str,
    all_files_by_path: Dict[str, uuid.UUID],
) -> Tuple_Resolved:
    spec = raw_specifier.strip().strip("'\"")
    parts = spec.split(".")
    class_name = parts[-1]

    # Look for files ending with ClassName.java
    for p, fid in all_files_by_path.items():
        if p.endswith(f"/{class_name}.java") or p == f"{class_name}.java":
            return fid, False, None

    pkg = ".".join(parts[:3]) if len(parts) >= 3 else spec
    return None, True, pkg


def resolve_import(
    raw_specifier: str,
    line: Optional[int],
    source_path: str,
    language: Optional[str],
    all_files_by_path: Dict[str, uuid.UUID],
    source_roots: Optional[List[str]] = None,
    go_module_name: Optional[str] = None,
) -> ResolvedImport:
    target_id = None
    is_ext = False
    pkg = None

    if language in ("javascript", "typescript"):
        target_id, is_ext, pkg = resolve_js_ts_import(raw_specifier, source_path, all_files_by_path)
    elif language == "python":
        target_id, is_ext, pkg = resolve_python_import(raw_specifier, source_path, all_files_by_path, source_roots or [])
    elif language == "go":
        target_id, is_ext, pkg = resolve_go_import(raw_specifier, go_module_name, all_files_by_path)
    elif language == "java":
        target_id, is_ext, pkg = resolve_java_import(raw_specifier, all_files_by_path)
    else:
        # Generic heuristic
        if raw_specifier.startswith(".") or "/" in raw_specifier:
            target_id, is_ext, pkg = resolve_js_ts_import(raw_specifier, source_path, all_files_by_path)
        else:
            is_ext = True
            pkg = raw_specifier.split("/")[0]

    return ResolvedImport(
        raw_specifier=raw_specifier,
        line=line,
        target_file_id=target_id,
        is_external=is_ext,
        package_name=pkg,
    )


Tuple_Resolved = tuple[Optional[uuid.UUID], bool, Optional[str]]
