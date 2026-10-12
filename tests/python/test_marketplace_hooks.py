from pathlib import Path

import toml
import yaml

ROOT = Path(__file__).resolve().parents[2]
HOOK_IDS = [
    'check-claude-plugin-names',
    'check-claude-plugin-marketplace',
    'no-em-dashes',
    'check-md-anchors',
    'check-claude-plugin-closure',
    'check-version-bumps',
]


def _hooks():
    entries = yaml.safe_load((ROOT / '.pre-commit-hooks.yaml').read_text())
    return {entry['id']: entry for entry in entries}


def test_every_hook_id_is_registered_and_a_script():
    scripts = toml.loads((ROOT / 'pyproject.toml').read_text())['project']['scripts']
    hooks = _hooks()
    for hook_id in HOOK_IDS:
        assert hook_id in hooks
        assert hooks[hook_id]['entry'] == hook_id
        assert hook_id in scripts


def test_hooks_run_on_whole_tree_even_for_deletions():
    hooks = _hooks()
    for hook_id in HOOK_IDS:
        assert hooks[hook_id]['pass_filenames'] is False
        assert hooks[hook_id]['always_run'] is True
        assert hooks[hook_id]['language'] == 'python'
