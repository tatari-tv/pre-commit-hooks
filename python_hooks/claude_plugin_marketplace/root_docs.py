"""Root agent docs must be real files."""
from __future__ import annotations

from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import repo_root
from python_hooks.claude_plugin_marketplace._common import report

ROOT_DOCS = ('CLAUDE.md', 'AGENTS.md')


def check_root_docs(root: Path, errors: list) -> None:
    for doc in ROOT_DOCS:
        if (root / doc).is_symlink():
            errors.append(f'{doc}: must be a regular file, not a symlink')


def main() -> int:
    errors: list = []
    check_root_docs(repo_root(), errors)
    return report(errors)
