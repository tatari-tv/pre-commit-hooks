import json

from python_hooks.claude_plugin_marketplace import plugin_names


def _plugin(plugins, name, manifest_name=None, skills=('one',)):
    base = plugins / name
    (base / '.claude-plugin').mkdir(parents=True)
    (base / '.claude-plugin' / 'plugin.json').write_text(json.dumps({'name': manifest_name or name}))
    for skill in skills or ():
        (base / 'skills' / skill).mkdir(parents=True)
        (base / 'skills' / skill / 'SKILL.md').write_text('---\nname: x\n---\n')
    return base


def _check(plugins):
    errors, warnings = [], []
    plugin_names.check_plugins(plugins, errors, warnings)
    return errors, warnings


def test_matching_name_passes(tmp_path):
    _plugin(tmp_path, 'alpha')
    assert _check(tmp_path) == ([], [])


def test_name_mismatch_is_flagged(tmp_path):
    _plugin(tmp_path, 'alpha', manifest_name='beta')
    errors, _ = _check(tmp_path)
    assert len(errors) == 1
    assert "'beta' != directory 'alpha'" in errors[0]


def test_missing_manifest_is_flagged(tmp_path):
    (tmp_path / 'alpha').mkdir()
    errors, _ = _check(tmp_path)
    assert 'missing .claude-plugin/plugin.json' in errors[0]


def test_invalid_json_is_flagged(tmp_path):
    base = _plugin(tmp_path, 'alpha')
    (base / '.claude-plugin' / 'plugin.json').write_text('{nope')
    errors, _ = _check(tmp_path)
    assert 'invalid JSON' in errors[0]


def test_symlinked_skill_is_flagged(tmp_path):
    base = _plugin(tmp_path, 'alpha')
    (base / 'skills' / 'link').symlink_to(base / 'skills' / 'one')
    errors, _ = _check(tmp_path)
    assert 'symlink not allowed' in errors[0]


def test_plugin_without_skills_dir_warns(tmp_path):
    _plugin(tmp_path, 'alpha', skills=None)
    errors, warnings = _check(tmp_path)
    assert errors == []
    assert 'no skills/ directory' in warnings[0]


def test_hidden_directories_are_ignored(tmp_path):
    (tmp_path / '.cache').mkdir()
    assert _check(tmp_path) == ([], [])


def test_missing_plugins_root_is_fine(tmp_path):
    assert _check(tmp_path / 'absent') == ([], [])


def test_skill_md_presence_is_left_to_skill_lint(tmp_path):
    base = _plugin(tmp_path, 'alpha', skills=())
    (base / 'skills' / 'empty').mkdir(parents=True)
    assert _check(tmp_path) == ([], [])
