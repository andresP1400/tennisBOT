"""Check the working tree for accidentally committed secrets.

Run in CI or pre-commit. Exits non-zero if a suspected secret is found
in any file tracked by git or in the local working directory.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Common patterns for accidentally committed secrets.
# Each pattern must match the full secret value (>= 32 hex chars) so
# masked references like `9b49...f83` or `sk-…XXXX` do not trigger.
PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "the-odds-api key",
        re.compile(r"ODDS_API_KEY\s*=\s*([a-f0-9]{32,})", re.IGNORECASE),
    ),
    (
        "openai key",
        re.compile(r"sk-[A-Za-z0-9]{32,}"),
    ),
    (
        "anthropic key",
        re.compile(r"sk-ant-[A-Za-z0-9]{32,}"),
    ),
    (
        "generic api key=value",
        re.compile(
            r"(?i)(api[_-]?key|secret|token)\s*=\s*['\"]?([A-Za-z0-9_\-]{32,})['\"]?"
        ),
    ),
]

# Files / directories to skip
SKIP = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".next",
    "dist",
    "build",
    "docs/SECURITY.md",  # this file mentions patterns by design
    "scripts/security/check_no_secrets.py",
}


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    # Avoid `rglob` to skip node_modules quickly; walk manually with depth limit.
    stack = [ROOT]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name in SKIP:
                    continue
                stack.append(entry)
            elif entry.is_file():
                rel = entry.relative_to(ROOT).as_posix()
                if any(rel == s or rel.startswith(s + "/") for s in SKIP):
                    continue
                if entry.suffix not in {
                    ".py",
                    ".ts",
                    ".tsx",
                    ".js",
                    ".json",
                    ".yml",
                    ".yaml",
                    ".md",
                    ".txt",
                    ".env",
                }:
                    continue
                files.append(entry)
    return files


def main() -> int:
    findings: list[tuple[Path, str, str]] = []
    for path in iter_python_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                findings.append((path, label, match.group(0)[:60] + "..."))

    if findings:
        print("FAIL: suspected secrets found in working tree:")
        for path, label, snippet in findings:
            print(f"  {path.relative_to(ROOT)}: [{label}] {snippet}")
        return 1

    print("OK: no suspected secrets found in working tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
