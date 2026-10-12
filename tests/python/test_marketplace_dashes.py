import subprocess

from python_hooks.claude_plugin_marketplace import dashes
from python_hooks.claude_plugin_marketplace._common import tracked_files

DASH = chr(0x2014)
ESCAPE = '\\' + 'u' + f'{0x2014:04x}'


def _git_repo(path, files):
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    for rel, text in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    subprocess.run(['git', '-C', str(path), 'add', '-A'], check=True)


def test_constants_match_characters():
    assert dashes.EM_DASH == DASH
    assert dashes.EM_DASH_ESCAPE == ESCAPE
    assert len(ESCAPE) == 6


def test_flags_literal_with_line_number(tmp_path):
    (tmp_path / 'a.md').write_text(f'ok\nbad {DASH} line\n', encoding='utf-8')
    errors = []
    dashes.check_dashes(tmp_path, ['a.md'], errors)
    assert len(errors) == 1
    assert errors[0].startswith('a.md:2:')


def test_flags_escape_in_json(tmp_path):
    (tmp_path / 'm.json').write_text('{"d": "a ' + ESCAPE + ' b"}\n', encoding='utf-8')
    errors = []
    dashes.check_dashes(tmp_path, ['m.json'], errors)
    assert len(errors) == 1
    assert 'escaped em-dash' in errors[0]


def test_line_with_both_forms_reports_each(tmp_path):
    (tmp_path / 'b.txt').write_text(f'{DASH} {ESCAPE}\n', encoding='utf-8')
    errors = []
    dashes.check_dashes(tmp_path, ['b.txt'], errors)
    assert len(errors) == 2


def test_clean_file_passes(tmp_path):
    (tmp_path / 'c.md').write_text('plain - hyphen only\n', encoding='utf-8')
    errors = []
    dashes.check_dashes(tmp_path, ['c.md'], errors)
    assert errors == []


def test_binary_file_is_skipped(tmp_path):
    (tmp_path / 'x.bin').write_bytes(b'\xff\xfe\x00\x01')
    errors = []
    dashes.check_dashes(tmp_path, ['x.bin'], errors)
    assert errors == []


def test_tracked_files_skips_untracked(tmp_path):
    _git_repo(tmp_path, {'kept.md': 'x\n'})
    (tmp_path / 'scratch.md').write_text(f'{DASH}\n', encoding='utf-8')
    errors = []
    assert tracked_files(tmp_path, errors) == ['kept.md']
    assert errors == []


def test_tracked_files_outside_git_is_an_error(tmp_path):
    errors = []
    assert tracked_files(tmp_path, errors) == []
    assert errors


def test_main_fails_on_dash_in_repo(tmp_path, monkeypatch, capsys):
    _git_repo(tmp_path, {'a.md': f'x {DASH} y\n'})
    monkeypatch.chdir(tmp_path)
    assert dashes.main() == 1
    assert 'a.md:1' in capsys.readouterr().out


def test_main_passes_on_clean_repo(tmp_path, monkeypatch):
    _git_repo(tmp_path, {'a.md': 'x - y\n'})
    monkeypatch.chdir(tmp_path)
    assert dashes.main() == 0
