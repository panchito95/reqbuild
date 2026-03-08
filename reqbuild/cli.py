"""
cli.py – Command-line interface for reqbuild.

Usage
-----
  reqbuild generate              # scan only current folder
  reqbuild generate -a           # scan recursively
  reqbuild generate -e tests -e docs
  reqbuild generate -ef setup.py
  reqbuild generate -o requirements.in
  reqbuild generate --print
  reqbuild generate --optional   # also detect try/except ImportError imports
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .resolver import resolve
from .scanner import scan
from .writer import print_output, write_file

# ─── ANSI colours (disabled on Windows unless ANSICON / WT is present) ───────
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


GREEN  = lambda t: _c("32", t)  # noqa: E731
YELLOW = lambda t: _c("33", t)  # noqa: E731
CYAN   = lambda t: _c("36", t)  # noqa: E731
BOLD   = lambda t: _c("1",  t)  # noqa: E731
DIM    = lambda t: _c("2",  t)  # noqa: E731


# ─── Shared argument definitions ─────────────────────────────────────────────

def _add_generate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-a", "--all",
        dest="recursive",
        action="store_true",
        default=False,
        help="Scan the current folder AND all subdirectories recursively.",
    )
    parser.add_argument(
        "-e", "--exclude",
        dest="exclude_dirs",
        metavar="DIR",
        action="append",
        default=[],
        help=(
            "Exclude a directory name from scanning. "
            "Can be repeated: -e tests -e docs"
        ),
    )
    parser.add_argument(
        "-ef", "--exclude-file",
        dest="exclude_files",
        metavar="FILE",
        action="append",
        default=[],
        help=(
            "Exclude a specific filename from scanning. "
            "Can be repeated: -ef conftest.py -ef setup.py"
        ),
    )
    parser.add_argument(
        "-o", "--output",
        dest="output",
        metavar="FILENAME",
        default="requirements.txt",
        help=(
            "Output filename (default: requirements.txt). "
            "Use .in for pip-compile compatible format."
        ),
    )
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        default=False,
        help="Print resolved dependencies to stdout instead of writing a file.",
    )
    parser.add_argument(
        "--optional",
        dest="detect_optional",
        action="store_true",
        default=False,
        help=(
            "Also detect imports inside try/except ImportError blocks "
            "and mark them as optional in the output."
        ),
    )
    parser.add_argument(
        "--no-network",
        dest="no_network",
        action="store_true",
        default=False,
        help=(
            "Skip network calls (pipreqs download + PyPI check). "
            "Only MAPPING_EXTRA and the local mapping will be used."
        ),
    )


# ─── The generate command ─────────────────────────────────────────────────────

def cmd_generate(args: argparse.Namespace) -> int:
    root = Path(".").resolve()
    recursive: bool = args.recursive
    exclude_dirs: list[str] = args.exclude_dirs
    exclude_files: list[str] = args.exclude_files
    output: str = args.output
    print_only: bool = args.print_only
    detect_optional: bool = args.detect_optional
    use_network: bool = not args.no_network

    # ── Banner ───────────────────────────────────────────────────────────────
    print(BOLD(f"\n  reqbuild v{__version__}"))
    print(DIM("  ─" * 26))

    mode = "recursive" if recursive else "top-level only"
    print(f"  📂 Root      : {root}")
    print(f"  🔍 Mode      : {mode}")
    if exclude_dirs:
        print(f"  🚫 Excl. dirs: {', '.join(exclude_dirs)}")
    if exclude_files:
        print(f"  🚫 Excl. files: {', '.join(exclude_files)}")
    print()

    # ── Scan ─────────────────────────────────────────────────────────────────
    scan_result = scan(
        root=root,
        recursive=recursive,
        extra_ignore_dirs=exclude_dirs,
        extra_ignore_files=exclude_files,
        detect_optional=detect_optional,
    )

    n_files = len(scan_result.scanned_files)
    n_skipped = len(scan_result.skipped_files)
    print(f"  📄 Scanned   : {n_files} file(s)", end="")
    if n_skipped:
        print(f"  {YELLOW(f'({n_skipped} skipped)')}", end="")
    print()

    if scan_result.skipped_files:
        for msg in scan_result.skipped_files:
            print(f"    {YELLOW('⚠')}  {msg}")

    # ── Collect unique external imports ──────────────────────────────────────
    all_records = scan_result.imports
    unique_names: list[str] = sorted({r.name for r in all_records})

    optional_names: set[str] = set()
    if detect_optional:
        optional_names = {r.name for r in all_records if r.is_optional}

    required_names = [n for n in unique_names if n not in optional_names]

    total_unique = len(unique_names)
    print(f"  📦 External  : {total_unique} unique import(s) found")
    if detect_optional and optional_names:
        print(f"  🔘 Optional  : {len(optional_names)} import(s) inside try/except ImportError")
    print()

    if not unique_names:
        print(GREEN("  ✅ No external dependencies found."))
        return 0

    # ── Resolve ──────────────────────────────────────────────────────────────
    if use_network:
        print("  🌐 Downloading pipreqs mapping...", end=" ", flush=True)

    col_w = max((len(n) for n in unique_names), default=20) + 2

    def _on_progress(imp: str, pkg: str | None, source: str) -> None:
        if pkg is None:
            indicator = YELLOW("⚠")
            detail = YELLOW("REVIEW MANUALLY")
        else:
            indicator = GREEN("✓")
            detail = f"{pkg}  {DIM(f'({source})')}"
        print(f"    {indicator}  {imp:<{col_w}} → {detail}")

    if use_network:
        # Print newline after the "Downloading..." message before progress starts
        print()

    resolve_result = resolve(
        import_names=unique_names,
        use_network=use_network,
        on_progress=_on_progress,
    )

    # ── Summary ──────────────────────────────────────────────────────────────
    n_resolved = len(resolve_result.resolved)
    n_unique_pkgs = len(set(resolve_result.resolved.values()))
    n_unresolved = len(resolve_result.unresolved)

    print()
    print(DIM("  ─" * 26))
    print(f"  {GREEN('✓')} Resolved     : {n_resolved} imports → {n_unique_pkgs} unique package(s)")
    if n_unresolved:
        print(f"  {YELLOW('⚠')} Unresolved   : {n_unresolved}  (see comments in output)")

    # Separate optional resolved names
    opt_resolved_names: list[str] | None = None
    if detect_optional and optional_names:
        opt_resolved_names = sorted(optional_names & set(resolve_result.resolved.keys()))

    # ── Output ───────────────────────────────────────────────────────────────
    if print_only:
        print()
        print_output(resolve_result, opt_resolved_names)
    else:
        out_path = write_file(resolve_result, output, opt_resolved_names)
        print(f"  📁 Saved to  : {out_path}")

    print()
    return 0


# ─── Root parser ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reqbuild",
        description=(
            "reqbuild – Reads your Python files and builds a requirements.txt automatically\n"
            "           without running your code or guessing package names.\n\n"
            "Commands / Flags:\n"
            "  generate            Scan the current folder .py files\n"
            "  -a, --all           Scan the current folder and all subdirectories recursively\n"
            "  -e DIR              Exclude a directory name (repeatable: -e tests -e docs)\n"
            "  -ef FILE            Exclude a specific filename (repeatable: -ef conftest.py)\n"
            "  -o FILENAME         Output filename (default: requirements.txt)\n"
            "                        Use .in for pip-compile compatible format\n"
            "  --print             Print resolved dependencies instead of writing a file\n"
            "  --optional          Detect imports inside try/except ImportError as comments\n"
            "  --no-network        Offline mode — skip pipreqs download and PyPI checks\n"
            "  -h, --help          Show this help message"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  reqbuild generate                  # scan .py files in current folder\n"
            "  reqbuild generate -a               # scan all subdirectories too\n"
            "  reqbuild generate -a -e tests      # exclude 'tests' folder\n"
            "  reqbuild generate -o req.in        # pip-compile compatible output\n"
            "  reqbuild generate --print          # preview without writing\n"
            "  reqbuild generate --optional       # include try/except imports as comments\n"
            "  reqbuild generate --no-network     # offline mode\n"
        ),
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ── generate ─────────────────────────────────────────────────────────────
    gen_parser = subparsers.add_parser(
        "generate",
        aliases=["gen"],
        help="Scan the current folder .py files and generate a requirements file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Scan the current folder .py files and generate a requirements file.\n\n"
            "By default only the top-level folder is scanned. Use -a to go recursive."
        ),
    )
    _add_generate_args(gen_parser)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in ("generate", "gen"):
        return cmd_generate(args)

    # No subcommand → show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
