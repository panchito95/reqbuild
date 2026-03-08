"""
writer.py – Formats and writes the requirements output.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

from .resolver import ResolveResult
from .scanner import ImportRecord


def _build_content(
    resolve_result: ResolveResult,
    optional_imports: list[str] | None = None,
) -> str:
    """Return the full text of the requirements file."""
    buf = StringIO()

    # Deduplicate: multiple imports can map to the same PyPI package
    unique_pkgs = sorted(set(resolve_result.resolved.values()), key=str.lower)

    for pkg in unique_pkgs:
        buf.write(f"{pkg}\n")

    if optional_imports:
        buf.write("\n# ─── Optional dependencies (detected inside try/except ImportError) ───\n")
        opt_resolved: dict[str, str] = {}
        opt_unresolved: list[str] = []
        for imp in sorted(optional_imports):
            if imp in resolve_result.resolved:
                opt_resolved[imp] = resolve_result.resolved[imp]
            else:
                opt_unresolved.append(imp)

        opt_pkgs = sorted(set(opt_resolved.values()), key=str.lower)
        for pkg in opt_pkgs:
            buf.write(f"# {pkg}\n")
        for imp in opt_unresolved:
            buf.write(f"# ⚠️  {imp}  (unresolved)\n")

    if resolve_result.unresolved:
        buf.write("\n# ─── Revisar manualmente / Review manually ──────────────────────────\n")
        for imp in sorted(resolve_result.unresolved):
            buf.write(f"# ⚠️  {imp}\n")

    return buf.getvalue()


def write_file(
    resolve_result: ResolveResult,
    output_path: str | Path,
    optional_imports: list[str] | None = None,
) -> Path:
    """Write requirements to *output_path* and return the Path."""
    output_path = Path(output_path)
    content = _build_content(resolve_result, optional_imports)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def print_output(
    resolve_result: ResolveResult,
    optional_imports: list[str] | None = None,
    file=None,
) -> None:
    """Print requirements to stdout (or *file*)."""
    if file is None:
        file = sys.stdout
    content = _build_content(resolve_result, optional_imports)
    file.write(content)
