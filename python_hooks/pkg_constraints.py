'''
Validate dependency constraint formats for Python package repos

- Python: requires-python should use >= or ~=
- Packages: dependency specifiers should use >= only (no upper bound with <=)
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
    """Yield (dep_name, constraint) from project.dependencies (PEP 621)."""
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
        exit_status = _validate_python_constraint_pkg('requires-python', requires_python)

    for dep_name, constraint in _get_uv_dependencies(pyproject):
        if dep_name in ignore:
            continue
        if exit_status != 0:
            _validate_package_constraint_pkg(dep_name, constraint)
        else:
            exit_status = _validate_package_constraint_pkg(dep_name, constraint)

    return exit_status


def _validate_python_constraint_pkg(dep_name: str, constraint: str) -> int:
    """Packages should use >= or ~= for requires-python."""
    if '>=' not in constraint and '~=' not in constraint:
        print(f'INCORRECT FORMAT: {dep_name} = "{constraint}"')
        print('Packages should use >= or ~= when defining requires-python. ' 'For example: requires-python = ">=3.10"')
        return 1
    return 0


def _validate_package_constraint_pkg(dep_name: str, constraint: str) -> int:
    """Package constraints should use >= only (no <=)."""
    if '>=' not in constraint or '<=' in constraint:
        print(f'INCORRECT FORMAT: {dep_name} = "{constraint}"')
        print('Package constraints should use >= when defining versions. ' 'For example: tatari-pyspark = ">=1.0.14"')
        return 1
    return 0


if __name__ == '__main__':
    parser = ArgumentParser(description='Validate dependency constraint formats for Python package repos (uv).')
    parser.add_argument('--ignore', nargs='+', default=[], help='List of packages to ignore constraint checking for.')
    args = parser.parse_args()
    exit(validate_constraints(args.ignore))
