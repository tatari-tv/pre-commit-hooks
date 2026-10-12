from __future__ import annotations

import json
import subprocess
from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import PLUGINS_DIR

BUMP_ORDER = ['patch', 'minor', 'major']


def manifest_rel(name: str) -> str:
    return f'{PLUGINS_DIR}/{name}/.claude-plugin/plugin.json'


def load_plugin_json(root: Path, name: str, rev: str | None = None) -> dict | None:
    if rev is None:
        path = root / manifest_rel(name)
        if not path.is_file():
            return None
        raw = path.read_text(encoding='utf-8')
    else:
        result = subprocess.run(
            ['git', 'show', f'{rev}:{manifest_rel(name)}'],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        raw = result.stdout
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_semver(version: str) -> tuple:
    parts = str(version).split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f'invalid semver: {version}')
    return tuple(int(p) for p in parts)


def max_bump(a: str | None, b: str | None) -> str | None:
    if a is None or b is None:
        return a or b
    return BUMP_ORDER[max(BUMP_ORDER.index(a), BUMP_ORDER.index(b))]


def bump_semver(version: str, bump: str) -> str:
    major, minor, patch = parse_semver(version)
    if bump == 'major':
        return f'{major + 1}.0.0'
    if bump == 'minor':
        return f'{major}.{minor + 1}.0'
    return f'{major}.{minor}.{patch + 1}'


def higher_version(required: str, current: str | None) -> str:
    if current is None or parse_semver(current) < parse_semver(required):
        return required
    return current


def write_version(path: Path, version: str, container: str | None = None) -> bool:
    data = json.loads(path.read_text(encoding='utf-8'))
    target = data[container] if container else data
    if target.get('version') == version:
        return False
    target['version'] = version
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return True
