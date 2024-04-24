import argparse
import ast
import sys

from python_hooks.utills.ignore_check import FunctionCall
from python_hooks.utills.ignore_check import ignore_check

MESSAGE = "Flagged attribute call of {name} in {filename} @ line {line} column {col_offset} with {replacement}"


def check_attributes(filename, disallowed_functions: list[str], suggest_replace: list[str]):
    check_accumulator = []
    with open(filename) as file:
        tree = ast.parse(file.read(), filename=filename)

    for node in ast.walk(tree):
        # then check for attributes
        if isinstance(node, ast.Attribute):
            if node.attr in disallowed_functions:
                index = disallowed_functions.index(node.attr)
                check_accumulator.append(FunctionCall(node.attr, suggest_replace[index], node.lineno, node.col_offset))

    # check if there's a tatari-noqa annotation in accumulator.
    # If so, ignore the check and remove from accumulator.
    # if not, print the flagged function calls
    annotated_check_accumulator = ignore_check(filename, check_accumulator)

    if len(annotated_check_accumulator) > 0:
        for check in annotated_check_accumulator:
            print(
                MESSAGE.format(
                    name=check.name, filename=filename, line=check.line, col_offset=check.col_offset, replacement=check.replacement
                )
            )
        return 1
    return 0  # Indicates success


def validate_args(args):
    if len(args.replacement_attributes) != len(args.disallowed_attributes):
        raise ValueError("Number of replacements does not match the number to check")


def main(args):
    return_code = 0

    for file_path in args.file_list:
        return_code |= check_attributes(file_path, args.disallowed_attributes, args.replacement_attributes)

    return return_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Flags attributes for replacement with suggested replacement attributes')
    parser.add_argument('--disallowed-attributes', nargs='+', help='Names of the attributes to check', required=True)
    parser.add_argument('--replacement-attributes', nargs='+', help='Names of the attributes to replace in flagged attributes', required=True)
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()

    validate_args(args)
    return_code = main(args)
    sys.exit(return_code)
