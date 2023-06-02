'''
Validate dependency constraint formats for Python package repos.

Currently supported formats are ^ and >=.
'''
from re import match

from toml import load


def validate_constraints(pyproject_path: str = 'pyproject.toml') -> int:
    exit_status = 0

    # Load pyproject.toml as Python object
    pyproject = load(pyproject_path)

    # Iterate over all dependencies to get constraints
    for dep_name, dep_value in pyproject['tool']['poetry']['dependencies'].items():
        # TODO: Remove this logic which only checks for python constraints
        # Eventually want to validate all deps
        if dep_name != 'python':
            continue

        # Handle special cases of version definitions, e.g.:
        # dep = {"version" = "^1.0.0"}
        try:
            constraint = dep_value['version']
        except TypeError:
            constraint = dep_value

        # Regex match on supported formats
        if not match(r'(\^|>=)', constraint):
            print(f'INCORRECT FORMAT: {dep_name} = "{constraint}"')
            exit_status = 1

    return exit_status


if __name__ == '__main__':
    exit(validate_constraints())
