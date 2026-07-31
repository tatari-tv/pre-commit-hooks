import os
import subprocess

import pytest

from python_hooks.validate_branch_name import main
from python_hooks.validate_branch_name import resolve_branch_name
from python_hooks.validate_branch_name import validate_branch_name


# keep the test repos independent of whatever the developer has in their global/system git config
GIT_SETTINGS = {
    'user.name': 'pre-commit-hooks tests',
    'user.email': 'sre@tatari.tv',
    'commit.gpgsign': 'false',
    'init.defaultBranch': 'main',
}
GIT_CONFIG = [arg for setting, value in GIT_SETTINGS.items() for arg in ('-c', f'{setting}={value}')]
GIT_ENV = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_SYSTEM': os.devnull}


def git(cwd, *args) -> str:
    return subprocess.run(['git', *GIT_CONFIG, *args], cwd=cwd, check=True, capture_output=True, text=True, env=GIT_ENV).stdout


@pytest.fixture
def repo(tmp_path):
    """A git repo with one commit, checked out on `main`."""
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init')
    (root / 'file.txt').write_text('contents\n')
    git(root, 'add', 'file.txt')
    git(root, 'commit', '--no-verify', '-m', 'initial commit')
    return root


def test_validate_branch_name():
    branch_names_with_exit_code = [
        ("simplebranch", 0),
        ("UPPER-12345/lower", 0),
        ("lower-12345/UPPER", 0),
        ("ABC-123/with-dash", 0),
        ("ABC-123/with_underscore", 0),
        ("ABC-123/with-dash_and_underscore", 0),
        ("ABC-123/with-dash_and_underscore.and.period", 0),
        (".ABC12345/abcdABC", 1),  # starts with period
        ("-ABC12345/abcdABC", 1),  # starts with hyphen
        ("once_upon_a_time_there_was_a_branch_name_that_told_a_very_long_story", 1),  # over 50 characters
        ("ABC-123/abc&123", 1),  # includes non-allowed symbols
        ("", 1),  # empty string is not a branch name
    ]

    for branch, exit_code in branch_names_with_exit_code:
        assert validate_branch_name(branch) == exit_code


def test_resolves_the_checked_out_branch_when_several_branches_contain_head(repo, tmp_path, monkeypatch):
    """Regression test: the first commit on a new branch, in a repo that has other worktrees.

    Before this was fixed the branch name was inferred from `git branch --contains HEAD`, which is
    every local branch containing the commit -- alphabetically ordered, and prefixed with `+` when
    the branch is checked out in another worktree. The hook read the last line of that listing, so
    it validated an unrelated branch name, and failed outright when that line carried a `+`.
    """
    git(repo, 'branch', 'zz/checked-out-in-another-worktree')
    git(repo, 'worktree', 'add', str(tmp_path / 'other-worktree'), 'zz/checked-out-in-another-worktree')
    git(repo, 'checkout', '-b', 'feature/current-work')

    # the exact shape that used to misfire: >1 branch contains HEAD, the current branch is not the
    # last line, and the last line is decorated with `+` because of the linked worktree
    contained = git(repo, 'branch', '--contains', 'HEAD').strip().splitlines()
    assert len(contained) == 3
    assert contained[-1].strip(' *') == '+ zz/checked-out-in-another-worktree'

    monkeypatch.delenv('GITHUB_REF_NAME', raising=False)
    monkeypatch.chdir(repo)
    assert resolve_branch_name() == 'feature/current-work'
    assert main() == 0


def test_git_is_preferred_over_the_github_actions_ref(repo, monkeypatch):
    git(repo, 'checkout', '-b', 'feature/checked-out-locally')
    monkeypatch.setenv('GITHUB_REF_NAME', 'some/other-ref')
    monkeypatch.chdir(repo)

    assert resolve_branch_name() == 'feature/checked-out-locally'


def test_detached_head_falls_back_to_the_github_actions_ref(repo, monkeypatch):
    git(repo, 'checkout', '--detach', 'HEAD')
    monkeypatch.setenv('GITHUB_REF_NAME', 'feature/from-github-actions')
    monkeypatch.chdir(repo)

    assert resolve_branch_name() == 'feature/from-github-actions'
    assert main() == 0


def test_detached_head_without_a_github_actions_ref_is_skipped(repo, monkeypatch):
    """A rebase, bisect or sha checkout has no branch name, and must not fail the commit."""
    git(repo, 'checkout', '--detach', 'HEAD')
    monkeypatch.delenv('GITHUB_REF_NAME', raising=False)
    monkeypatch.chdir(repo)

    assert resolve_branch_name() is None
    assert main() == 0


def test_an_empty_github_actions_ref_is_treated_as_unset(repo, monkeypatch):
    git(repo, 'checkout', '--detach', 'HEAD')
    monkeypatch.setenv('GITHUB_REF_NAME', '')
    monkeypatch.chdir(repo)

    assert resolve_branch_name() is None
    assert main() == 0


def test_outside_a_git_repo_is_skipped(tmp_path, monkeypatch):
    monkeypatch.delenv('GITHUB_REF_NAME', raising=False)
    monkeypatch.chdir(tmp_path)

    assert resolve_branch_name() is None
    assert main() == 0
