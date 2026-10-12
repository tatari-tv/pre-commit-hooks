"""Check each plugin directory against its manifest."""
from __future__ import annotations

import json
from pathlib import Path

from python_hooks.marketplace._common import PLUGINS_DIR
from python_hooks.marketplace._common import repo_root
from python_hooks.marketplace._common import report


def check_plugins(plugins_root: Path, errors: list, warnings: list) -> None:
    if not plugins_root.is_dir():
        return
    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith('.'):
            continue
        name = plugin_dir.name
        manifest = plugin_dir / '.claude-plugin' / 'plugin.json'
        if not manifest.exists():
            errors.append(f'plugins/{name}/: missing .claude-plugin/plugin.json')
            continue
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
        except Exception as exc:
            errors.append(f'plugins/{name}/plugin.json: invalid JSON: {exc}')
            continue
        if data.get('name') != name:
            errors.append(f"plugins/{name}/plugin.json: name '{data.get('name')}' != directory '{name}'")

        skills_dir = plugin_dir / 'skills'
        if not skills_dir.is_dir():
            warnings.append(f'plugins/{name}/: no skills/ directory')
            continue
        for entry in sorted(skills_dir.iterdir()):
            where = f'plugins/{name}/skills/{entry.name}'
            if entry.is_symlink():
                errors.append(f'{where}: symlink not allowed')
            elif not entry.is_dir():
                warnings.append(f'{where}: not a directory')
            elif not (entry / 'SKILL.md').exists():
                errors.append(f'{where}: missing SKILL.md')


def main() -> int:
    errors: list = []
    warnings: list = []
    check_plugins(repo_root() / PLUGINS_DIR, errors, warnings)
    return report(errors, warnings)
