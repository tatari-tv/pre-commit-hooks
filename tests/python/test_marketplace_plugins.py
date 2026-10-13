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


def test_nested_file_symlink_is_flagged(tmp_path):
    base = _plugin(tmp_path, 'alpha')
    (base / 'skills' / 'one' / 'link.md').symlink_to(base / 'skills' / 'one' / 'SKILL.md')
    errors, _ = _check(tmp_path)
    assert errors == ['plugins/alpha/skills/one/link.md: symlink not allowed']


def test_nested_directory_symlink_is_flagged_once(tmp_path):
    base = _plugin(tmp_path, 'alpha')
    (base / 'skills' / 'one' / 'refs').symlink_to(tmp_path)
    errors, _ = _check(tmp_path)
    assert errors == ['plugins/alpha/skills/one/refs: symlink not allowed']


def test_symlinked_skills_dir_is_flagged(tmp_path):
    base = _plugin(tmp_path, 'alpha', skills=None)
    (base / 'skills').symlink_to(tmp_path)
    errors, warnings = _check(tmp_path)
    assert errors == ['plugins/alpha/skills: symlink not allowed']
    assert warnings == []


def test_dangling_skills_dir_symlink_is_flagged(tmp_path):
    base = _plugin(tmp_path, 'alpha', skills=None)
    (base / 'skills').symlink_to(tmp_path / 'nowhere')
    errors, _ = _check(tmp_path)
    assert errors == ['plugins/alpha/skills: symlink not allowed']


def test_symlinks_are_flagged_even_with_a_missing_manifest(tmp_path):
    base = tmp_path / 'alpha'
    (base / 'skills' / 'one').mkdir(parents=True)
    (base / 'skills' / 'one' / 'link').symlink_to(base)
    errors, _ = _check(tmp_path)
    assert 'missing .claude-plugin/plugin.json' in errors[0]
    assert errors[1] == 'plugins/alpha/skills/one/link: symlink not allowed'


def test_symlink_outside_skills_dirs_is_ignored(tmp_path):
    base = _plugin(tmp_path, 'alpha')
    (base / 'shared').symlink_to(base / 'skills')
    assert _check(tmp_path) == ([], [])
