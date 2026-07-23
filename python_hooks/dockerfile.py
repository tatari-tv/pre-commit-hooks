'''
Check that a Dockerfile pins a uv version on install.

Accepts a pinned uv version in any instruction form we use, and only in a real
instruction:

- ``RUN ... install uv==0.7.14`` (direct pin in an install command)
- ``ARG UV_VERSION="0.7.14"`` (build-arg pin, referenced as ``uv==${UV_VERSION}``)
- ``FROM ...python:3.11-uv0.9.16-...`` (uv-pinned base image)

Comment-only lines, inline comments, and non-install commands (e.g. ``RUN echo
"uv==0.7.14"``) do not count.
'''
import argparse
import re
import sys

# Version tokens end on a boundary so malformed refs like `0.7.14junk` don't
# validate; `_INSTALL` matches `install` but not `uninstall`.
_FROM_PIN = re.compile(r'[-:]uv\d[\d.]*(?![\w.])', re.IGNORECASE)
_ARG_PIN = re.compile(r'UV_VERSION\s*=\s*["\']?\d[\d.]*(?![\w.])', re.IGNORECASE)
_RUN_PIN = re.compile(r'\buv==\d[\d.]*(?![\w.])')
_INSTALL = re.compile(r'(?<![a-z])install\b', re.IGNORECASE)


def _pins_uv(instruction: str) -> bool:
    '''Return True if a single (comment-stripped) Dockerfile instruction pins uv.'''
    text = instruction.strip()
    if not text:
        return False
    keyword = text.split(None, 1)[0].upper()
    if keyword == 'FROM':
        return bool(_FROM_PIN.search(text))
    if keyword == 'ARG':
        return bool(_ARG_PIN.search(text))
    if keyword == 'RUN':
        return bool(_INSTALL.search(text)) and bool(_RUN_PIN.search(text))
    return False


def check_uv(filename: str) -> int:
    with open(filename) as file:
        dockerfile = file.read()

    # Join line continuations, then evaluate each instruction with inline
    # comments stripped, so only real uv-pinning instructions count.
    joined = re.sub(r'\\\s*\n', ' ', dockerfile)
    for line in joined.splitlines():
        if _pins_uv(line.split('#', 1)[0]):
            return 0

    print(f'uv version needs to be pinned in {filename} (e.g. ARG UV_VERSION=0.7.14 or pip install uv==0.7.14)')
    return 1


def main() -> None:
    '''CLI entry point for the dockerfile pre-commit hook.'''
    parser = argparse.ArgumentParser(description='Check if Dockerfile pins a uv version on install')
    parser.add_argument('file_list', nargs='+', help='List of files to check')  # provided by the pre-commit call
    args = parser.parse_args()
    return_code = 0

    for file_path in args.file_list:
        return_code |= check_uv(file_path)

    sys.exit(return_code)


if __name__ == '__main__':
    main()
