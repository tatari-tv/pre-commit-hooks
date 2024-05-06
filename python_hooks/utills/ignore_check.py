from dataclasses import dataclass

NOQA = "tatari-noqa"


@dataclass
class IdentifierCheck:
    name: str
    replacement: str
    line: int
    col_offset: int


def ignore_check(filename: str, check_fails: list[IdentifierCheck], noqa_string: str = NOQA) -> list[IdentifierCheck]:
    """
    Takes a filename, and a list of failed checks, and a noqa_string to check for in comments.
    Checks each failed line for a noqa_string comment, and removes the check if it is found.
    Returns the number of checks remaining.
    """
    with open(filename) as file:
        failing_lines = [check.line for check in check_fails]
        for i, line in enumerate(file):
            if i + 1 in failing_lines:
                # there can be multiple IdentifierChecks per line
                for check in [check for check in check_fails if check.line == i + 1]:
                    if noqa_string in line:
                        check_fails.remove(check)
    return check_fails
