"""
scanner.py – Walks the project tree and extracts import names via AST.
"""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# Folders ignored by default (never relevant for dependencies)
DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".venv",
        "venv",
        ".env",
        "env",
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        "dist",
        "build",
        "site-packages",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        ".eggs",
    }
)

STDLIB: frozenset[str] = frozenset(
    sys.stdlib_module_names if hasattr(sys, "stdlib_module_names") else []
)


@dataclass
class ImportRecord:
    name: str
    source_file: str
    is_optional: bool = False  # found inside try/except ImportError


@dataclass
class ScanResult:
    imports: list[ImportRecord] = field(default_factory=list)
    local_modules: set[str] = field(default_factory=set)
    scanned_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _is_import_error_handler(handler: ast.ExceptHandler) -> bool:
    """Return True if the except clause catches ImportError / ModuleNotFoundError."""
    if handler.type is None:
        return False
    caught = handler.type
    if isinstance(caught, ast.Name):
        return caught.id in ("ImportError", "ModuleNotFoundError")
    if isinstance(caught, ast.Tuple):
        return any(
            isinstance(e, ast.Name) and e.id in ("ImportError", "ModuleNotFoundError")
            for e in caught.elts
        )
    return False


def _extract_imports(
    tree: ast.AST,
    source_file: str,
    detect_optional: bool = False,
) -> list[ImportRecord]:
    """Walk an AST and collect all top-level import names."""
    records: list[ImportRecord] = []

    # Collect nodes that are inside an ImportError try/except body
    optional_nodes: set[int] = set()

    if detect_optional:
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if _is_import_error_handler(handler):
                        # Mark all nodes inside the try body
                        for child in ast.walk(node):
                            optional_nodes.add(id(child))

    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names = [node.module.split(".")[0]]

        is_optional = detect_optional and id(node) in optional_nodes
        for name in names:
            if name:
                records.append(ImportRecord(name, source_file, is_optional))

    return records


def _iter_py_files(
    root: Path,
    recursive: bool,
    ignore_dirs: frozenset[str],
    ignore_files: set[str],
) -> Iterator[Path]:
    """Yield .py files respecting the ignore rules."""
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            for fname in filenames:
                if fname.endswith(".py") and fname not in ignore_files:
                    yield Path(dirpath) / fname
    else:
        for item in root.iterdir():
            if item.is_file() and item.suffix == ".py" and item.name not in ignore_files:
                yield item


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def scan(
    root: str | Path = ".",
    recursive: bool = False,
    extra_ignore_dirs: list[str] | None = None,
    extra_ignore_files: list[str] | None = None,
    detect_optional: bool = False,
    self_name: str = "reqbuild",
) -> ScanResult:
    """
    Scan *root* for Python files and extract their imports.

    Parameters
    ----------
    root            : Directory to scan.
    recursive       : If True, descend into subdirectories.
    extra_ignore_dirs  : Additional directory names to skip.
    extra_ignore_files : Additional file names to skip.
    detect_optional : If True, tag imports inside try/except ImportError.
    self_name       : Name of this tool's own script (excluded automatically).
    """
    root = Path(root).resolve()
    ignore_dirs = DEFAULT_IGNORE_DIRS | frozenset(extra_ignore_dirs or [])
    ignore_files: set[str] = set(extra_ignore_files or [])

    result = ScanResult()

    # Collect local module names first (file stems reachable from root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        for fname in filenames:
            if fname.endswith(".py"):
                result.local_modules.add(Path(fname).stem)

    all_imports: list[ImportRecord] = []

    for py_file in _iter_py_files(root, recursive, ignore_dirs, ignore_files):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
            records = _extract_imports(tree, str(py_file), detect_optional)
            all_imports.extend(records)
            result.scanned_files.append(str(py_file))
        except SyntaxError as exc:
            result.skipped_files.append(f"{py_file}: SyntaxError – {exc.msg}")
        except Exception as exc:  # noqa: BLE001
            result.skipped_files.append(f"{py_file}: {exc}")

    # Filter out stdlib, local modules, and empty names
    result.imports = [
        r
        for r in all_imports
        if r.name
        and r.name not in STDLIB
        and r.name not in result.local_modules
    ]

    return result
