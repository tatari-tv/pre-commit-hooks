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
