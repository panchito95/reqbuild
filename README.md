# reqbuild

> Reads your Python files and builds a `requirements.txt` automatically — without running your code or guessing package names.

[![PyPI version](https://badge.fury.io/py/reqbuild.svg)](https://pypi.org/project/reqbuild/)
[![Python](https://img.shields.io/pypi/pyversions/reqbuild.svg)](https://pypi.org/project/reqbuild/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- 🔍 **Reads your source files directly** — finds every `import` statement without executing your code
- 🌐 **Resolves real package names** — uses the [pipreqs](https://github.com/bndr/pipreqs) database + a live PyPI check as fallback
- 🚫 **No dependencies** — only the Python standard library, nothing extra to install
- 🔘 **Detects optional imports** — spots packages wrapped in `try/except ImportError` and marks them separately
- 🎛️ **Flexible CLI** — control scope, exclusions, output format, and more

---

## Installation

```bash
pip install reqbuild
```

---

## Quick Start

```bash
# Scan only the current folder
reqbuild generate

# Scan everything recursively
reqbuild generate -a

# Preview without writing a file
reqbuild generate -a --print
```

---

## CLI Reference

| Command / Flag | Description |
|----------------|-------------|
| `generate` | Scan the current folder `.py` files |
| `-a`, `--all` | Scan the current folder **and all subdirectories** recursively |
| `-e DIR` | Exclude a directory name (repeatable: `-e tests -e docs`) |
| `-ef FILE` | Exclude a specific filename (repeatable: `-ef conftest.py`) |
| `-o FILENAME` | Output filename (default: `requirements.txt`). Use `.in` for pip-compile |
| `--print` | Print resolved dependencies to stdout instead of writing a file |
| `--optional` | Detect imports inside `try/except ImportError` and list them as comments |
| `--no-network` | Offline mode — skip pipreqs download and PyPI checks |
| `-h`, `--help` | Show help for this command |

---

## Examples

```bash
# Generate requirements.in (pip-compile compatible)
reqbuild generate -a -o requirements.in

# Exclude test and docs directories
reqbuild generate -a -e tests -e docs

# Exclude a specific file
reqbuild generate -a -ef setup.py

# Detect optional imports (try/except ImportError)
reqbuild generate -a --optional

# Offline mode (no network calls)
reqbuild generate -a --no-network

# Preview all dependencies without writing
reqbuild generate -a --print
```

---

## Optional import detection

With `--optional`, reqbuild will detect imports wrapped in `try/except ImportError`:

```python
import requests          # required — goes to requirements.txt

try:
    import ujson         # optional — listed as a comment
except ImportError:
    import json as ujson
```

Output (`requirements.txt`):
```
requests

# ─── Optional dependencies (detected inside try/except ImportError) ───
# ujson
```

---

## Default ignored directories

reqbuild automatically ignores:

`.venv`, `venv`, `.env`, `env`, `__pycache__`, `.git`, `.hg`, `.svn`,
`.tox`, `.nox`, `dist`, `build`, `site-packages`, `.mypy_cache`,
`.pytest_cache`, `.ruff_cache`, `node_modules`, `.eggs`

Add more with `-e`:

```bash
reqbuild generate -a -e migrations -e fixtures
```

---

## Python API

reqbuild can also be used as a library:

```python
from reqbuild import scan, resolve, write_file

scan_result = scan(root=".", recursive=True, detect_optional=True)
external_names = [r.name for r in scan_result.imports]

resolve_result = resolve(external_names)
write_file(resolve_result, "requirements.txt")
```

---

## License

[MIT](LICENSE)
