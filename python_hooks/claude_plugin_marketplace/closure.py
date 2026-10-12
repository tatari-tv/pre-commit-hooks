"""Forbid script-level references across plugins."""
from __future__ import annotations

import posixpath
import re
from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import PLUGINS_DIR
from python_hooks.claude_plugin_marketplace._common import repo_root
from python_hooks.claude_plugin_marketplace._common import report

_FENCE = re.compile(
    r'^[ \t]*(?P<ticks>(?P<ch>[`~])(?P=ch){2,})(?P<info>[^\n]*)\n(?P<body>.*?)(?:^[ \t]*(?P=ticks)(?P=ch)*[ \t]*$|\Z)',
    re.DOTALL | re.MULTILINE,
)

# Bare fence counts: conventionally shell.
_EXECUTABLE_FENCE_LANGS = {'', 'bash', 'sh', 'shell', 'console', 'zsh', 'fish', 'python', 'python3', 'py'}

# Whitelist stops match at path's end.
_SKILL_DIR_PATH = re.compile(r'CLAUDE_SKILL_DIR\}/([A-Za-z0-9._/-]+)')


def _executable_fences(text: str):
    for match in _FENCE.finditer(text):
        words = match.group('info').strip().lstrip('`').split()[:1]
        lang = words[0].lower() if words else ''
        if lang in _EXECUTABLE_FENCE_LANGS:
            yield match.group('body')


def _within(target: Path, base: Path) -> bool:
    return target == base or base in target.parents


def _plugin_and_skill(target: Path, plugins_root: Path):
    if not _within(target, plugins_root):
        return None, None
    parts = target.relative_to(plugins_root).parts
    if len(parts) >= 3 and parts[1] == 'skills':
        return parts[0], parts[2]
    return None, None


def _cross_plugin_message(other_skill: str, owners: set, this_plugin: str) -> str:
    where = ', '.join(f'plugins/{o}/' for o in sorted(owners))
    suggest = sorted(owners)[0]
    return (
        f"sibling path reaches '{other_skill}' in {where}, not plugins/{this_plugin}/; "
        f"co-locate the skills, or invoke '{suggest}:{other_skill}' in prose"
    )


def _skill_dirs(plugins_root: Path):
    if not plugins_root.is_dir():
        return
    for plugin_dir in sorted(plugins_root.iterdir()):
        skills_dir = plugin_dir / 'skills'
        if not plugin_dir.is_dir() or plugin_dir.name.startswith('.') or not skills_dir.is_dir():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir():
                yield plugin_dir, skill_dir


def _skill_to_plugin(plugins_root: Path) -> dict:
    # Set: one name, several plugins.
    mapping: dict = {}
    for plugin_dir, skill_dir in _skill_dirs(plugins_root):
        mapping.setdefault(skill_dir.name, set()).add(plugin_dir.name)
    return mapping


def _script_texts(skill_dir: Path):
    for path in sorted(skill_dir.rglob('*')):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        if path.suffix.lower() == '.md':
            for i, block in enumerate(_executable_fences(text)):
                yield f'{path}#block{i}', block
        else:
            yield str(path), text


def _sibling_path_error(rel: str, skill_dir: Path, plugin_dir: Path, plugins_root: Path, skill_owner: dict):
    if '..' not in rel.split('/'):
        return None
    target = Path(posixpath.normpath(posixpath.join(skill_dir.as_posix(), rel)))
    this_plugin = plugin_dir.name

    if not _within(target, plugin_dir):
        owner, other_skill = _plugin_and_skill(target, plugins_root)
        if owner and owner != this_plugin:
            return _cross_plugin_message(other_skill, {owner}, this_plugin)
        return f"path '{rel}' resolves outside plugins/{this_plugin}/"

    _, other_skill = _plugin_and_skill(target, plugins_root)
    if other_skill is None or (plugin_dir / 'skills' / other_skill).is_dir():
        return None
    owners = skill_owner.get(other_skill) or set()
    if owners and this_plugin not in owners:
        return _cross_plugin_message(other_skill, owners, this_plugin)
    return f"sibling path '{rel}' resolves to a missing skill"


def _prefix_pattern(skill_owner: dict):
    # Roster only; avoids `repo:org/name` matches.
    pairs = sorted(f'{plugin}:{skill}' for skill, plugins in skill_owner.items() for plugin in plugins)
    if not pairs:
        return None
    return re.compile(r'(?<![A-Za-z0-9_-])(' + '|'.join(re.escape(p) for p in pairs) + r')(?![A-Za-z0-9_-])')


def check_closure(plugins_root: Path, errors: list) -> None:
    if not plugins_root.is_dir():
        return
    skill_owner = _skill_to_plugin(plugins_root)
    prefix_pattern = _prefix_pattern(skill_owner)
    if prefix_pattern is None:
        return

    for plugin_dir, skill_dir in _skill_dirs(plugins_root):
        for label, text in _script_texts(skill_dir):
            for match in _SKILL_DIR_PATH.finditer(text):
                problem = _sibling_path_error(match.group(1), skill_dir, plugin_dir, plugins_root, skill_owner)
                if problem:
                    errors.append(f'{label}: {problem}')
            for match in prefix_pattern.finditer(text):
                ref_plugin, ref_skill = match.group(1).split(':', 1)
                if ref_plugin != plugin_dir.name:
                    errors.append(f"{label}: reference to '{ref_plugin}:{ref_skill}' crosses plugins; co-locate the skills")


def main() -> int:
    errors: list = []
    check_closure(repo_root() / PLUGINS_DIR, errors)
    return report(errors)
