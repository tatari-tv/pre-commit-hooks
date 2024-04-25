import argparse
import ast
import enum
import sys

from python_hooks.utills.ignore_check import IdentifierCheck
from python_hooks.utills.ignore_check import ignore_check

DISALLOWED_MESSAGE = "Flagged {identifier} {name} in {filename}:{line} column {col_offset}. Replace with {replacement}"


class Identifier(enum.Enum):
    function = 'function'
    attribute = 'attribute'

    def __str__(self):
        return self.value


def check_identifiers(filename, identifier: Identifier, disallowed: list[str], replacements: list[str]):
    check_accumulator = []
    with open(filename) as file:
        tree = ast.parse(file.read(), filename=filename)

    for node in ast.walk(tree):
        # function check
        if identifier == Identifier.function and isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in disallowed:
                    index = disallowed.index(node.func.attr)
                    check_accumulator.append(IdentifierCheck(node.func.attr, replacements[index], node.lineno, node.col_offset))

        # attribute check
        if identifier == Identifier.attribute and isinstance(node, ast.Attribute):
            if node.attr in disallowed:
                index = disallowed.index(node.attr)
                check_accumulator.append(IdentifierCheck(node.attr, replacements[index], node.lineno, node.col_offset))

    # check if there's a tatari-noqa annotation in accumulator.
    # If so, ignore the check and remove from accumulator.
    # if not, print the flagged function calls
    annotated_check_accumulator = ignore_check(filename, check_accumulator)

    if len(annotated_check_accumulator) > 0:
        for check in annotated_check_accumulator:
            print(
                DISALLOWED_MESSAGE.format(
                    identifier=identifier,
                    name=check.name,
                    filename=filename,
                    line=check.line,
                    col_offset=check.col_offset,
                    replacement=check.replacement,
                )
            )
        return 1
    return 0  # Indicates success


def validate_args(args):
    if len(args.replacements) != len(args.disallowed):
        raise ValueError("Number of replacements does not match the number to check")


def main(args):
    return_code = 0

    for file_path in args.file_list:
        return_code |= check_identifiers(file_path, args.identifier, args.disallowed, args.replacements)

    return return_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Flags problematic code and suggests replacement code')
    parser.add_argument('--identifier', type=Identifier, choices=list(Identifier), required=True)
    parser.add_argument('--disallowed', nargs='+', help='Disallowed identifier names to check for in code', required=True)
    parser.add_argument('--replacements', nargs='+', help='Replacement names for disallowed identifiers', required=True)
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()
    print(args.identifier)

    validate_args(args)
    return_code = main(args)
    sys.exit(return_code)
