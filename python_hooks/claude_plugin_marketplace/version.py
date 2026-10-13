from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import PLUGINS_DIR

BUMP_ORDER = ['patch', 'minor', 'major']
SEMVER = re.compile(r'(\d+)\.(\d+)\.(\d+)', re.ASCII)


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
        data = None
    if not isinstance(data, dict):
        raise ValueError(f'{manifest_rel(name)} at {rev or "worktree"} is not a valid JSON object')
    return data


def parse_semver(version: str, label: str = 'version') -> tuple:
    match = SEMVER.fullmatch(str(version))
    if not match:
        raise ValueError(f'{label} {version!r} is not X.Y.Z (pre-release and build suffixes are unsupported)')
    return tuple(int(p) for p in match.groups())


def max_bump(a: str | None, b: str | None) -> str | None:
    return max(filter(None, (a, b)), key=BUMP_ORDER.index, default=None)


def bump_semver(version: str, bump: str, label: str = 'version') -> str:
    major, minor, patch = parse_semver(version, label)
    if bump == 'major':
        return f'{major + 1}.0.0'
    if bump == 'minor':
        return f'{major}.{minor + 1}.0'
    return f'{major}.{minor}.{patch + 1}'


def higher_version(required: str, current: str | None, label: str = 'version') -> str:
    if current is None or parse_semver(current, label) < parse_semver(required):
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
