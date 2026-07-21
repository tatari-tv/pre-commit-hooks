'''
Validate dependency constraint formats for Python package repos (uv / PEP 621).

Reads ``[project.dependencies]`` and ``[project.requires-python]`` from
pyproject.toml. Per the SRE Python Software Development Policy, package repos use
open lower-bound constraints for downstream flexibility:

- every dependency uses a ``>=`` lower bound with no ``<`` upper cap
  (e.g. ``tatari-foo>=1.2.0``)
- ``requires-python`` uses ``>=`` or ``~=``

Deps that must stay exact can be passed via ``--ignore``. This hook only
validates uv/PEP 621 projects; Poetry projects are covered by
``poetry-pkg-constraints``.
'''

from argparse import ArgumentParser
from collections.abc import Iterator
from re import match

from toml import load

# Operators whose presence means a dependency string carries a version specifier.
_VERSION_OPERATORS = ('>=', '<=', '==', '~=', '!=', '<', '>')


def _normalize(name: str) -> str:
    return name.strip().lower().replace('_', '-').replace('.', '-')


def _iter_dependencies(pyproject: dict) -> Iterator[tuple[str, str]]:
    '''Yield ``(name, specifier)`` for each ``[project.dependencies]`` entry.'''
    dependencies = (pyproject.get('project') or {}).get('dependencies') or []
    for raw in dependencies:
        spec = raw.split(';', 1)[0].strip()  # drop any environment marker
        name_match = match(r'[A-Za-z0-9][A-Za-z0-9._-]*', spec)
        if not name_match:
            continue
        rest = spec[name_match.end() :].strip()
        if rest.startswith('['):  # drop extras, e.g. acryl-datahub[datahub-rest]
            _, _, rest = rest.partition(']')
            rest = rest.strip()
        yield name_match.group(0), rest


def _has_version(specifier: str) -> bool:
    return any(operator in specifier for operator in _VERSION_OPERATORS)


def validate_constraints(ignore: list[str], pyproject_path: str = 'pyproject.toml') -> int:
    pyproject = load(pyproject_path)
    if 'dependencies' not in (pyproject.get('project') or {}):
        print('ERROR: pkg-constraints only validates uv/PEP 621 projects ([project.dependencies]).')
        return 1

    ignored = {_normalize(name) for name in ignore}
    exit_status = 0

    requires_python = (pyproject.get('project') or {}).get('requires-python')
    if requires_python is not None:
        exit_status |= _validate_python_constraint(requires_python)

    for name, specifier in _iter_dependencies(pyproject):
        if _normalize(name) in ignored or not _has_version(specifier):
            continue
        exit_status |= _validate_package_constraint(name, specifier)

    return exit_status


def _validate_python_constraint(constraint: str) -> int:
    if '>=' not in constraint and '~=' not in constraint:
        print(f'INCORRECT FORMAT: requires-python = "{constraint}"')
        print('Packages should use >= (or ~=) for requires-python, e.g. ">=3.12".')
        return 1
    return 0


def _validate_package_constraint(name: str, specifier: str) -> int:
    if '>=' not in specifier or '<' in specifier:
        print(f'INCORRECT FORMAT: {name} = "{specifier}"')
        print('Package dependencies should use an open >= lower bound with no < upper cap, e.g. tatari-foo>=1.2.0.')
        return 1
    return 0


def main() -> None:
    parser = ArgumentParser(description='Validate uv/PEP 621 dependency constraints for Python package repos.')
    parser.add_argument('--ignore', nargs='+', default=[], help='Package names to skip constraint checking for.')
    args = parser.parse_args()
    exit(validate_constraints(args.ignore))


if __name__ == '__main__':
    main()
