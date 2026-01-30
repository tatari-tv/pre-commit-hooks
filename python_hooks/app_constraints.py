'''
Validate dependency constraint formats for Python application repos

- Python: requires-python should use ~= (compatible release)
- Packages: dependency specifiers should use ~= (compatible release)
'''
from argparse import ArgumentParser
from re import search

from toml import load

# version operators; used to extract constraint from uv dependency strings
_VERSION_OP_RE = r'(~=|\^|>=|<=|==|!=|<|>)[^;]*'


def _is_uv_project(pyproject: dict) -> bool:
    """Return True if pyproject uses uv format (project.dependencies)."""
    project = pyproject.get('project') or {}
    return 'dependencies' in project


def _get_uv_dependencies(pyproject: dict) -> list[tuple[str, str]]:
    """Yield (dep_name, constraint) from project.dependencies"""
    deps = pyproject.get('project', {}).get('dependencies') or []
    for dep_str in deps:
        dep_str = dep_str.strip()
        # handle for platform specific dependencies (semicolon)
        if ';' in dep_str:
            dep_str = dep_str.split(';', 1)[0].strip()
        version_match = search(_VERSION_OP_RE, dep_str)
        if not version_match:
            continue
        constraint = version_match.group(0).strip()
        name_part = dep_str[: version_match.start()].strip()
        # handle for extras (brackets)
        if '[' in name_part:
            name_part = name_part.split('[')[0].strip()
        dep_name = name_part
        yield dep_name, constraint


def _get_uv_requires_python(pyproject: dict) -> str | None:
    """Return requires-python string if set."""
    return (pyproject.get('project') or {}).get('requires-python')


def validate_constraints(ignore: list[str], pyproject_path: str = 'pyproject.toml') -> int:
    exit_status = 0
    pyproject = load(pyproject_path)

    if not _is_uv_project(pyproject):
        print('ERROR: This hook only validates uv projects at this point in time.')
        return 1

    requires_python = _get_uv_requires_python(pyproject)
    if requires_python is not None:
        exit_status = _validate_python_constraint_app('requires-python', requires_python)

    for dep_name, constraint in _get_uv_dependencies(pyproject):
        if dep_name in ignore:
            continue
        if exit_status != 0:
            _validate_package_constraint_app(dep_name, constraint)
        else:
            exit_status = _validate_package_constraint_app(dep_name, constraint)

    return exit_status


def _validate_python_constraint_app(dep_name: str, constraint: str) -> int:
    """Applications should use ~= for python (compatible release)."""
    if '~=' not in constraint:
        print(f'INCORRECT FORMAT: {dep_name} = "{constraint}"')
        print('Applications should use ~= when defining python version in requires-python. ' 'For example: requires-python = "~=3.10"')
        return 1
    return 0


def _validate_package_constraint_app(dep_name: str, constraint: str) -> int:
    """Application packages should use ~= (compatible release)."""
    if '~=' not in constraint:
        print(f'INCORRECT FORMAT: {dep_name} = "{constraint}"')
        print('All application package constraints should use ~= (compatible release). ' 'For example: tatari-metrics = "~=1.0.1"')
        return 1
    return 0


if __name__ == '__main__':
    parser = ArgumentParser(description='Validate dependency constraint formats for Python application repos (uv).')
    parser.add_argument('--ignore', nargs='+', default=[], help='List of packages to ignore constraint checking for.')
    args = parser.parse_args()
    exit(validate_constraints(args.ignore))
