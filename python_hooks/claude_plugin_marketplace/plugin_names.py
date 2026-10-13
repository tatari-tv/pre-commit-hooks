"""Check each plugin directory against its manifest."""
from __future__ import annotations

import json
import os
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
    if data.get('name') != name:
        errors.append(f"plugins/{name}/plugin.json: name '{data.get('name')}' != directory '{name}'")


def _check_skills(plugin_dir: Path, errors: list, warnings: list) -> None:
    name = plugin_dir.name
    skills_dir = plugin_dir / 'skills'
    if skills_dir.is_symlink():
        errors.append(f'plugins/{name}/skills: symlink not allowed')
        return
    if not skills_dir.is_dir():
        warnings.append(f'plugins/{name}/: no skills/ directory')
        return
    for dirpath, dirnames, filenames in os.walk(skills_dir):
        for entry in sorted(dirnames + filenames):
            path = Path(dirpath) / entry
            where = f'plugins/{name}/skills/{path.relative_to(skills_dir).as_posix()}'
            if path.is_symlink():
                errors.append(f'{where}: symlink not allowed')
            elif Path(dirpath) == skills_dir and not path.is_dir():
                warnings.append(f'{where}: not a directory')


def check_plugins(plugins_root: Path, errors: list, warnings: list) -> None:
    if not plugins_root.is_dir():
        return
    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith('.'):
            continue
        _check_manifest(plugin_dir, errors)
        _check_skills(plugin_dir, errors, warnings)


def main() -> int:
    errors: list = []
    warnings: list = []
    check_plugins(repo_root() / PLUGINS_DIR, errors, warnings)
    return report(errors, warnings)
