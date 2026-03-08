"""
tests/test_reqbuild.py – Unit tests for reqbuild.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from reqbuild.scanner import scan, DEFAULT_IGNORE_DIRS, STDLIB
from reqbuild.resolver import ResolveResult, resolve
from reqbuild.writer import _build_content


# ─── scanner ─────────────────────────────────────────────────────────────────

class TestScanner:
    def _write(self, tmp_path: Path, filename: str, source: str) -> Path:
        p = tmp_path / filename
        p.write_text(textwrap.dedent(source), encoding="utf-8")
        return p

    def test_basic_import(self, tmp_path):
        self._write(tmp_path, "app.py", """\
            import requests
            import os
        """)
        result = scan(tmp_path, recursive=False)
        names = {r.name for r in result.imports}
        assert "requests" in names
        assert "os" not in names  # stdlib filtered out

    def test_from_import(self, tmp_path):
        self._write(tmp_path, "app.py", """\
            from flask import Flask
            from collections import defaultdict
        """)
        result = scan(tmp_path, recursive=False)
        names = {r.name for r in result.imports}
        assert "flask" in names
        assert "collections" not in names

    def test_local_module_excluded(self, tmp_path):
        self._write(tmp_path, "utils.py", "x = 1")
        self._write(tmp_path, "app.py", "import utils")
        result = scan(tmp_path, recursive=False)
        names = {r.name for r in result.imports}
        assert "utils" not in names

    def test_recursive_flag(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        self._write(sub, "deep.py", "import numpy")
        result_flat = scan(tmp_path, recursive=False)
        result_all  = scan(tmp_path, recursive=True)
        flat_names = {r.name for r in result_flat.imports}
        all_names  = {r.name for r in result_all.imports}
        assert "numpy" not in flat_names
        assert "numpy" in all_names

    def test_extra_ignore_dirs(self, tmp_path):
        ignored = tmp_path / "tests"
        ignored.mkdir()
        self._write(ignored, "t.py", "import pytest")
        result = scan(tmp_path, recursive=True, extra_ignore_dirs=["tests"])
        names = {r.name for r in result.imports}
        assert "pytest" not in names

    def test_extra_ignore_files(self, tmp_path):
        self._write(tmp_path, "setup.py", "import distutils")
        self._write(tmp_path, "main.py", "import flask")
        result = scan(tmp_path, recursive=False, extra_ignore_files=["setup.py"])
        names = {r.name for r in result.imports}
        assert "distutils" not in names
        assert "flask" in names

    def test_default_ignore_dirs_content(self):
        for d in (".venv", "venv", "__pycache__", ".git"):
            assert d in DEFAULT_IGNORE_DIRS

    def test_optional_detection(self, tmp_path):
        self._write(tmp_path, "app.py", """\
            import requests

            try:
                import ujson
            except ImportError:
                pass
        """)
        result = scan(tmp_path, recursive=False, detect_optional=True)
        opt = {r.name for r in result.imports if r.is_optional}
        req = {r.name for r in result.imports if not r.is_optional}
        assert "ujson" in opt
        assert "requests" in req

    def test_syntax_error_skipped(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("def (", encoding="utf-8")
        result = scan(tmp_path, recursive=False)
        assert len(result.skipped_files) == 1

    def test_stdlib_fully_filtered(self, tmp_path):
        stdlib_imports = "\n".join(f"import {m}" for m in list(STDLIB)[:20])
        self._write(tmp_path, "stdlib_only.py", stdlib_imports)
        result = scan(tmp_path, recursive=False)
        assert not result.imports


# ─── resolver ────────────────────────────────────────────────────────────────

class TestResolver:
    def test_mapping_extra_known(self):
        # cv2 → opencv-python is in MAPPING_EXTRA
        result = resolve(["cv2"], use_network=False)
        assert result.resolved.get("cv2") == "opencv-python"
        assert result.source.get("cv2") == "extra"

    def test_unresolved_offline(self):
        result = resolve(["totally_fake_lib_xyz"], use_network=False)
        assert "totally_fake_lib_xyz" in result.unresolved

    def test_empty_input(self):
        result = resolve([], use_network=False)
        assert result.resolved == {}
        assert result.unresolved == []

    def test_progress_callback(self):
        calls = []
        resolve(["cv2", "does_not_exist_xyz"], use_network=False,
                on_progress=lambda imp, pkg, src: calls.append((imp, pkg, src)))
        assert len(calls) == 2
        resolved_call = next(c for c in calls if c[0] == "cv2")
        assert resolved_call[1] == "opencv-python"


# ─── writer ──────────────────────────────────────────────────────────────────

class TestWriter:
    def _make_result(self, resolved: dict, unresolved: list | None = None) -> ResolveResult:
        r = ResolveResult()
        r.resolved = resolved
        r.source = {k: "test" for k in resolved}
        r.unresolved = unresolved or []
        return r

    def test_basic_output(self):
        r = self._make_result({"requests": "requests", "flask": "Flask"})
        content = _build_content(r)
        assert "Flask\n" in content
        assert "requests\n" in content

    def test_deduplication(self):
        # Two imports mapping to the same PyPI package
        r = self._make_result({"win32api": "pywin32", "win32con": "pywin32"})
        content = _build_content(r)
        assert content.count("pywin32") == 1

    def test_unresolved_as_comments(self):
        r = self._make_result({}, ["mystery_lib"])
        content = _build_content(r)
        assert "# ⚠️  mystery_lib" in content

    def test_write_file(self, tmp_path):
        from reqbuild.writer import write_file
        r = self._make_result({"requests": "requests"})
        out = write_file(r, tmp_path / "requirements.txt")
        assert out.exists()
        assert "requests" in out.read_text()
