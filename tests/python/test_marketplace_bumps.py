import json
import subprocess

import pytest

from python_hooks.claude_plugin_marketplace import bumps
from python_hooks.claude_plugin_marketplace import changes

GIT = ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com']


def _git(path, *args):
    subprocess.run([*GIT, '-C', str(path), *args], check=True, capture_output=True)


def _write(path, rel, text):
    target = path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')


def _manifest(name, version):
    return json.dumps({'name': name, 'description': f'{name} plugin', 'version': version}, indent=2) + '\n'


def _marketplace(version, names, pointers=()):
    plugins = [{'name': n, 'source': f'./plugins/{n}'} for n in names]
    plugins += [{'name': n, 'source': {'source': 'git-subdir', 'url': 'https://example.com/x.git'}} for n in pointers]
    return json.dumps({'name': 'demo', 'metadata': {'version': version}, 'plugins': plugins}, indent=2) + '\n'


def _commit(path, message='change'):
    _git(path, 'add', '-A')
    _git(path, 'commit', '-q', '-m', message)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, 'init', '-q', '-b', 'main')
    for name in ('alpha', 'beta'):
        _write(tmp_path, f'plugins/{name}/.claude-plugin/plugin.json', _manifest(name, '0.1.0'))
        _write(tmp_path, f'plugins/{name}/skills/one/SKILL.md', 'one\n')
    _write(tmp_path, '.claude-plugin/marketplace.json', _marketplace('1.0.0', ['alpha', 'beta']))
    _commit(tmp_path, 'base')
    _git(tmp_path, 'checkout', '-q', '-b', 'feature')
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _version(repo, name):
    return json.loads((repo / f'plugins/{name}/.claude-plugin/plugin.json').read_text())['version']


def _meta(repo):
    return json.loads((repo / '.claude-plugin/marketplace.json').read_text())['metadata']['version']


def _touch(repo, name, text='x\n'):
    _write(repo, f'plugins/{name}/notes.md', text)


def test_check_fails_when_a_changed_plugin_is_not_bumped(repo, capsys):
    _touch(repo, 'alpha')
    _commit(repo)
    assert bumps.check_main(['main']) == 1
    err = capsys.readouterr().err
    assert "plugin 'alpha'" in err
    assert 'compute-version-bump main' in err


def test_compute_then_check_passes(repo):
    _touch(repo, 'alpha')
    _commit(repo)
    assert bumps.compute_main(['main']) == 0
    assert _version(repo, 'alpha') == '0.1.1'
    assert _version(repo, 'beta') == '0.1.0'
    assert _meta(repo) == '1.0.1'
    _commit(repo, 'bump')
    assert bumps.check_main(['main']) == 0


def test_check_passes_when_no_plugin_changed(repo):
    _write(repo, 'README.md', 'hi\n')
    _commit(repo)
    assert bumps.check_main(['main']) == 0
    assert bumps.compute_main(['main']) == 0
    assert _meta(repo) == '1.0.0'


def test_rerun_after_second_change_bumps_only_the_new_plugin(repo):
    _touch(repo, 'alpha')
    _commit(repo)
    bumps.compute_main(['main'])
    _commit(repo, 'bump alpha')
    _touch(repo, 'beta')
    _commit(repo, 'change beta')
    bumps.compute_main(['main'])
    assert _version(repo, 'alpha') == '0.1.1'
    assert _version(repo, 'beta') == '0.1.1'
    assert _meta(repo) == '1.0.1'


def test_new_skill_after_patch_bump_upgrades_to_minor(repo):
    _touch(repo, 'alpha')
    _commit(repo)
    bumps.compute_main(['main'])
    _commit(repo, 'bump')
    _write(repo, 'plugins/alpha/skills/two/SKILL.md', 'two\n')
    _commit(repo, 'add skill')
    assert bumps.check_main(['main']) == 1
    bumps.compute_main(['main'])
    assert _version(repo, 'alpha') == '0.2.0'
    assert _meta(repo) == '1.1.0'
    _commit(repo, 'bump again')
    assert bumps.check_main(['main']) == 0


