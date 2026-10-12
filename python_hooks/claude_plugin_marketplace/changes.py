from __future__ import annotations

import json
import subprocess
from pathlib import Path
from pathlib import PurePosixPath

from python_hooks.claude_plugin_marketplace._common import PLUGINS_DIR
from python_hooks.claude_plugin_marketplace.version import load_plugin_json

MARKETPLACE_PATH = '.claude-plugin/marketplace.json'
MANIFEST_PARTS = ('.claude-plugin', 'plugin.json')


def _diff_paths(root: Path, base_ref: str, head_ref: str, diff_filter: str) -> set:
    result = subprocess.run(
        ['git', 'diff', '-z', '--name-only', f'--diff-filter={diff_filter}', f'{base_ref}...{head_ref}'],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or 'git diff failed')
    return {p for p in result.stdout.split('\0') if p}


def changed_paths(root: Path, base_ref: str, head_ref: str) -> set:
    return _diff_paths(root, base_ref, head_ref, 'ACDMRTUXB')


def added_paths(root: Path, base_ref: str, head_ref: str) -> set:
    return _diff_paths(root, base_ref, head_ref, 'A')


def _version_only_change(root: Path, name: str, base_ref: str, head_ref: str) -> bool:
    base = load_plugin_json(root, name, base_ref)
    head = load_plugin_json(root, name, head_ref)
    if base is None or head is None:
        return False

    def strip(data: dict) -> dict:
        return {k: v for k, v in data.items() if k != 'version'}

    return base != head and strip(base) == strip(head)


def affected_plugins(root: Path, paths: set, base_ref: str, head_ref: str) -> set:
    affected = set()
    manifest_only: dict = {}
    for raw_path in paths:
        parts = PurePosixPath(raw_path).parts
        # loose docs like plugins/README.md excluded
        if len(parts) >= 3 and parts[0] == PLUGINS_DIR:
            name = parts[1]
            if parts[2:] == MANIFEST_PARTS:
                manifest_only.setdefault(name, True)
                continue
            manifest_only[name] = False
            affected.add(name)
    for name, only_manifest in manifest_only.items():
        if only_manifest and not _version_only_change(root, name, base_ref, head_ref):
            affected.add(name)
    return affected


def has_new_skill(plugin: str, added: set) -> bool:
    for raw_path in added:
        parts = PurePosixPath(raw_path).parts
        if len(parts) == 5 and parts[:3] == (PLUGINS_DIR, plugin, 'skills') and parts[4] == 'SKILL.md':
            return True
    return False


def has_new_agent(plugin: str, added: set) -> bool:
    for raw_path in added:
        parts = PurePosixPath(raw_path).parts
        if len(parts) == 4 and parts[:3] == (PLUGINS_DIR, plugin, 'agents') and parts[3].endswith('.md'):
            return True
    return False


def load_marketplace_at(root: Path, rev: str) -> dict | None:
    result = subprocess.run(
        ['git', 'show', f'{rev}:{MARKETPLACE_PATH}'],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f'{MARKETPLACE_PATH} at {rev} is not valid JSON')
    return data if isinstance(data, dict) else None
