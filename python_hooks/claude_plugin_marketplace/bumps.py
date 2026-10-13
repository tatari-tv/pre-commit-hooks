from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from python_hooks.claude_plugin_marketplace._common import repo_root
from python_hooks.claude_plugin_marketplace.changes import added_paths
from python_hooks.claude_plugin_marketplace.changes import affected_plugins
from python_hooks.claude_plugin_marketplace.changes import changed_paths
from python_hooks.claude_plugin_marketplace.changes import has_new_agent
from python_hooks.claude_plugin_marketplace.changes import has_new_skill
from python_hooks.claude_plugin_marketplace.changes import load_marketplace_at
from python_hooks.claude_plugin_marketplace.changes import MARKETPLACE_PATH
from python_hooks.claude_plugin_marketplace.version import bump_semver
from python_hooks.claude_plugin_marketplace.version import higher_version
from python_hooks.claude_plugin_marketplace.version import load_plugin_json
from python_hooks.claude_plugin_marketplace.version import manifest_rel
from python_hooks.claude_plugin_marketplace.version import max_bump
from python_hooks.claude_plugin_marketplace.version import parse_semver
from python_hooks.claude_plugin_marketplace.version import write_version

NEW_PLUGIN_VERSION = '0.1.0'
META_LABEL = 'metadata.version'
UVX_SOURCE = 'git+https://github.com/tatari-tv/pre-commit-hooks@<rev>'


def _parse_args(description: str, argv: list | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('base_ref', nargs='?', default='origin/main')
    parser.add_argument('head_ref', nargs='?', default='HEAD')
    return parser.parse_args(argv)


def _fail(exc: Exception) -> int:
    message = str(exc)
    print(f'error: {message}', file=sys.stderr)
    if 'no merge base' in message:
        print('fetch full history (fetch-depth: 0)', file=sys.stderr)
    return 2


def _require_inside(root: Path, path: Path) -> None:
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'{path.relative_to(root)} is a symlink or leaves the repo; refusing to write')


def _version_of(data: dict | None) -> str | None:
    return data.get('version') if data else None


def plan_bumps(root: Path, base_ref: str, head_ref: str) -> tuple | None:
    affected = affected_plugins(root, changed_paths(root, base_ref, head_ref), base_ref, head_ref)
    base_data = load_marketplace_at(root, base_ref)
    if base_data is None:
        return None
    if not affected:
        return set(), {}, None

    base_meta = (base_data.get('metadata') or {}).get('version')
    if base_meta is None:
        raise RuntimeError(f'{MARKETPLACE_PATH} at {base_ref} has no metadata.version')

    added = added_paths(root, base_ref, head_ref)
    base_names = {p.get('name') for p in base_data.get('plugins', []) if isinstance(p, dict)}
    required: dict = {}
    level = None
    for name in sorted(affected):
        if name not in base_names:
            required[name] = NEW_PLUGIN_VERSION
            level = max_bump(level, 'minor')
            continue
        bump = 'minor' if has_new_skill(name, added) or has_new_agent(name, added) else 'patch'
        level = max_bump(level, bump)
        base_manifest = load_plugin_json(root, name, base_ref)
        if base_manifest is not None:
            base_version = _version_of(base_manifest)
            label = f"plugin '{name}' version at {base_ref}"
            required[name] = bump_semver(base_version, bump, label) if base_version else NEW_PLUGIN_VERSION
    return affected, required, bump_semver(base_meta, level, META_LABEL) if level else None


def check_main(argv: list | None = None) -> int:
    args = _parse_args('Fail when changed plugins lack a version bump.', argv)
    root = repo_root()
    try:
        plan = plan_bumps(root, args.base_ref, args.head_ref)
        if plan is None:
            print(f'note: {MARKETPLACE_PATH} not found at {args.base_ref}; skipping check', file=sys.stderr)
            return 0
        if not plan[0]:
            return 0
        _, required_versions, required_meta = plan
        head_data = load_marketplace_at(root, args.head_ref)
        if head_data is None:
            print(f'error: {MARKETPLACE_PATH} not found at {args.head_ref}', file=sys.stderr)
            return 1

        errors = []
        for name, required in sorted(required_versions.items()):
            manifest = load_plugin_json(root, name, args.head_ref)
            if manifest is None:
                continue
            current = _version_of(manifest)
            if current is None or parse_semver(current, f"plugin '{name}' version") < parse_semver(required):
                errors.append(f"  plugin '{name}' is {current}, needs at least {required}")
        current_meta = (head_data.get('metadata') or {}).get('version')
        if required_meta and (current_meta is None or parse_semver(current_meta, META_LABEL) < parse_semver(required_meta)):
            errors.append(f'  metadata.version is {current_meta}, needs at least {required_meta}')
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return _fail(exc)

    if errors:
        print('Version bump required:', file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        print(f'\nRun: uvx --from {UVX_SOURCE} compute-version-bump {args.base_ref}', file=sys.stderr)
        return 1
    return 0


def compute_main(argv: list | None = None) -> int:
    args = _parse_args('Raise changed plugin versions in place.', argv)
    root = repo_root()
    try:
        plan = plan_bumps(root, args.base_ref, args.head_ref)
        if plan is None:
            print(f'error: {MARKETPLACE_PATH} not found at {args.base_ref}', file=sys.stderr)
            return 1
        affected, required_versions, required_meta = plan
        if not affected:
            return 0

        writes: list = []
        for name, required in sorted(required_versions.items()):
            path = root / manifest_rel(name)
            if not path.is_file():
                continue
            _require_inside(root, path)
            current = _version_of(load_plugin_json(root, name))
            writes.append((path, higher_version(required, current, f"plugin '{name}' version"), None, current))

        marketplace = root / MARKETPLACE_PATH
        if not marketplace.is_file():
            print(f'error: {MARKETPLACE_PATH} not found', file=sys.stderr)
            return 1
        _require_inside(root, marketplace)
        data = json.loads(marketplace.read_text(encoding='utf-8'))
        if not isinstance(data.get('metadata'), dict):
            print(f'error: {MARKETPLACE_PATH} has no metadata object', file=sys.stderr)
            return 1
        current_meta = data['metadata'].get('version')
        writes.append((marketplace, higher_version(required_meta, current_meta, META_LABEL), 'metadata', current_meta))

        for path, new_version, container, current in writes:
            if write_version(path, new_version, container):
                print(f'{path.relative_to(root)}: {current} -> {new_version}')
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return _fail(exc)
    return 0
