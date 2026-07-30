import os
import re
import subprocess
import sys


# regex patterns for acceptable branch names
# the only current check enforces the branch name is in a valid docker tag format (see https://docs.docker.com/reference/cli/docker/image/tag/), and also allows forward slashes.
# we also restrict the branch name to be 50 characters or less, because that makes sense.
EXPECTED_PATTERN = r"^(?![-.])[a-zA-Z0-9._/-]{1,50}$"
ERROR_MESSAGE = "branch name can't start with hyphen or period, cant be more than 50 characters, and can only contain letters, numbers, and special the characters: ._-/"

# `git rev-parse --abbrev-ref HEAD` reports this literal string when HEAD is detached.
DETACHED_HEAD = 'HEAD'


def validate_branch_name(branch: str) -> int:
    if re.match(EXPECTED_PATTERN, branch):
        return 0
    print(ERROR_MESSAGE)
    print(f'got branch name: {branch!r}')
    return 1


def _branch_name_from_git() -> str | None:
    """Return the checked-out branch name, or None when HEAD is detached or git can't answer."""
    try:
        output = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        # not a git repo, git not installed, or an unborn HEAD with no commits yet
        return None
    branch = output.strip().decode('utf-8')
    if not branch or branch == DETACHED_HEAD:
        return None
    return branch


def _branch_name_from_env() -> str | None:
    """Return the branch name Github Actions advertises, or None when it isn't usable."""
    # Github Actions checks out a detached HEAD, so git cannot name the branch there.
    # Treat an empty value the same as an unset one: an empty string is not a branch name.
    return os.environ.get('GITHUB_REF_NAME', '').strip() or None


def resolve_branch_name() -> str | None:
    """Return the name of the branch being committed to, or None if it cannot be determined.

    git is the source of truth: `rev-parse --abbrev-ref HEAD` names the branch that is actually
    checked out. Do not infer the name from `git branch --contains HEAD` -- that lists every local
    branch containing the commit, in alphabetical order, decorated with `*` for the current branch
    and `+` for a branch checked out in another worktree, so picking a line out of it returns an
    unrelated branch (or a `+`-prefixed, unparseable one) whenever more than one branch is a match.
    """
    return _branch_name_from_git() or _branch_name_from_env()


def main() -> int:
    """CLI entry point for the validate-branch-name pre-commit hook."""
    branch = resolve_branch_name()
    if branch is None:
        # Detached HEAD with no Github Actions ref to fall back on: rebase, bisect, or a bare
        # checkout by commit sha. There is no branch name to validate, and a branch-name linter
        # should never be the thing that blocks such a run.
        print('no branch name available (detached HEAD and no GITHUB_REF_NAME); skipping check')
        return 0

    return validate_branch_name(branch)


if __name__ == "__main__":
    sys.exit(main())
