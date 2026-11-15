import ast
from importlib import import_module
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from app.core.logging import logger

try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except (ImportError, OSError):
    Language = None
    Parser = None
    HAS_TREE_SITTER = False

_GRAMMAR_FAILURES = set()


def _tree_sitter_parser(language: str) -> Any:
    grammar_functions = {
        "javascript": ("tree_sitter_javascript", "language"),
        "typescript": ("tree_sitter_typescript", "language_typescript"),
        "java": ("tree_sitter_java", "language"),
        "go": ("tree_sitter_go", "language"),
    }
    if not HAS_TREE_SITTER:
        raise RuntimeError("tree-sitter runtime is unavailable")
    module_name, function_name = grammar_functions[language]
    grammar_capsule = getattr(import_module(module_name), function_name)()
    grammar = Language(grammar_capsule)
    return Parser(grammar)


@dataclass
class ParsedSymbol:
    name: str
    kind: str  # function, class, method, interface, type, variable, enum
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_name: Optional[str] = None


@dataclass
class ParsedImport:
    raw_specifier: str
    line: int


Tuple_Symbols_Imports = Tuple[List[ParsedSymbol], List[ParsedImport]]


def _parse_python_ast(source_code: str) -> Tuple_Symbols_Imports:
    symbols: List[ParsedSymbol] = []
    imports: List[ParsedImport] = []
    lines = source_code.splitlines()

    try:
        tree = ast.parse(source_code)
    except Exception:
        return _regex_fallback_parse(source_code, "python")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ParsedImport(raw_specifier=alias.name, line=getattr(node, "lineno", 1)))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            prefix = "." * node.level if node.level else ""
            spec = f"{prefix}{module}"
            imports.append(ParsedImport(raw_specifier=spec, line=getattr(node, "lineno", 1)))

    def visit_class_or_func(node, parent_name=None):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_l = node.lineno
            end_l = getattr(node, "end_lineno", node.lineno)
            sig_line = lines[start_l - 1].strip() if start_l <= len(lines) else f"def {node.name}(...)"
            doc = ast.get_docstring(node)
            kind = "method" if parent_name else "function"
            symbols.append(
                ParsedSymbol(
                    name=node.name,
                    kind=kind,
                    start_line=start_l,
                    end_line=end_l,
                    signature=sig_line[:200],
                    docstring=doc[:500] if doc else None,
                    parent_name=parent_name,
                )
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit_class_or_func(child, parent_name=node.name)

        elif isinstance(node, ast.ClassDef):
            start_l = node.lineno
            end_l = getattr(node, "end_lineno", node.lineno)
            sig_line = lines[start_l - 1].strip() if start_l <= len(lines) else f"class {node.name}:"
            doc = ast.get_docstring(node)
            symbols.append(
                ParsedSymbol(
                    name=node.name,
                    kind="class",
                    start_line=start_l,
                    end_line=end_l,
                    signature=sig_line[:200],
                    docstring=doc[:500] if doc else None,
                    parent_name=parent_name,
                )
            )
            for child in node.body:
                visit_class_or_func(child, parent_name=node.name)

    for item in tree.body:
        visit_class_or_func(item)

    return symbols, imports


def _regex_fallback_parse(source_code: str, language: str) -> tuple[List[ParsedSymbol], List[ParsedImport]]:
    symbols: List[ParsedSymbol] = []
    imports: List[ParsedImport] = []
    lines = source_code.splitlines()

    # JS / TS import patterns
    # import ... from '...' or import '...'
    js_import_re = re.compile(r"""(?:import\s+(?:.*?\s+from\s+)?['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\)|export\s+.*?\s+from\s+['"]([^'"]+)['"])""")
    js_func_re = re.compile(r"""(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(""")
    js_const_func_re = re.compile(r"""(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>""")
    js_class_re = re.compile(r"""(?:export\s+)?class\s+([A-Za-z0-9_$]+)""")
    js_interface_re = re.compile(r"""(?:export\s+)?interface\s+([A-Za-z0-9_$]+)""")
    js_type_re = re.compile(r"""(?:export\s+)?type\s+([A-Za-z0-9_$]+)\s*=""")

    # Go patterns
    go_import_re = re.compile(r"""import\s+['"]([^'"]+)['"]|^\s*['"]([^'"]+)['"]""")
    go_func_re = re.compile(r"""func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)\s*\(""")
    go_type_re = re.compile(r"""type\s+([A-Za-z0-9_]+)\s+(?:struct|interface)""")

    # Java patterns
    java_import_re = re.compile(r"""import\s+(?:static\s+)?([A-Za-z0-9_.]+);""")
    java_class_re = re.compile(r"""(?:public|protected|private)?\s*(?:static)?\s*(?:class|interface|enum)\s+([A-Za-z0-9_]+)""")
    java_method_re = re.compile(r"""(?:public|protected|private)?\s*(?:static)?\s*[\w<>\[\],]+\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{?""")

    in_multi_import = False

    for idx, line in enumerate(lines):
        line_num = idx + 1
        stripped = line.strip()

        if language in ("javascript", "typescript"):
            # Imports
            for m in js_import_re.finditer(line):
                spec = m.group(1) or m.group(2) or m.group(3)
                if spec:
                    imports.append(ParsedImport(raw_specifier=spec, line=line_num))

            # Classes
            m = js_class_re.search(line)
            if m:
                symbols.append(ParsedSymbol(name=m.group(1), kind="class", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

            # Interfaces
            m = js_interface_re.search(line)
            if m:
                symbols.append(ParsedSymbol(name=m.group(1), kind="interface", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

            # Types
            m = js_type_re.search(line)
            if m:
                symbols.append(ParsedSymbol(name=m.group(1), kind="type", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

            # Functions
            m = js_func_re.search(line)
            if m:
                symbols.append(ParsedSymbol(name=m.group(1), kind="function", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

            m = js_const_func_re.search(line)
            if m:
                symbols.append(ParsedSymbol(name=m.group(1), kind="function", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

        elif language == "go":
            if stripped.startswith("import ("):
                in_multi_import = True
                continue
            if in_multi_import:
                if stripped.startswith(")"):
                    in_multi_import = False
                else:
                    m = go_import_re.search(line)
                    if m:
                        spec = m.group(1) or m.group(2)
                        if spec:
                            imports.append(ParsedImport(raw_specifier=spec, line=line_num))
                continue

            m = go_import_re.search(line)
            if m:
                spec = m.group(1) or m.group(2)
                if spec:
                    imports.append(ParsedImport(raw_specifier=spec, line=line_num))

            m = go_func_re.search(line)
            if m:
                symbols.append(ParsedSymbol(name=m.group(1), kind="function", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

            m = go_type_re.search(line)
            if m:
                symbols.append(ParsedSymbol(name=m.group(1), kind="type", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

        elif language == "java":
            m = java_import_re.search(line)
            if m:
                imports.append(ParsedImport(raw_specifier=m.group(1), line=line_num))

            m = java_class_re.search(line)
            if m:
                symbols.append(ParsedSymbol(name=m.group(1), kind="class", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

            m = java_method_re.search(line)
            if m and not any(kw in m.group(1) for kw in ("if", "for", "while", "switch", "catch")):
                symbols.append(ParsedSymbol(name=m.group(1), kind="method", start_line=line_num, end_line=line_num, signature=stripped[:200]))
                continue

    return symbols, imports


def extract_symbols_and_imports(
    language: Optional[str],
    source_bytes: bytes,
) -> tuple[List[ParsedSymbol], List[ParsedImport]]:
    if not source_bytes:
        return [], []

    try:
        source_code = source_bytes.decode("utf-8", errors="replace")
    except Exception:
        return [], []

    if language == "python":
        return _parse_python_ast(source_code)

    if language in ("javascript", "typescript", "java", "go"):
        try:
            parser = _tree_sitter_parser(language)
            tree = parser.parse(source_bytes)
            ts_symbols, ts_imports = _extract_via_tree_sitter(tree, source_bytes, language)
            return ts_symbols, ts_imports
        except Exception:
            if language not in _GRAMMAR_FAILURES:
                logger.warning(
                    "Tree-sitter grammar unavailable for %s; symbols and imports will be skipped.",
                    language,
                )
                _GRAMMAR_FAILURES.add(language)
            return [], []

    if language:
        return _regex_fallback_parse(source_code, language)

    return [], []


def _extract_via_tree_sitter(tree, source_bytes: bytes, language: str) -> tuple[List[ParsedSymbol], List[ParsedImport]]:
    symbols: List[ParsedSymbol] = []
    imports: List[ParsedImport] = []

    def get_text(node):
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def traverse(node, parent_name=None):
        ntype = node.type

        # Imports
        if ntype in ("import_statement", "import_declaration"):
            spec = get_text(node)
            imports.append(ParsedImport(raw_specifier=spec, line=node.start_point[0] + 1))
        elif ntype in ("function_declaration", "function_definition", "method_declaration", "method_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                sname = get_text(name_node)
                kind = "method" if parent_name else "function"
                sig = get_text(node).splitlines()[0] if get_text(node) else f"{sname}()"
                symbols.append(
                    ParsedSymbol(
                        name=sname,
                        kind=kind,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=sig[:200],
                        parent_name=parent_name,
                    )
                )
                parent_name = sname

        elif ntype in ("class_declaration", "class_definition", "interface_declaration", "type_declaration"):
            name_node = node.child_by_field_name("name")
            if name_node:
                sname = get_text(name_node)
                kind = "interface" if "interface" in ntype else "class"
                sig = get_text(node).splitlines()[0] if get_text(node) else f"{kind} {sname}"
                symbols.append(
                    ParsedSymbol(
                        name=sname,
                        kind=kind,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=sig[:200],
                        parent_name=parent_name,
                    )
                )
                parent_name = sname

        for child in node.children:
            traverse(child, parent_name)

    traverse(tree.root_node)
    return symbols, imports


Tuple_Symbols_Imports = tuple[List[ParsedSymbol], List[ParsedImport]]
