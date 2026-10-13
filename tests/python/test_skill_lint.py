import json
import subprocess

import pytest

from python_hooks.skill_lint import DEFAULT_MAX_DESCRIPTION_CHARS
from python_hooks.skill_lint import filter_gitignored
from python_hooks.skill_lint import main
from python_hooks.skill_lint import parse_frontmatter_keys


def write_skill(root, name, description='A short description.', extra_frontmatter='', body_lines=5, with_spec=False):
    """Write a skill directory that passes every default check."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = f'---\nname: {name}\ndescription: {description}\n{extra_frontmatter}---\n'
    body = '\n'.join(f'Line {i}' for i in range(body_lines))
    (skill_dir / 'SKILL.md').write_text(frontmatter + '\n' + body + '\n')
    if with_spec:
        (skill_dir / 'tests').mkdir()
        (skill_dir / 'tests' / 'spec.json').write_text('{}')
    return skill_dir


@pytest.fixture
def skills_repo(tmp_path, monkeypatch):
    """A cwd with a bare skills/ layout holding one clean skill."""
    monkeypatch.chdir(tmp_path)
    write_skill(tmp_path / 'skills', 'clean')
    return tmp_path


class TestFrontmatterParsing:
    def test_plain_and_quoted_scalars(self):
        keys = parse_frontmatter_keys('name: foo\ndescription: "hello world"\nother: \'quoted\'\n')
        assert keys == {'name': 'foo', 'description': 'hello world', 'other': 'quoted'}

    def test_folded_block_scalar_joins_with_spaces(self):
        keys = parse_frontmatter_keys('description: >\n  hello\n  world\n')
        assert keys['description'] == 'hello world'

    def test_literal_block_scalar_preserves_newlines(self):
        keys = parse_frontmatter_keys('description: |\n  line one\n  line two\n')
        assert keys['description'] == 'line one\nline two'

    def test_wrapped_plain_scalar_folds_with_spaces(self):
        keys = parse_frontmatter_keys('description: This is a long\n  description that wraps.\n')
        assert keys['description'] == 'This is a long description that wraps.'

    def test_mapping_valued_key_stays_empty_and_children_are_not_folded_in(self):
        keys = parse_frontmatter_keys('hooks:\n  foo: bar\nname: x\n')
        assert keys['hooks'] == ''
        assert keys['name'] == 'x'


class TestDiscovery:
    def test_bare_skills_layout(self, skills_repo):
        assert main([]) == 0

    def test_plugins_layout(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_skill(tmp_path / 'plugins' / 'general' / 'skills', 'clean')
        write_skill(tmp_path / 'plugins' / 'platform' / 'skills', 'broken', description='')
        assert main([]) == 1

    def test_both_layouts_scanned_together(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        write_skill(tmp_path / 'skills', 'one')
        write_skill(tmp_path / 'plugins' / 'general' / 'skills', 'two')
        assert main([]) == 0
        assert '2 skills' in capsys.readouterr().out

    def test_no_skills_found_fails(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        assert main([]) == 1
        assert 'no skill directories found' in capsys.readouterr().out

    def test_explicit_skills_root(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_skill(tmp_path / 'lib' / 'myskills', 'clean')
        assert main([]) == 1  # not under a default root
        assert main(['--skills-root', 'lib/myskills']) == 0

    def test_gitignored_skill_dirs_are_skipped(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
        write_skill(tmp_path / 'skills', 'clean')
        write_skill(tmp_path / 'skills', 'scratch', description='')  # would fail if scanned
        (tmp_path / '.gitignore').write_text('skills/scratch/\n')
        assert main([]) == 0
        assert '1 skills' in capsys.readouterr().out

    def test_unexpected_check_ignore_returncode_keeps_everything_and_warns(self, monkeypatch, capsys):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args, returncode=128, stdout='', stderr='fatal: not a git repository')

        monkeypatch.setattr(subprocess, 'run', fake_run)
        assert filter_gitignored(['skills/a', 'skills/b']) == ['skills/a', 'skills/b']
        assert 'git check-ignore exited 128' in capsys.readouterr().err


class TestFrontmatterChecks:
    def test_missing_skill_md_fails(self, skills_repo, capsys):
        (skills_repo / 'skills' / 'empty').mkdir()
        assert main([]) == 1
        assert 'skills/empty: missing_frontmatter - no SKILL.md found' in capsys.readouterr().out

    def test_empty_description_counts_as_missing(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'nodesc', description='')
        assert main([]) == 1
        assert 'missing key(s): description' in capsys.readouterr().out

    def test_extra_required_key_arg_takes_effect(self, skills_repo, capsys):
        assert main([]) == 0  # allowed-tools is not required by default
        assert main(['--required-key', 'description', '--required-key', 'allowed-tools']) == 1
        assert 'missing key(s): allowed-tools' in capsys.readouterr().out

    def test_required_key_arg_replaces_the_default_rather_than_extending_it(self, skills_repo):
        # --required-key is documented to replace DEFAULT_REQUIRED_KEYS, not extend it: a
        # single `--required-key allowed-tools` (without re-passing description) must stop
        # enforcing description, even though a skill with an empty description would
        # otherwise always fail the default check.
        write_skill(skills_repo / 'skills', 'clean', description='')
        assert main(['--required-key', 'allowed-tools']) == 1  # allowed-tools missing
        write_skill(skills_repo / 'skills', 'clean', description='', extra_frontmatter='allowed-tools: Read\n')
        assert main(['--required-key', 'allowed-tools']) == 0  # description empty, but no longer required

    def test_platform_key_allowed_by_default(self, skills_repo):
        write_skill(skills_repo / 'skills', 'modeled', extra_frontmatter='model: haiku\n')
        assert main([]) == 0

    def test_unknown_key_fails_and_allowed_key_arg_takes_effect(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'typoed', extra_frontmatter='descripton: oops\n')
        assert main([]) == 1
        assert 'unexpected key(s): descripton' in capsys.readouterr().out
        assert main(['--allowed-key', 'descripton']) == 0

    def test_required_keys_are_always_allowed(self, skills_repo):
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter='classification: capability\n')
        assert main(['--required-key', 'description', '--required-key', 'classification']) == 0

    def test_crlf_line_endings_still_parse(self, skills_repo):
        skill_dir = skills_repo / 'skills' / 'crlf'
        skill_dir.mkdir()
        content = '---\r\nname: crlf\r\ndescription: A short description.\r\n---\r\n\r\nbody\r\n'
        (skill_dir / 'SKILL.md').write_bytes(content.encode('utf-8'))
        assert main([]) == 0

    def test_frontmatter_with_no_trailing_newline_still_parses(self, skills_repo):
        skill_dir = skills_repo / 'skills' / 'noeof'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text('---\nname: noeof\ndescription: A short description.\n---')
        assert main([]) == 0

    def test_key_values_arg_takes_effect(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'classified', extra_frontmatter='classification: banana\n')
        args = ['--allowed-key', 'classification', '--key-values', 'classification=capability,preference,mixed']
        assert main(args) == 1
        assert "classification: 'banana'" in capsys.readouterr().out
        write_skill(skills_repo / 'skills', 'classified', extra_frontmatter='classification: capability\n')
        assert main(args) == 0

    def test_key_values_ignores_absent_key(self, skills_repo):
        assert main(['--key-values', 'classification=capability,preference,mixed']) == 0

    def test_malformed_key_values_is_a_usage_error(self, skills_repo):
        with pytest.raises(SystemExit) as excinfo:
            main(['--key-values', 'classification'])
        assert excinfo.value.code == 2


class TestSizeChecks:
    def test_description_at_default_cap_passes_and_over_fails(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        write_skill(tmp_path / 'skills', 'atcap', description='x' * DEFAULT_MAX_DESCRIPTION_CHARS)
        assert main([]) == 0
        write_skill(tmp_path / 'skills', 'atcap', description='x' * (DEFAULT_MAX_DESCRIPTION_CHARS + 1))
        assert main([]) == 1
        assert 'oversized_description' in capsys.readouterr().out

    def test_max_description_chars_arg_takes_effect(self, skills_repo):
        assert main([]) == 0
        assert main(['--max-description-chars', '10']) == 1
        assert main(['--max-description-chars', '0']) == 0  # 0 disables

    def test_when_to_use_counts_toward_the_listing_budget(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        write_skill(tmp_path / 'skills', 'combo', description='x' * 600, extra_frontmatter=f'when_to_use: {"y" * 600}\n')
        assert main(['--allowed-key', 'when_to_use']) == 1
        assert '1200 chars combined (description 600 + when_to_use 600' in capsys.readouterr().out

    def test_max_body_lines_arg_takes_effect(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'longbody', body_lines=200)
        assert main([]) == 0
        assert main(['--max-body-lines', '50']) == 1
        assert 'oversized_body' in capsys.readouterr().out
        assert main(['--max-body-lines', '0']) == 0  # 0 disables


class TestSpecCheck:
    def test_spec_not_required_by_default(self, skills_repo):
        assert main([]) == 0

    def test_require_spec_arg_takes_effect(self, skills_repo, capsys):
        assert main(['--require-spec']) == 1
        assert 'missing_spec - no tests/spec.json' in capsys.readouterr().out
        write_skill(skills_repo / 'skills', 'clean', with_spec=True)
        assert main(['--require-spec']) == 0

    def test_only_restricts_to_one_check(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'nodesc', description='')
        # nodesc violates both missing_frontmatter and (with --require-spec) missing_spec;
        # assert on which check actually fired, not just the exit code, so this proves
        # --only excluded missing_spec rather than missing_spec happening to also be non-zero.
        assert main(['--require-spec', '--only', 'missing_frontmatter']) == 1
        out = capsys.readouterr().out
        assert 'missing_frontmatter' in out
        assert 'missing_spec' not in out
        assert main(['--only', 'oversized_body']) == 0


class TestBaseline:
    def test_no_baseline_means_zero_tolerance(self, skills_repo):
        write_skill(skills_repo / 'skills', 'fat', description='x' * 2000)
        assert main([]) == 1

    def test_missing_baseline_file_is_an_error(self, skills_repo, capsys):
        assert main(['--baseline', 'nope.json']) == 1
        assert 'baseline file not found: nope.json' in capsys.readouterr().out

    def test_baseline_absorbs_a_violation(self, skills_repo):
        write_skill(skills_repo / 'skills', 'fat', description='x' * 2000)
        baseline = {'skills/fat': {'oversized_description': {'magnitude': 2000, 'reason': 'pre-existing'}}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        assert main(['--baseline', 'baseline.json']) == 0

    def test_baselined_violation_that_grew_fails(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'fat', description='x' * 2000)
        baseline = {'skills/fat': {'oversized_description': {'magnitude': 1999, 'reason': 'pre-existing'}}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        assert main(['--baseline', 'baseline.json']) == 1
        assert 'grew past its baselined magnitude' in capsys.readouterr().out

    def test_stale_baseline_entry_fails(self, skills_repo, capsys):
        baseline = {'skills/clean': {'oversized_description': {'magnitude': 2000, 'reason': 'pre-existing'}}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        assert main(['--baseline', 'baseline.json']) == 1
        assert 'stale (no longer violated)' in capsys.readouterr().out

    def test_baselined_deleted_skill_fails(self, skills_repo, capsys):
        baseline = {'skills/gone': {'oversized_description': {'magnitude': 2000, 'reason': 'pre-existing'}}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        assert main(['--baseline', 'baseline.json']) == 1
        assert 'no longer exists' in capsys.readouterr().out

    def test_new_missing_key_on_a_baselined_skill_fails(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter='allowed-tools: Read\nargument-hint: none\n')
        write_skill(skills_repo / 'skills', 'gappy', extra_frontmatter='argument-hint: none\n')
        baseline = {'skills/gappy': {'missing_frontmatter': {'magnitude': ['allowed-tools'], 'reason': 'pre-existing'}}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        args = ['--baseline', 'baseline.json', '--required-key', 'description', '--required-key', 'allowed-tools']
        assert main(args) == 0
        (skills_repo / 'skills' / 'gappy' / 'SKILL.md').write_text('---\nname: gappy\ndescription: A short description.\n---\nbody\n')
        assert main(args + ['--required-key', 'argument-hint']) == 1
        assert 'grew past its baselined magnitude' in capsys.readouterr().out

    def test_write_baseline_then_pass(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'fat', description='x' * 2000, body_lines=600)
        assert main(['--baseline', 'baseline.json', '--write-baseline']) == 0
        assert 'wrote baseline for 1 skill(s)' in capsys.readouterr().out
        written = json.loads((skills_repo / 'baseline.json').read_text())
        assert written['skills/fat']['oversized_description']['magnitude'] == 2000
        assert written['skills/fat']['oversized_body']['magnitude'] > 500
        assert main(['--baseline', 'baseline.json']) == 0

    def test_write_baseline_requires_a_path(self, skills_repo):
        with pytest.raises(SystemExit) as excinfo:
            main(['--write-baseline'])
        assert excinfo.value.code == 2

    def test_write_baseline_rejects_only(self, skills_repo):
        with pytest.raises(SystemExit) as excinfo:
            main(['--baseline', 'baseline.json', '--write-baseline', '--only', 'oversized_body'])
        assert excinfo.value.code == 2

    def test_malformed_json_baseline_fails_closed(self, skills_repo, capsys):
        (skills_repo / 'baseline.json').write_text('{not json')
        assert main(['--baseline', 'baseline.json']) == 1
        assert 'not valid JSON' in capsys.readouterr().out

    def test_wrong_shape_baseline_fails_closed(self, skills_repo, capsys):
        (skills_repo / 'baseline.json').write_text(json.dumps(['not', 'a', 'mapping']))
        assert main(['--baseline', 'baseline.json']) == 1
        assert 'must be a JSON object mapping' in capsys.readouterr().out

    def test_baseline_entry_wrong_shape_fails_closed(self, skills_repo, capsys):
        baseline = {'skills/clean': {'oversized_description': 'not-a-dict'}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        assert main(['--baseline', 'baseline.json']) == 1
        assert 'must be a JSON object mapping' in capsys.readouterr().out

    def test_invalid_value_drift_to_a_different_bad_value_counts_as_growth(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter='classification: bogus1\n')
        baseline = {'skills/clean': {'invalid_value': {'magnitude': ['classification=bogus1'], 'reason': 'pre-existing'}}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        args = [
            '--baseline',
            'baseline.json',
            '--allowed-key',
            'classification',
            '--key-values',
            'classification=capability,preference,mixed',
        ]
        assert main(args) == 0  # same bad value as baselined: absorbed
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter='classification: bogus2\n')
        assert main(args) == 1  # drifted to a different bad value under the same key: not absorbed
        assert 'grew past its baselined magnitude' in capsys.readouterr().out

    def test_stale_check_skips_entries_whose_rule_is_not_active_this_run(self, skills_repo, capsys):
        # missing_spec is baselined, but this run omits --require-spec, so the check never
        # ran. "not violated this run" here means "not checked", not "fixed" - the entry
        # must not be reported stale (which would invite deleting real, still-present debt).
        baseline = {'skills/clean': {'missing_spec': {'magnitude': None, 'reason': 'pre-existing'}}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        assert main(['--baseline', 'baseline.json']) == 0
        assert 'stale' not in capsys.readouterr().out

    def test_missing_skill_md_is_not_absorbed_by_an_empty_field_baseline(self, skills_repo, capsys):
        # An empty required field and a deleted SKILL.md both produce missing_frontmatter for
        # the same key name, but the file's outright absence must still register as growth.
        write_skill(skills_repo / 'skills', 'clean', description='')
        baseline = {'skills/clean': {'missing_frontmatter': {'magnitude': ['description'], 'reason': 'pre-existing'}}}
        (skills_repo / 'baseline.json').write_text(json.dumps(baseline))
        assert main(['--baseline', 'baseline.json']) == 0  # empty field: absorbed
        (skills_repo / 'skills' / 'clean' / 'SKILL.md').unlink()
        assert main(['--baseline', 'baseline.json']) == 1  # file gone entirely: not absorbed
        assert 'grew past its baselined magnitude' in capsys.readouterr().out


def write_raw_skill(root, dirname, frontmatter):
    skill_dir = root / dirname
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / 'SKILL.md').write_text(f'---\n{frontmatter}---\n\nbody\n')


ALL_FLAGS = ['--check-name', '--no-angle-brackets', '--max-compatibility-chars', '500']


class TestOptInFrontmatterRules:
    def test_no_new_flags_is_noop(self, skills_repo):
        write_skill(skills_repo / 'skills', 'Bad_Name', description='uses <tags>', extra_frontmatter=f'compatibility: {"x" * 900}\n')
        write_raw_skill(skills_repo / 'skills', 'mismatch', 'name: other\ndescription: ok\n')
        assert main([]) == 0
        assert main(ALL_FLAGS) == 1

    def test_clean_skill_passes_every_new_flag(self, skills_repo):
        assert main(ALL_FLAGS) == 0

    @pytest.mark.parametrize(
        ('dirname', 'frontmatter', 'reasons'),
        [
            ('Bad_Name', 'name: Bad_Name\ndescription: ok\n', 'kebab-case'),
            ('a--b', 'name: a--b\ndescription: ok\n', 'hyphens'),
            ('end-', 'name: end-\ndescription: ok\n', 'hyphens'),
            ('a' * 65, f'name: {"a" * 65}\ndescription: ok\n', 'too-long'),
            ('dirname', 'name: other\ndescription: ok\n', 'dir-mismatch'),
            ('Bad', 'description: ok\n', 'kebab-case'),
        ],
    )
    def test_each_invalid_name_reason_fails(self, skills_repo, capsys, dirname, frontmatter, reasons):
        write_raw_skill(skills_repo / 'skills', dirname, frontmatter)
        assert main(['--check-name']) == 1
        assert f"': {reasons}\n" in capsys.readouterr().out

    def test_reasons_are_listed(self, skills_repo, capsys):
        write_raw_skill(skills_repo / 'skills', 'bad-dir', 'name: Bad\ndescription: ok\n')
        assert main(['--check-name']) == 1
        assert "invalid_name - name 'Bad': kebab-case, dir-mismatch" in capsys.readouterr().out

    def test_missing_name_falls_back_to_directory_name(self, skills_repo):
        write_raw_skill(skills_repo / 'skills', 'ok-dir', 'description: ok\n')
        assert main(['--check-name']) == 0

    def test_numeric_name_is_read_as_its_string_form(self, skills_repo, capsys):
        write_raw_skill(skills_repo / 'skills', '123', 'name: 123\ndescription: ok\n')
        assert main(['--check-name']) == 0
        write_raw_skill(skills_repo / 'skills', 'other-dir', 'name: 123\ndescription: ok\n')
        assert main(['--check-name']) == 1
        assert "name '123': dir-mismatch" in capsys.readouterr().out

    @pytest.mark.parametrize('empty_name', ['name:\n', 'name: ""\n', 'name: "   "\n'])
    def test_present_but_empty_name_does_not_fall_back_to_directory(self, skills_repo, capsys, empty_name):
        write_raw_skill(skills_repo / 'skills', 'good', f'{empty_name}description: ok\n')
        assert main(['--check-name']) == 1
        assert "name '': kebab-case, dir-mismatch" in capsys.readouterr().out

    def test_description_angle_brackets(self, skills_repo, capsys):
        assert main(['--no-angle-brackets']) == 0
        write_skill(skills_repo / 'skills', 'clean', description='uses <tags>')
        assert main([]) == 0
        assert main(['--no-angle-brackets']) == 1
        assert 'description_angle_brackets - description contains < or >' in capsys.readouterr().out
        write_skill(skills_repo / 'skills', 'clean', description='a > b')
        assert main(['--no-angle-brackets']) == 1
        write_skill(skills_repo / 'skills', 'clean', description='a < b')
        assert main(['--no-angle-brackets']) == 1

    def test_compatibility_budget_is_inclusive(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter=f'compatibility: {"x" * 500}\n')
        assert main(['--max-compatibility-chars', '500']) == 0
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter=f'compatibility: {"x" * 501}\n')
        assert main(['--max-compatibility-chars', '500']) == 1
        assert 'oversized_compatibility - compatibility 501 chars (budget 500)' in capsys.readouterr().out
        assert main(['--max-compatibility-chars', '0']) == 0

    def test_block_scalar_compatibility_is_measured_stripped(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter=f'compatibility: |\n  {"x" * 500}\n')
        assert main(['--max-compatibility-chars', '500']) == 0
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter=f'compatibility: |\n  {"x" * 501}\n')
        assert main(['--max-compatibility-chars', '500']) == 1
        assert 'compatibility 501 chars' in capsys.readouterr().out

    def test_quoted_compatibility_is_measured_stripped(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter='compatibility: "  abc  "\n')
        assert main(['--max-compatibility-chars', '3']) == 0
        write_skill(skills_repo / 'skills', 'clean', extra_frontmatter='compatibility: "  abcd  "\n')
        assert main(['--max-compatibility-chars', '3']) == 1
        assert 'compatibility 4 chars' in capsys.readouterr().out

    def test_only_runs_the_named_check(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'Bad_Name', description='uses <tags>', extra_frontmatter=f'compatibility: {"x" * 501}\n')
        checks = ['invalid_name', 'description_angle_brackets', 'oversized_compatibility']
        for only in checks:
            assert main(ALL_FLAGS + ['--only', only]) == 1
            out = capsys.readouterr().out
            assert f': {only} - ' in out
            assert not [other for other in checks if other != only and f': {other} - ' in out]


class TestOptInBaseline:
    def baseline(self, skills_repo, entries):
        (skills_repo / 'baseline.json').write_text(json.dumps({'skills/bad': entries}))

    def test_invalid_name_baseline_absorbs_and_tracks_new_reasons(self, skills_repo, capsys):
        write_raw_skill(skills_repo / 'skills', 'bad', 'name: Bad\ndescription: ok\n')
        self.baseline(skills_repo, {'invalid_name': {'magnitude': ['dir-mismatch', 'kebab-case'], 'reason': 'x'}})
        assert main(['--baseline', 'baseline.json', '--check-name']) == 0
        write_raw_skill(skills_repo / 'skills', 'bad', 'name: Bad--\ndescription: ok\n')
        assert main(['--baseline', 'baseline.json', '--check-name']) == 1
        assert 'grew past its baselined magnitude' in capsys.readouterr().out

    def test_angle_bracket_baseline_absorbs_presence(self, skills_repo):
        write_skill(skills_repo / 'skills', 'bad', description='uses <tags>')
        self.baseline(skills_repo, {'description_angle_brackets': {'magnitude': None, 'reason': 'x'}})
        assert main(['--baseline', 'baseline.json', '--no-angle-brackets']) == 0

    def test_compatibility_baseline_fails_when_length_grows(self, skills_repo, capsys):
        write_skill(skills_repo / 'skills', 'bad', extra_frontmatter=f'compatibility: {"x" * 600}\n')
        self.baseline(skills_repo, {'oversized_compatibility': {'magnitude': 600, 'reason': 'x'}})
        args = ['--baseline', 'baseline.json', '--max-compatibility-chars', '500']
        assert main(args) == 0
        write_skill(skills_repo / 'skills', 'bad', extra_frontmatter=f'compatibility: {"x" * 700}\n')
        assert main(args) == 1
        assert 'grew past its baselined magnitude' in capsys.readouterr().out

    @pytest.mark.parametrize(
        ('check_id', 'flags', 'magnitude'),
        [
            ('invalid_name', ['--check-name'], ['kebab-case']),
            ('description_angle_brackets', ['--no-angle-brackets'], None),
            ('oversized_compatibility', ['--max-compatibility-chars', '500'], 600),
        ],
    )
    def test_fixed_violation_goes_stale_only_when_its_flag_is_on(self, skills_repo, capsys, check_id, flags, magnitude):
        write_skill(skills_repo / 'skills', 'bad')
        self.baseline(skills_repo, {check_id: {'magnitude': magnitude, 'reason': 'x'}})
        assert main(['--baseline', 'baseline.json']) == 0
        assert 'stale' not in capsys.readouterr().out
        assert main(['--baseline', 'baseline.json', *flags]) == 1
        assert 'is stale (no longer violated)' in capsys.readouterr().out

    def test_invalid_name_reasons_compare_as_a_set(self, skills_repo):
        write_raw_skill(skills_repo / 'skills', 'bad', 'name: Bad\ndescription: ok\n')
        args = ['--baseline', 'baseline.json', '--check-name']
        self.baseline(skills_repo, {'invalid_name': {'magnitude': ['kebab-case', 'dir-mismatch'], 'reason': 'x'}})
        assert main(args) == 0  # reordered reasons: absorbed
        self.baseline(skills_repo, {'invalid_name': {'magnitude': ['kebab-case', 'dir-mismatch', 'too-long'], 'reason': 'x'}})
        assert main(args) == 0  # fewer reasons than baselined: absorbed
        write_raw_skill(skills_repo / 'skills', 'bad', 'name: bad--\ndescription: ok\n')
        self.baseline(skills_repo, {'invalid_name': {'magnitude': ['kebab-case', 'dir-mismatch'], 'reason': 'x'}})
        assert main(args) == 1  # same count, a different reason: not absorbed

    def test_angle_bracket_baseline_ignores_how_many_brackets(self, skills_repo):
        write_skill(skills_repo / 'skills', 'bad', description='a <b> <c>')
        self.baseline(skills_repo, {'description_angle_brackets': {'magnitude': None, 'reason': 'x'}})
        assert main(['--baseline', 'baseline.json', '--no-angle-brackets']) == 0

    def test_write_baseline_records_new_checks_and_round_trips(self, skills_repo):
        write_skill(skills_repo / 'skills', 'Bad_Name', description='uses <tags>', extra_frontmatter=f'compatibility: {"x" * 600}\n')
        assert main(['--baseline', 'baseline.json', '--write-baseline', *ALL_FLAGS]) == 0
        written = json.loads((skills_repo / 'baseline.json').read_text())['skills/Bad_Name']
        assert written['invalid_name']['magnitude'] == ['kebab-case']
        assert written['description_angle_brackets']['magnitude'] is None
        assert written['oversized_compatibility']['magnitude'] == 600
        assert main(['--baseline', 'baseline.json', *ALL_FLAGS]) == 0


class TestBodyExcludesFrontmatter:
    def write_fat(self, root, frontmatter_extra_lines, body_lines, blank_after_fence=0):
        skill_dir = root / 'skills' / 'fat'
        skill_dir.mkdir(parents=True)
        extra = ''.join(f'key{i}: v\n' for i in range(frontmatter_extra_lines))
        body = '\n' * blank_after_fence + '\n'.join(f'Line {i}' for i in range(body_lines)) + '\n'
        (skill_dir / 'SKILL.md').write_text(f'---\nname: fat\ndescription: ok\n{extra}---\n{body}')

    def test_default_counts_the_whole_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.write_fat(tmp_path, frontmatter_extra_lines=5, body_lines=48)
        assert (
            main(
                [
                    '--max-body-lines',
                    '50',
                    '--allowed-key',
                    'key0',
                    '--allowed-key',
                    'key1',
                    '--allowed-key',
                    'key2',
                    '--allowed-key',
                    'key3',
                    '--allowed-key',
                    'key4',
                ]
            )
            == 1
        )

    def test_flag_counts_only_the_body(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.write_fat(tmp_path, frontmatter_extra_lines=5, body_lines=48)
        args = ['--max-body-lines', '50', '--body-excludes-frontmatter']
        for i in range(5):
            args += ['--allowed-key', f'key{i}']
        assert main(args) == 0

    def test_flag_still_fails_an_oversized_body(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        self.write_fat(tmp_path, frontmatter_extra_lines=0, body_lines=51)
        assert main(['--max-body-lines', '50', '--body-excludes-frontmatter']) == 1
        assert '51 lines' in capsys.readouterr().out

    def test_flag_drops_blank_lines_after_the_closing_fence(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.write_fat(tmp_path, frontmatter_extra_lines=0, body_lines=50, blank_after_fence=3)
        assert main(['--max-body-lines', '50', '--body-excludes-frontmatter']) == 0

    def test_flag_counts_every_line_without_frontmatter(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        skill_dir = tmp_path / 'skills' / 'bare'
        skill_dir.mkdir(parents=True)
        (skill_dir / 'SKILL.md').write_text('\n'.join(f'Line {i}' for i in range(60)) + '\n')
        assert main(['--max-body-lines', '50', '--body-excludes-frontmatter', '--only', 'oversized_body']) == 1

    def test_flag_off_by_default_leaves_baseline_runs_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.write_fat(tmp_path, frontmatter_extra_lines=0, body_lines=50)
        assert main(['--max-body-lines', '50']) == 1
        assert main(['--max-body-lines', '50', '--body-excludes-frontmatter']) == 0

    def test_flag_counts_crlf_body_lines(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        skill_dir = tmp_path / 'skills' / 'crlf'
        skill_dir.mkdir(parents=True)
        body = ''.join(f'Line {i}\r\n' for i in range(51))
        (skill_dir / 'SKILL.md').write_bytes(f'---\r\nname: crlf\r\ndescription: ok\r\n---\r\n{body}'.encode())
        assert main(['--max-body-lines', '50', '--body-excludes-frontmatter']) == 1
        assert '51 lines' in capsys.readouterr().out

    def test_flag_baseline_records_the_body_count(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.write_fat(tmp_path, frontmatter_extra_lines=0, body_lines=60)
        args = ['--max-body-lines', '50', '--body-excludes-frontmatter']
        assert main([*args, '--baseline', 'baseline.json', '--write-baseline']) == 0
        written = json.loads((tmp_path / 'baseline.json').read_text())
        assert written['skills/fat']['oversized_body']['magnitude'] == 60
        assert main([*args, '--baseline', 'baseline.json']) == 0

    def test_flag_ignores_a_stray_baseline_without_the_baseline_arg(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.write_fat(tmp_path, frontmatter_extra_lines=0, body_lines=60)
        baseline = {'skills/fat': {'oversized_body': {'magnitude': 60, 'reason': 'pre-existing'}}}
        (tmp_path / 'baseline.json').write_text(json.dumps(baseline))
        assert main(['--max-body-lines', '50', '--body-excludes-frontmatter']) == 1


class TestValueTypes:
    FLAG = '--check-value-types'

    def raw(self, root, frontmatter, name='typed'):
        skill_dir = root / 'skills' / name
        skill_dir.mkdir(parents=True)
        (skill_dir / 'SKILL.md').write_text(f'---\n{frontmatter}---\n\nbody\n')

    def test_off_by_default(self, skills_repo):
        self.raw(skills_repo, 'name: typed\ndescription: 42\n')
        assert main([]) == 0

    @pytest.mark.parametrize('value', ['42', '-7', 'true', 'false', 'null', '~', '[a, b]'])
    def test_non_string_description_fails(self, skills_repo, capsys, value):
        self.raw(skills_repo, f'name: typed\ndescription: {value}\n')
        assert main([self.FLAG]) == 1
        out = capsys.readouterr().out
        assert 'skills/typed: non_string_value' in out
        assert 'description' in out

    def test_each_string_key_is_checked(self, skills_repo, capsys):
        self.raw(skills_repo, 'name: 42\ndescription: ok\ncompatibility: true\n')
        assert main([self.FLAG]) == 1
        assert 'compatibility, name' in capsys.readouterr().out

    def test_allowed_tools_number_fails(self, skills_repo, capsys):
        self.raw(skills_repo, 'name: typed\ndescription: ok\nallowed-tools: 42\n')
        assert main([self.FLAG]) == 1
        assert 'allowed-tools' in capsys.readouterr().out

    @pytest.mark.parametrize(
        'frontmatter',
        [
            'name: typed\ndescription: "42"\n',
            "name: typed\ndescription: '42'\n",
            'name: typed\ndescription: 1.5\n',
            'name: typed\ndescription: 42 widgets\n',
            'name: typed\ndescription: 42\n  and more\n',
            'name: typed\ndescription: |\n  42\n',
            'name: typed\ndescription: ok\nallowed-tools: Read, Grep\n',
            'name: typed\ndescription: ok\nallowed-tools: [Read, Grep]\n',
            'name: typed\ndescription: ok\nallowed-tools:\n  - Read\n  - Grep\n',
        ],
    )
    def test_valid_shapes_pass(self, skills_repo, frontmatter):
        self.raw(skills_repo, frontmatter)
        assert main([self.FLAG, '--allowed-key', 'allowed-tools']) == 0

    def test_mapping_valued_description_fails(self, skills_repo):
        self.raw(skills_repo, 'name: typed\ndescription:\n  nested: value\n')
        assert main([self.FLAG]) == 1

    def test_only_runs_the_single_check(self, skills_repo, capsys):
        self.raw(skills_repo, 'name: typed\ndescription: 42\n')
        assert main([self.FLAG, '--only', 'non_string_value']) == 1
        assert main([self.FLAG, '--only', 'oversized_body']) == 0

    def test_baseline_absorbs_then_ratchets(self, skills_repo, capsys):
        self.raw(skills_repo, 'name: typed\ndescription: 42\n')
        assert main([self.FLAG, '--baseline', 'b.json', '--write-baseline']) == 0
        written = json.loads((skills_repo / 'b.json').read_text())
        assert written['skills/typed']['non_string_value']['magnitude'] == ['description']
        assert main([self.FLAG, '--baseline', 'b.json']) == 0
        self.raw_rewrite(skills_repo, 'name: typed\ndescription: 42\ncompatibility: true\n')
        assert main([self.FLAG, '--baseline', 'b.json']) == 1
        assert 'grew past its baselined magnitude' in capsys.readouterr().out

    def raw_rewrite(self, root, frontmatter):
        (root / 'skills' / 'typed' / 'SKILL.md').write_text(f'---\n{frontmatter}---\n\nbody\n')

    def test_fixed_baseline_entry_goes_stale(self, skills_repo, capsys):
        self.raw(skills_repo, 'name: typed\ndescription: 42\n')
        assert main([self.FLAG, '--baseline', 'b.json', '--write-baseline']) == 0
        self.raw_rewrite(skills_repo, 'name: typed\ndescription: fixed\n')
        assert main([self.FLAG, '--baseline', 'b.json']) == 1
        assert 'stale' in capsys.readouterr().out

    def test_baseline_entry_left_alone_when_flag_off(self, skills_repo):
        self.raw(skills_repo, 'name: typed\ndescription: 42\n')
        assert main([self.FLAG, '--baseline', 'b.json', '--write-baseline']) == 0
        self.raw_rewrite(skills_repo, 'name: typed\ndescription: fixed\n')
        assert main(['--baseline', 'b.json']) == 0
