'''
Validate dependency constraint formats for Python package repos.

Python version constraint currently supported formats are ^ and >=.
Package version constraint currently supported format: >=
'''
from argparse import ArgumentParser
from re import match

from toml import load


def validate_constraints(ignore: list[str], pyproject_path: str = 'pyproject.toml') -> int:
    exit_status = 0

    # Load pyproject.toml as Python object
    pyproject = load(pyproject_path)

    # Iterate over all dependencies to get constraints
    for dep_name, dep_value in pyproject['tool']['poetry']['dependencies'].items():
        # Handle special cases of version definitions, e.g.:
        # dep = {"version" = "^1.0.0"}
        try:
            constraint = dep_value['version']
        except TypeError:
            constraint = dep_value

        if dep_name == 'python':
            exit_status = validate_python_constraint(dep_name, constraint)
        elif dep_name not in ignore:
            if exit_status != 0:
                validate_package_constraint(dep_name, constraint)
            else:
                exit_status = validate_package_constraint(dep_name, constraint)
    return exit_status


def validate_python_constraint(dep_name: str, constraint: str) -> int:
    # Regex match on supported formats
    if not match(r'(\^|>=)', constraint):
        print(f'INCORRECT FORMAT: {dep_name} = "{constraint}"')
        print('Packages should use ^ (or less ideally >=) when defining python versions. For example: python = "^3.10"')
        return 1

    return 0


def validate_package_constraint(dep_name: str, constraint: str) -> int:
    # Regex match on supported formats
    if not match(r'>=', constraint) or not (match(r'>=', constraint) and match(r'<=', constraint)):
        print(f'INCORRECT FORMAT: {dep_name} = "{constraint}"')
        print('Package constraints should use >= when defining versions. For example: tatari-pyspark = ">=1.0.14"')
        return 1

    return 0


if __name__ == '__main__':
    parser = ArgumentParser(description="Validate dependency constraint formats for Python package repos.")
    parser.add_argument("--ignore", nargs='+', default=[], help="List of packages to ignore constraint checking for.")
    args = parser.parse_args()
    exit(validate_constraints(args.ignore))
