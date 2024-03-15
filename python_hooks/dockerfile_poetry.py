import argparse
import re
import sys

REGEX_MATCH = r"poetry[~]?=[\d.]+"


def check_poetry(filename):
    with open(filename) as file:
        dockerfile = file.read()

    if not re.search(REGEX_MATCH, dockerfile):
        print(f"Poetry version needs to be specified in {filename}")
        return 1

    return 0  # Indicates success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check for specific imports')
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()
    return_code = 0

    file_list = args.file_list
    print(file_list)

    # in case there are multiple dockerfiles:
    for file_path in file_list:
        return_code |= check_poetry(file_path)

    sys.exit(return_code)
