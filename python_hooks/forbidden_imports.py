import argparse
import ast
import sys


def check_imports(filename, forbidden_classes):
    with open(filename) as file:
        tree = ast.parse(file.read(), filename=filename)

    for node in tree.body:
        if isinstance(node, ast.Import) | isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in forbidden_classes:
                    print(f"Flagged import of {alias.name} in {filename}")
                    return 1  # Indicates failure
    return 0  # Indicates success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check for specific imports')
    parser.add_argument('--forbidden_classes', nargs='+', help='Names of the classes to check in imports')
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()

    classes_to_check = args.forbidden_classes
    if not classes_to_check:
        raise ValueError("No classes to check provided. add `args: ['--forbidden_classes', 'foo', 'bar', '--']` to the pre-commit config")

    file_list = args.file_list
    return_code = 0

    for file_path in file_list:
        return_code |= check_imports(file_path, classes_to_check)

    sys.exit(return_code)
