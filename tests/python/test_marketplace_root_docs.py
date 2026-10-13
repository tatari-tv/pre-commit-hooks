from python_hooks.claude_plugin_marketplace import root_docs


def _check(root):
    errors = []
    root_docs.check_root_docs(root, errors)
    return errors


def test_regular_files_pass(tmp_path):
    (tmp_path / 'CLAUDE.md').write_text('c\n')
    (tmp_path / 'AGENTS.md').write_text('a\n')
    assert _check(tmp_path) == []


def test_symlinked_claude_md_is_flagged(tmp_path):
    (tmp_path / 'AGENTS.md').write_text('a\n')
    (tmp_path / 'CLAUDE.md').symlink_to(tmp_path / 'AGENTS.md')
    assert _check(tmp_path) == ['CLAUDE.md: must be a regular file, not a symlink']


def test_symlinked_agents_md_is_flagged(tmp_path):
    (tmp_path / 'CLAUDE.md').write_text('c\n')
    (tmp_path / 'AGENTS.md').symlink_to(tmp_path / 'CLAUDE.md')
    assert _check(tmp_path) == ['AGENTS.md: must be a regular file, not a symlink']


def test_dangling_symlink_is_flagged(tmp_path):
    (tmp_path / 'AGENTS.md').symlink_to(tmp_path / 'nowhere')
    assert _check(tmp_path) == ['AGENTS.md: must be a regular file, not a symlink']


def test_missing_files_are_not_an_error(tmp_path):
    assert _check(tmp_path) == []
