"""Fail on em-dashes in tracked files."""
from __future__ import annotations

from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import repo_root
from python_hooks.claude_plugin_marketplace._common import report
from python_hooks.claude_plugin_marketplace._common import tracked_files

# Built, not inlined, to avoid self-flagging.
EM_DASH = chr(0x2014)
EM_DASH_ESCAPE = '\\' + 'u' + f'{0x2014:04x}'

_REMEDY = 'use a colon, comma, parens, or two sentences'


def check_dashes(root: Path, files: list, errors: list) -> None:
    for rel in sorted(files):
        try:
            text = (root / rel).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        if EM_DASH not in text and EM_DASH_ESCAPE not in text:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            literal = line.count(EM_DASH)
            if literal:
                errors.append(f'{rel}:{lineno}: {literal} em-dash (U+2014); {_REMEDY}')
            escaped = line.count(EM_DASH_ESCAPE)
            if escaped:
                errors.append(f'{rel}:{lineno}: {escaped} escaped em-dash ({EM_DASH_ESCAPE}); {_REMEDY}')


def main() -> int:
    root = repo_root()
    errors: list = []
    check_dashes(root, tracked_files(root, errors), errors)
    return report(errors)
