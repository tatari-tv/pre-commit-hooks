"""Fail on dangling markdown anchor links."""
from __future__ import annotations

import re
from pathlib import Path

from python_hooks.marketplace._common import repo_root
from python_hooks.marketplace._common import report
from python_hooks.marketplace._common import tracked_files

_FENCE = re.compile(r'```.*?```', re.DOTALL)
_HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*$', re.MULTILINE)
_ANCHOR_LINK = re.compile(r'\]\(#([^)\s]+)\)')
_DISAMBIGUATOR = re.compile(r'-\d+$')


def slugify(heading: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', heading.strip().lower())
    # One hyphen per space, as GitHub does.
    return re.sub(r'\s', '-', slug)


def check_anchors(root: Path, files: list, errors: list) -> None:
    for rel in sorted(files):
        if not rel.endswith('.md'):
            continue
        try:
            text = (root / rel).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        body = _FENCE.sub(lambda m: '\n' * m.group(0).count('\n'), text)
        slugs = {slugify(m.group(2)) for m in _HEADING.finditer(body)}
        if not slugs:
            continue
        for match in _ANCHOR_LINK.finditer(body):
            anchor = match.group(1)
            if anchor in slugs or _DISAMBIGUATOR.sub('', anchor) in slugs:
                continue
            lineno = body[: match.start()].count('\n') + 1
            errors.append(f'{rel}:{lineno}: anchor #{anchor} matches no heading')


def main() -> int:
    root = repo_root()
    errors: list = []
    check_anchors(root, tracked_files(root, errors), errors)
    return report(errors)
