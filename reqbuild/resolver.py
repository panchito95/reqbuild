"""
resolver.py – Maps raw import names → PyPI package names.

Resolution order:
  1. MAPPING_EXTRA  (local hardcoded fallbacks for known gaps)
  2. pipreqs mapping (downloaded once, cached in memory)
  3. PyPI JSON API   (live check as last resort)
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field

PIPREQS_MAPPING_URL = (
    "https://raw.githubusercontent.com/bndr/pipreqs/master/pipreqs/mapping"
)

# Known imports that pipreqs mapping doesn't cover
MAPPING_EXTRA: dict[str, str] = {
    "win32api":      "pywin32",
    "win32con":      "pywin32",
    "win32process":  "pywin32",
    "win32ui":       "pywin32",
    "win32gui":      "pywin32",
    "win32print":    "pywin32",
    "win32security": "pywin32",
    "win32ts":       "pywin32",
    "pythoncom":     "pywin32",
    "gi":            "PyGObject",
    "wx":            "wxPython",
    "OpenGL":        "PyOpenGL",
    "yaml":          "PyYAML",
    "cv2":           "opencv-python",
    "sklearn":       "scikit-learn",
    "bs4":           "beautifulsoup4",
    "PIL":           "Pillow",
    "pkg_resources": "setuptools",
    "dotenv":        "python-dotenv",
    "usb":           "pyusb",
    "serial":        "pyserial",
    "dateutil":      "python-dateutil",
    "magic":         "python-magic",
    "Crypto":        "pycryptodome",
    "jwt":           "PyJWT",
    "google.cloud":  "google-cloud",
    "attr":          "attrs",
}


@dataclass
class ResolveResult:
    resolved: dict[str, str] = field(default_factory=dict)   # import → pypi_name
    source: dict[str, str] = field(default_factory=dict)      # import → "extra"|"pipreqs"|"pypi"
    unresolved: list[str] = field(default_factory=list)


def _load_pipreqs_mapping(timeout: int = 10) -> dict[str, str]:
    """Download pipreqs mapping file; return empty dict on failure."""
    mapping: dict[str, str] = {}
    try:
        with urllib.request.urlopen(PIPREQS_MAPPING_URL, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
    except Exception:
        return mapping

    # Auto-detect separator from first non-comment line
    sep = ":"
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sep = ":" if ":" in line else ("\t" if "\t" in line else " ")
        break

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(sep, 1)
        if len(parts) == 2:
            imp, pkg = parts[0].strip(), parts[1].strip()
            if imp and pkg:
                mapping[imp] = pkg

    return mapping


def _exists_on_pypi(name: str, timeout: int = 8) -> bool:
    """Check if *name* is a valid package on PyPI."""
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False


def resolve(
    import_names: list[str],
    use_network: bool = True,
    on_progress: "callable | None" = None,
) -> ResolveResult:
    """
    Resolve a list of import names to PyPI package names.

    Parameters
    ----------
    import_names : Unique external import names to resolve.
    use_network  : If False, skip both pipreqs download and PyPI checks.
    on_progress  : Optional callback(imp, pypi_name_or_None, source_str).
    """
    result = ResolveResult()

    # Build combined mapping (EXTRA is the baseline; pipreqs overrides where it knows better)
    pipreqs_mapping: dict[str, str] = {}
    if use_network:
        pipreqs_mapping = _load_pipreqs_mapping()

    combined = {**MAPPING_EXTRA, **pipreqs_mapping}  # pipreqs wins on overlap

    for imp in sorted(import_names):
        if imp in combined:
            pkg = combined[imp]
            src = "pipreqs" if imp in pipreqs_mapping else "extra"
            result.resolved[imp] = pkg
            result.source[imp] = src
            if on_progress:
                on_progress(imp, pkg, src)
        elif use_network and _exists_on_pypi(imp):
            result.resolved[imp] = imp
            result.source[imp] = "pypi"
            if on_progress:
                on_progress(imp, imp, "pypi")
        else:
            result.unresolved.append(imp)
            if on_progress:
                on_progress(imp, None, "unresolved")

    return result
