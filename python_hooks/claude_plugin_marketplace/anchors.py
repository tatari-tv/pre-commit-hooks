"""Fail on dangling markdown anchor links."""
from __future__ import annotations

import re
from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import repo_root
from python_hooks.claude_plugin_marketplace._common import report
from python_hooks.claude_plugin_marketplace._common import tracked_files

_FENCE_OPEN = re.compile(r'^ {0,3}(`{3,}|~{3,})')
_INLINE_CODE = re.compile(r'(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)')
_HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*$', re.MULTILINE)
_SETEXT = re.compile(r'^(?![#\s])(\S[^\n]*?)[ \t]*\n(?:=+|-+)[ \t]*$', re.MULTILINE)
_ANCHOR_LINK = re.compile(r'\]\(#([^)\s]+)\)')
_EMPHASIS = re.compile(r'(?<!\w)_+(.+?)_+(?!\w)')


def slugify(heading: str) -> str:
    text = _EMPHASIS.sub(r'\1', heading.strip().lower())
    slug = re.sub(r'[^\w\s-]', '', text)
    # One hyphen per space, as GitHub does.
    return re.sub(r'\s', '-', slug)


def _mask_code(text: str) -> tuple:
    prose: list = []
    links: list = []
    fence = None
    for line in text.split('\n'):
        if fence:
            if re.fullmatch(f'{re.escape(fence[0])}{{{len(fence)},}}', line.strip()):
                fence = None
            prose.append('')
            links.append('')
            continue
        opener = _FENCE_OPEN.match(line)
        if opener:
            fence = opener.group(1)
            prose.append('')
            links.append('')
            continue
        prose.append(line)
        links.append(_INLINE_CODE.sub(lambda m: ' ' * len(m.group(0)), line))
    return '\n'.join(prose), '\n'.join(links)


def _slug_set(prose: str) -> set:
    seen: dict = {}
    slugs = set()
    found = [(m.start(), m.group(2)) for m in _HEADING.finditer(prose)]
    found += [(m.start(), m.group(1)) for m in _SETEXT.finditer(prose)]
    for _, heading in sorted(found):
        base = slugify(heading)
        count = seen.get(base, 0)
        slugs.add(base if count == 0 else f'{base}-{count}')
        seen[base] = count + 1
    return slugs


def check_anchors(root: Path, files: list, errors: list) -> None:
    for rel in sorted(files):
        if not rel.endswith('.md'):
            continue
        try:
            text = (root / rel).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        prose, links = _mask_code(text)
        slugs = _slug_set(prose)
        for match in _ANCHOR_LINK.finditer(links):
            anchor = match.group(1)
            if anchor in slugs:
                continue
            lineno = links[: match.start()].count('\n') + 1
            errors.append(f'{rel}:{lineno}: anchor #{anchor} matches no heading')


def main() -> int:
    root = repo_root()
    errors: list = []
    check_anchors(root, tracked_files(root, errors), errors)
    return report(errors)
