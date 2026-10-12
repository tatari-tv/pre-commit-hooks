import json

from python_hooks.claude_plugin_marketplace import marketplace_entries as entries


def _repo(tmp_path, plugins, dirs=()):
    (tmp_path / '.claude-plugin').mkdir()
    (tmp_path / '.claude-plugin' / 'marketplace.json').write_text(json.dumps({'plugins': plugins}))
    for name in dirs:
        (tmp_path / 'plugins' / name).mkdir(parents=True)


def _check(tmp_path):
    errors = []
    entries.check_marketplace(tmp_path, tmp_path / 'plugins', errors)
    return errors


def test_listed_plugin_with_directory_passes(tmp_path):
    _repo(tmp_path, [{'name': 'alpha', 'source': './plugins/alpha'}], dirs=['alpha'])
    assert _check(tmp_path) == []


def test_missing_marketplace_file_is_flagged(tmp_path):
    assert 'missing .claude-plugin/marketplace.json' in _check(tmp_path)[0]


def test_invalid_json_is_flagged(tmp_path):
    (tmp_path / '.claude-plugin').mkdir()
    (tmp_path / '.claude-plugin' / 'marketplace.json').write_text('{nope')
    assert 'invalid JSON' in _check(tmp_path)[0]


def test_entry_pointing_at_missing_directory_is_flagged(tmp_path):
    _repo(tmp_path, [{'name': 'ghost', 'source': './plugins/ghost'}])
    errors = _check(tmp_path)
    assert len(errors) == 1
    assert "'ghost'" in errors[0]


def test_unlisted_plugin_directory_is_flagged(tmp_path):
    _repo(tmp_path, [], dirs=['alpha'])
    errors = _check(tmp_path)
    assert errors == ["marketplace.json: plugin 'alpha' not listed"]


def test_pointer_entry_needs_no_directory(tmp_path):
    pointer = {'name': 'remote', 'source': {'source': 'git-subdir', 'url': 'https://example.com/x.git'}}
    _repo(tmp_path, [pointer])
    assert _check(tmp_path) == []


def test_hidden_directories_are_ignored(tmp_path):
    _repo(tmp_path, [], dirs=['.cache'])
    assert _check(tmp_path) == []


def test_entry_without_source_is_flagged(tmp_path):
    _repo(tmp_path, [{'name': 'alpha'}])
    errors = _check(tmp_path)
    assert errors == ["marketplace.json: plugin 'alpha' has no valid source"]


def test_empty_source_is_flagged(tmp_path):
    _repo(tmp_path, [{'name': 'alpha', 'source': '  '}])
    assert 'no valid source' in _check(tmp_path)[0]


def test_parent_segment_in_source_is_flagged(tmp_path):
    _repo(tmp_path, [{'name': 'alpha', 'source': './plugins/../plugins/alpha'}], dirs=['alpha'])
    assert 'leaves the repo' in _check(tmp_path)[0]


def test_source_outside_repo_is_flagged(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    repo = tmp_path / 'repo'
    repo.mkdir()
    _repo(repo, [{'name': 'alpha', 'source': str(outside)}])
    assert 'leaves the repo' in _check(repo)[0]
