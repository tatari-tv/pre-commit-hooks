import argparse
import ast
import sys
import enum
from python_hooks.utills.ignore_check import ignore_check
from python_hooks.utills.ignore_check import IdentifierCheck

DISALLOWED_MESSAGE = "Flagged {name} in {filename}:{line}."

def check_file(filename):
    check_accumulator = []
    with open(filename) as file:
        tree = ast.parse(file.read(), filename=filename)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ['DatabricksJobOperator', 'DatabricksImageRepo', 'DatabricksSharedOperator', 'DatabricksNotebookOperator']:
                for keyword in node.keywords:
                    if keyword.arg == 'image_tag' or keyword.arg == 'branch':
                        check_accumulator.append( IdentifierCheck(keyword.arg, None, keyword.lineno, keyword.col_offset))

    # check if there's a tatari-noqa annotation in accumulator.
    # If so, ignore the check and remove from accumulator.
    # if not, print the flagged function calls
    annotated_check_accumulator = ignore_check(filename, check_accumulator)
    if annotated_check_accumulator:
        for check in annotated_check_accumulator:
            print(
                DISALLOWED_MESSAGE.format(
                    name=check.name,
                    filename = filename,
                    line = check.line
                )
            )
        return 1
    return 0  # Indicates success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Prevents specification of image_tag and branch in DatabricksOperator')
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()

    file_list = args.file_list
    return_code = 0

    for file_path in file_list:
        return_code |= check_file(file_path)

    sys.exit(return_code)
