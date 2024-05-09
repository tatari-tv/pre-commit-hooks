import re
import sys
from subprocess import check_output


# regex patterns for acceptable branch names
# the only current check enforces the branch name is in a valid docker tag format (see https://docs.docker.com/reference/cli/docker/image/tag/), and also allows forward slashes.
# we also restrict the branch name to be 50 characters or less, because that makes sense.
EXPECTED_PATTERN = r"^(?![-.])[a-zA-Z0-9._/-]{1,50}$"
ERROR_MESSAGE = "branch name can't start with hyphen or period, cant be more than 50 characters, and can only contain letters, numbers, and special the characters: ._-/"


def validate_branch_name(branch) -> int:
    if re.match(EXPECTED_PATTERN, branch):
        return 0
    print(ERROR_MESSAGE)
    return 1


if __name__ == "__main__":
    branch = check_output(['git', 'symbolic-ref', '--short', 'HEAD']).strip().decode('utf-8')
    return_code = validate_branch_name(branch)
    sys.exit(return_code)
