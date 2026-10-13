"""Check each plugin directory against its manifest."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import PLUGINS_DIR
from python_hooks.claude_plugin_marketplace._common import repo_root
from python_hooks.claude_plugin_marketplace._common import report


def _check_manifest(plugin_dir: Path, errors: list) -> None:
    name = plugin_dir.name
    manifest = plugin_dir / '.claude-plugin' / 'plugin.json'
    if not manifest.exists():
        errors.append(f'plugins/{name}/: missing .claude-plugin/plugin.json')
        return
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'plugins/{name}/plugin.json: invalid JSON: {exc}')
        return
    if not isinstance(data, dict):
        errors.append(f'plugins/{name}/plugin.json: expected a JSON object, got {type(data).__name__}')
        return
    if data.get('name') != name:
        errors.append(f"plugins/{name}/plugin.json: name '{data.get('name')}' != directory '{name}'")


def _ignored(parent: Path, names: list) -> set:
    if not names:
        return set()
    try:
        result = subprocess.run(
            ['git', 'check-ignore', '--stdin'],
            cwd=parent,
            input='\n'.join(f'{n}/' for n in names),
            capture_output=True,
            text=True,
        )
    except OSError:
        return set()
    return {line.rstrip('/') for line in result.stdout.splitlines()}


def _check_skills(plugin_dir: Path, errors: list, warnings: list) -> None:
    name = plugin_dir.name
    skills_dir = plugin_dir / 'skills'
    if skills_dir.is_symlink():
        errors.append(f'plugins/{name}/skills: symlink not allowed')
        return
    if not skills_dir.is_dir():
        warnings.append(f'plugins/{name}/: no skills/ directory')
        return
    entries = sorted(skills_dir.iterdir())
    for entry in entries:
        if not entry.is_symlink() and not entry.is_dir():
            warnings.append(f'plugins/{name}/skills/{entry.name}: not a directory')
    # skill-lint already covers visible dirs
    candidates = [e.name for e in entries if e.is_dir() and not e.is_symlink() and not (e / 'SKILL.md').exists()]
    ignored = _ignored(skills_dir, candidates)
    for dir_name in candidates:
        if dir_name.startswith('.') or dir_name in ignored:
            errors.append(f'plugins/{name}/skills/{dir_name}: missing SKILL.md')


def _check_symlinks(plugins_root: Path, errors: list) -> None:
    # mirrors old CI find scope
    for dirpath, dirnames, filenames in os.walk(plugins_root):
        for entry in sorted(dirnames + filenames):
            path = Path(dirpath) / entry
            where = f'plugins/{path.relative_to(plugins_root).as_posix()}'
            if path.is_symlink() and '/skills/' in where:
                errors.append(f'{where}: symlink not allowed')


def check_plugins(plugins_root: Path, errors: list, warnings: list) -> None:
    if not plugins_root.is_dir():
        return
    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith('.'):
            continue
        _check_manifest(plugin_dir, errors)
        _check_skills(plugin_dir, errors, warnings)
    _check_symlinks(plugins_root, errors)


def main() -> int:
    errors: list = []
    warnings: list = []
    check_plugins(repo_root() / PLUGINS_DIR, errors, warnings)
    return report(errors, warnings)
