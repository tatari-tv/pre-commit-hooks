"""Check marketplace.json entries against plugins/."""
from __future__ import annotations

import json
from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import is_pointer
from python_hooks.claude_plugin_marketplace._common import PLUGINS_DIR
from python_hooks.claude_plugin_marketplace._common import repo_root
from python_hooks.claude_plugin_marketplace._common import report


def check_marketplace(root: Path, plugins_root: Path, errors: list) -> None:
    manifest = root / '.claude-plugin' / 'marketplace.json'
    if not manifest.exists():
        errors.append('missing .claude-plugin/marketplace.json')
        return
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'marketplace.json: invalid JSON: {exc}')
        return

    listed = set()
    for plugin in data.get('plugins', []):
        name = plugin.get('name', '<unnamed>')
        listed.add(name)
        if is_pointer(plugin):
            continue
        source = plugin.get('source')
        if not isinstance(source, str) or not source.strip():
            errors.append(f"marketplace.json: plugin '{name}' has no valid source")
            continue
        target = (root / source).resolve()
        if '..' in Path(source).parts or not target.is_relative_to(root.resolve()):
            errors.append(f"marketplace.json: plugin '{name}' source '{source}' leaves the repo")
        elif not target.is_dir():
            errors.append(f"marketplace.json: plugin '{name}' source '{source}' not found")

    if plugins_root.is_dir():
        for entry in sorted(plugins_root.iterdir()):
            if entry.is_dir() and not entry.name.startswith('.') and entry.name not in listed:
                errors.append(f"marketplace.json: plugin '{entry.name}' not listed")


def main() -> int:
    root = repo_root()
    errors: list = []
    check_marketplace(root, root / PLUGINS_DIR, errors)
    return report(errors)
