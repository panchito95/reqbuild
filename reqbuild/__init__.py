"""
reqbuild – Automatically generate requirements.txt from your Python project.
"""

__version__ = "0.1.0"
__author__ = "reqbuild contributors"
__license__ = "MIT"

from .scanner import scan, ScanResult, ImportRecord, DEFAULT_IGNORE_DIRS
from .resolver import resolve, ResolveResult
from .writer import write_file, print_output

__all__ = [
    "scan",
    "resolve",
    "write_file",
    "print_output",
    "ScanResult",
    "ImportRecord",
    "ResolveResult",
    "DEFAULT_IGNORE_DIRS",
    "__version__",
]
