import argparse
import ast
import sys

from python_hooks.utills.ignore_check import FunctionCall
from python_hooks.utills.ignore_check import ignore_check

MESSAGE = "Flagged function call of {name} in {filename} @ line {line} column {col_offset} with {replacement}"


def check_function_call(filename, disallowed_functions: list[str], suggest_replace: list[str]):
    check_accumulator = []
    with open(filename) as file:
        tree = ast.parse(file.read(), filename=filename)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in disallowed_functions:
                    index = disallowed_functions.index(node.func.attr)
                    # accumulate flagged functions
                    check_accumulator.append(FunctionCall(node.func.attr, suggest_replace[index], node.lineno, node.col_offset))

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
    if len(args.replacement_function_calls) != len(args.disallowed_function_calls):
        raise ValueError("Number of replacement functions does not match the number of functions to check")


def main(args):
    return_code = 0

    for file_path in args.file_list:
        return_code |= check_function_call(file_path, args.disallowed_function_calls, args.replacement_function_calls)

    return return_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Flags function calls for replacement with suggested replacement function')
    parser.add_argument('--disallowed-function-calls', nargs='+', help='Names of the function calls to check', required=True)
    parser.add_argument('--replacement-function-calls', nargs='+', help='Names of the function to replace in flagged calls', required=True)
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()

    validate_args(args)
    return_code = main(args)
    sys.exit(return_code)