def test_new_agent_is_a_minor_bump(repo):
    _write(repo, 'plugins/alpha/agents/helper.md', 'agent\n')
    _commit(repo)
    bumps.compute_main(['main'])
    assert _version(repo, 'alpha') == '0.2.0'


def test_check_fails_patch_bump_when_skill_was_added(repo):
    _write(repo, 'plugins/alpha/skills/two/SKILL.md', 'two\n')
    _write(repo, 'plugins/alpha/.claude-plugin/plugin.json', _manifest('alpha', '0.1.1'))
    _write(repo, '.claude-plugin/marketplace.json', _marketplace('1.1.0', ['alpha', 'beta']))
    _commit(repo)
    assert bumps.check_main(['main']) == 1


def test_manual_major_bump_is_not_lowered(repo):
    _touch(repo, 'alpha')
    _write(repo, 'plugins/alpha/.claude-plugin/plugin.json', _manifest('alpha', '1.0.0'))
    _write(repo, '.claude-plugin/marketplace.json', _marketplace('2.0.0', ['alpha', 'beta']))
    _commit(repo)
    assert bumps.check_main(['main']) == 0
    assert bumps.compute_main(['main']) == 0
    assert _version(repo, 'alpha') == '1.0.0'
    assert _meta(repo) == '2.0.0'


def test_unchanged_rerun_leaves_manifests_byte_identical(repo):
    _touch(repo, 'alpha')
    _commit(repo)
    bumps.compute_main(['main'])
    plugin = repo / 'plugins/alpha/.claude-plugin/plugin.json'
    market = repo / '.claude-plugin/marketplace.json'
    before = (plugin.read_bytes(), market.read_bytes())
    assert bumps.compute_main(['main']) == 0
    assert (plugin.read_bytes(), market.read_bytes()) == before


def test_new_plugin_requires_initial_version_and_keeps_larger(repo):
    _write(repo, 'plugins/gamma/.claude-plugin/plugin.json', _manifest('gamma', '0.3.0'))
    _write(repo, 'plugins/delta/.claude-plugin/plugin.json', _manifest('delta', '0.0.1'))
    _write(repo, '.claude-plugin/marketplace.json', _marketplace('1.0.0', ['alpha', 'beta', 'gamma', 'delta']))
    _commit(repo)
    assert bumps.check_main(['main']) == 1
    bumps.compute_main(['main'])
    assert _version(repo, 'gamma') == '0.3.0'
    assert _version(repo, 'delta') == '0.1.0'
    assert _meta(repo) == '1.1.0'


def test_uncommitted_edit_to_other_marketplace_field_survives(repo):
    _touch(repo, 'alpha')
    _commit(repo)
    market = repo / '.claude-plugin/marketplace.json'
    data = json.loads(market.read_text())
    data['name'] = 'renamed'
    market.write_text(json.dumps(data, indent=2) + '\n')
    bumps.compute_main(['main'])
    after = json.loads(market.read_text())
    assert after['name'] == 'renamed'
    assert after['metadata']['version'] == '1.0.1'


def test_uncommitted_edit_to_other_manifest_field_survives(repo):
    _touch(repo, 'alpha')
    _commit(repo)
    plugin = repo / 'plugins/alpha/.claude-plugin/plugin.json'
    data = json.loads(plugin.read_text())
    data['description'] = 'edited'
    plugin.write_text(json.dumps(data, indent=2) + '\n')
    bumps.compute_main(['main'])
    after = json.loads(plugin.read_text())
    assert after['description'] == 'edited'
    assert after['version'] == '0.1.1'


