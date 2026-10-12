from python_hooks.claude_plugin_marketplace import closure


def _skill(plugins, plugin, skill, files=None):
    base = plugins / plugin / 'skills' / skill
    base.mkdir(parents=True)
    (base / 'SKILL.md').write_text('---\nname: x\n---\n')
    for rel, text in (files or {}).items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text)
    return base


def _check(plugins):
    errors = []
    closure.check_closure(plugins, errors)
    return errors


def _fence(lang, body):
    return f'text\n\n```{lang}\n{body}\n```\n'


def test_prefix_reference_in_script_is_flagged(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'run.sh': 'invoke beta:two now\n'})
    _skill(tmp_path, 'beta', 'two')
    errors = _check(tmp_path)
    assert len(errors) == 1
    assert "'beta:two'" in errors[0]


def test_prefix_reference_inside_own_plugin_passes(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'run.sh': 'invoke alpha:two\n'})
    _skill(tmp_path, 'alpha', 'two')
    assert _check(tmp_path) == []


def test_prose_reference_is_allowed(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'notes.md': 'Use beta:two for this.\n'})
    _skill(tmp_path, 'beta', 'two')
    assert _check(tmp_path) == []


def test_executable_fence_in_markdown_is_scanned(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'notes.md': _fence('bash', 'run beta:two')})
    _skill(tmp_path, 'beta', 'two')
    assert len(_check(tmp_path)) == 1


def test_bare_fence_counts_as_shell(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'notes.md': _fence('', 'run beta:two')})
    _skill(tmp_path, 'beta', 'two')
    assert len(_check(tmp_path)) == 1


def test_markdown_fence_stays_prose(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'notes.md': _fence('markdown', 'see beta:two')})
    _skill(tmp_path, 'beta', 'two')
    assert _check(tmp_path) == []


def test_search_qualifier_is_not_a_reference(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'run.sh': 'gh search code repo:org/name\n'})
    _skill(tmp_path, 'repo', 'two')
    assert _check(tmp_path) == []


def test_sibling_path_into_other_plugin_is_flagged(tmp_path):
    path = '${CLAUDE_SKILL_DIR}/../../../beta/skills/two/tool.sh'
    _skill(tmp_path, 'alpha', 'one', {'run.sh': f'bash {path}\n'})
    _skill(tmp_path, 'beta', 'two')
    errors = _check(tmp_path)
    assert len(errors) == 1
    assert "'two'" in errors[0]


def test_sibling_path_to_existing_skill_in_plugin_passes(tmp_path):
    path = '${CLAUDE_SKILL_DIR}/../two/tool.sh'
    _skill(tmp_path, 'alpha', 'one', {'run.sh': f'bash {path}\n'})
    _skill(tmp_path, 'alpha', 'two')
    assert _check(tmp_path) == []


def test_sibling_path_to_missing_skill_is_flagged(tmp_path):
    path = '${CLAUDE_SKILL_DIR}/../gone/tool.sh'
    _skill(tmp_path, 'alpha', 'one', {'run.sh': f'bash {path}\n'})
    _skill(tmp_path, 'beta', 'two')
    errors = _check(tmp_path)
    assert len(errors) == 1
    assert 'missing skill' in errors[0]


def test_path_leaving_plugins_root_is_flagged(tmp_path):
    path = '${CLAUDE_SKILL_DIR}/../../../../outside/x.sh'
    _skill(tmp_path, 'alpha', 'one', {'run.sh': f'bash {path}\n'})
    _skill(tmp_path, 'beta', 'two')
    errors = _check(tmp_path)
    assert len(errors) == 1
    assert 'resolves outside' in errors[0]


def test_skill_name_in_two_plugins_is_not_blamed(tmp_path):
    path = '${CLAUDE_SKILL_DIR}/../two/tool.sh'
    _skill(tmp_path, 'alpha', 'one', {'run.sh': f'bash {path}\n'})
    _skill(tmp_path, 'alpha', 'two')
    _skill(tmp_path, 'beta', 'two')
    assert _check(tmp_path) == []


def test_missing_plugins_root_is_fine(tmp_path):
    assert _check(tmp_path / 'absent') == []


def test_indented_fence_in_list_is_scanned(tmp_path):
    body = '- step\n\n  ```bash\n  run beta:two\n  ```\n'
    _skill(tmp_path, 'alpha', 'one', {'notes.md': body})
    _skill(tmp_path, 'beta', 'two')
    assert len(_check(tmp_path)) == 1


def test_longer_name_is_not_a_roster_match(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'run.sh': 'invoke beta:two-extra now\n'})
    _skill(tmp_path, 'beta', 'two')
    assert _check(tmp_path) == []


def test_rostered_longer_name_is_still_flagged(tmp_path):
    _skill(tmp_path, 'alpha', 'one', {'run.sh': 'invoke beta:two-extra now\n'})
    _skill(tmp_path, 'beta', 'two')
    _skill(tmp_path, 'beta', 'two-extra')
    errors = _check(tmp_path)
    assert len(errors) == 1
    assert "'beta:two-extra'" in errors[0]
