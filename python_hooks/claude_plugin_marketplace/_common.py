from __future__ import annotations

import subprocess
from pathlib import Path

PLUGINS_DIR = 'plugins'


def repo_root() -> Path:
    result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit('error: not inside a git repository')
    return Path(result.stdout.strip())


def is_pointer(entry: dict) -> bool:
    return isinstance(entry.get('source'), dict)


def tracked_files(root: Path, errors: list) -> list:
    try:
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=root, capture_output=True, text=True)
    except FileNotFoundError:
        errors.append('git not found')
        return []
    if result.returncode != 0:
        errors.append(f'git ls-files failed: {result.stderr.strip()}')
        return []
    return [p for p in result.stdout.split('\0') if p]


def report(errors: list, warnings: list | None = None) -> int:
    for warning in warnings or []:
        print(f'warning: {warning}')
    for error in errors:
        print(f'error: {error}')
    return 1 if errors else 0
