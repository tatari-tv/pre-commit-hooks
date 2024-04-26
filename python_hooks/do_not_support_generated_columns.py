import argparse
import os
import re
import sys

FILE_REGEX = r'\d{8}'
SQL_REGEX = r"GENERATED ALWAYS AS \(\w+\) STORED"
CUTOFF_DATE = "20240426"


def check_file(filename):
    print(filename)
    with open(filename) as file:
        file_data = file.read()

    if re.search(SQL_REGEX, file_data):
        print(f"Postgres WAL replication to datalake does not support generated column. Please use a different approach: file {filename}")
        return 1

    return 0  # Indicates success


def filter_files(file_list: list[str]) -> list[str]:
    return [file for file in file_list if re.match(FILE_REGEX, os.path.basename(file)).group() >= CUTOFF_DATE]  # type: ignore


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='prevent postgres migrations using generated columns')
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()
    return_code = 0

    file_list = args.file_list

    # filter files to exlude older migrations
    filter_file_list = filter_files(file_list)

    for file_path in filter_file_list:
        return_code |= check_file(file_path)

    sys.exit(return_code)
