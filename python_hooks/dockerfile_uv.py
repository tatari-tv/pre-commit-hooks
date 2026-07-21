'''
Check that a Dockerfile pins a uv version on install.

The uv counterpart of ``dockerfile-poetry``. Matches any of the pinning styles
we use: a direct ``uv==0.7.14`` install, an ``ARG UV_VERSION="0.7.14"`` pin, or a
uv-pinned base image tag such as ``python:3.11-uv0.9.16-onbuild-lambda``.
'''
import argparse
import re
import sys

REGEX_MATCH = r'uv==[\d.]+|uv_version\s*=\s*.?[\d.]+|[-:]uv[\d.]+'


def check_uv(filename: str) -> int:
    with open(filename) as file:
        dockerfile = file.read()

    # Ignore comment-only lines so a commented-out pin can't satisfy the check.
    instructions = '\n'.join(line for line in dockerfile.splitlines() if not line.lstrip().startswith('#'))

    if not re.search(REGEX_MATCH, instructions, re.IGNORECASE):
        print(f'uv version needs to be pinned in {filename} (e.g. ARG UV_VERSION=0.7.14 or pip install uv==0.7.14)')
        return 1

    return 0  # Indicates success


def main() -> None:
    '''CLI entry point for the dockerfile-uv pre-commit hook.'''
    parser = argparse.ArgumentParser(description='Check if Dockerfile pins a uv version on install')
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()
    return_code = 0

    for file_path in args.file_list:
        return_code |= check_uv(file_path)

    sys.exit(return_code)


if __name__ == '__main__':
    main()