def test_pointer_entry_without_version_is_tolerated(repo):
    _write(repo, '.claude-plugin/marketplace.json', _marketplace('1.0.0', ['alpha', 'beta'], pointers=['ext']))
    _commit(repo, 'add pointer')
    _git(repo, 'checkout', '-q', 'main')
    _git(repo, 'merge', '-q', '--ff-only', 'feature')
    _git(repo, 'checkout', '-q', '-b', 'second')
    _touch(repo, 'alpha')
    _commit(repo)
    assert bumps.check_main(['main']) == 1
    assert bumps.compute_main(['main']) == 0
    _commit(repo, 'bump')
    assert bumps.check_main(['main']) == 0


def test_deleted_plugin_does_not_crash_and_bumps_marketplace(repo):
    _git(repo, 'rm', '-rq', 'plugins/beta')
    _write(repo, '.claude-plugin/marketplace.json', _marketplace('1.0.0', ['alpha']))
    _commit(repo, 'remove beta')
    assert bumps.check_main(['main']) == 1
    assert bumps.compute_main(['main']) == 0
    assert _meta(repo) == '1.0.1'
    _commit(repo, 'bump')
    assert bumps.check_main(['main']) == 0


def test_version_only_manifest_change_is_not_affected(repo):
    _write(repo, 'plugins/alpha/.claude-plugin/plugin.json', _manifest('alpha', '0.1.1'))
    _commit(repo)
    paths = changes.changed_paths(repo, 'main', 'HEAD')
    assert changes.affected_plugins(repo, paths, 'main', 'HEAD') == set()


def test_description_only_manifest_change_is_affected(repo):
    data = json.loads((repo / 'plugins/alpha/.claude-plugin/plugin.json').read_text())
    data['description'] = 'new words'
    _write(repo, 'plugins/alpha/.claude-plugin/plugin.json', json.dumps(data, indent=2) + '\n')
    _commit(repo)
    paths = changes.changed_paths(repo, 'main', 'HEAD')
    assert changes.affected_plugins(repo, paths, 'main', 'HEAD') == {'alpha'}


def test_loose_file_under_plugins_is_not_a_plugin(repo):
    _write(repo, 'plugins/README.md', 'loose\n')
    _commit(repo)
    paths = changes.changed_paths(repo, 'main', 'HEAD')
    assert changes.affected_plugins(repo, paths, 'main', 'HEAD') == set()


def test_added_file_detection():
    added = {'plugins/a/skills/s/SKILL.md', 'plugins/a/agents/x.md', 'plugins/a/skills/s/extra.md'}
    assert changes.has_new_skill('a', added)
    assert changes.has_new_agent('a', added)
    assert not changes.has_new_skill('b', added)
    assert not changes.has_new_agent('a', {'plugins/a/agents/x.txt'})


def test_shallow_history_prints_fetch_hint(repo, tmp_path_factory, monkeypatch, capsys):
    _touch(repo, 'alpha')
    _commit(repo)
    clone = tmp_path_factory.mktemp('clone') / 'c'
    subprocess.run(
        ['git', 'clone', '-q', '--depth=1', '--branch', 'feature', f'file://{repo}', str(clone)],
        check=True,
        capture_output=True,
    )
    _git(clone, 'fetch', '-q', '--depth=1', 'origin', 'main:refs/remotes/origin/main')
    monkeypatch.chdir(clone)
    assert bumps.check_main([]) == 2
    assert 'fetch-depth: 0' in capsys.readouterr().err


def test_missing_base_marketplace_is_not_a_check_failure(repo):
    _git(repo, 'checkout', '-q', '--orphan', 'bare')
    _git(repo, 'rm', '-rfq', '.')
    _write(repo, 'README.md', 'x\n')
    _commit(repo, 'root')
    _git(repo, 'checkout', '-q', 'feature')
    _git(repo, 'checkout', '-q', '-b', 'topic')
    _touch(repo, 'alpha')
    _commit(repo)
    _git(repo, 'merge', '-q', '--allow-unrelated-histories', '-m', 'join', 'bare')
    assert bumps.check_main(['bare']) == 0
