import tempfile
from os.path import dirname

from pytest import raises

from python_hooks.poetry_app_constraints import validate_constraints
from tests.python.test_utils.test_toml import write_pyproject_toml


def test_validate_constraints_correct_python():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_pyproject_toml(temp_dir, {"python": "~3.10"})
        assert validate_constraints([], pyproject) == 0


def test_validate_constraints_incorrect_python():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_pyproject_toml(temp_dir, {"python": "^3.10"})
        assert validate_constraints([], pyproject) == 1


def test_validate_constraints_correct_pkg():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_pyproject_toml(temp_dir, {"tatari-foo": "^3.10", "tatari-bar": "^3.13"})
        assert validate_constraints([], pyproject) == 0


def test_validate_constraints_incorrect_pkg():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_pyproject_toml(temp_dir, {"tatari-foo": ">=3.10"})
        assert validate_constraints([], pyproject) == 1
        pyproject2 = write_pyproject_toml(temp_dir, {"tatari-foo": "3.10"})
        assert validate_constraints([], pyproject2) == 1
        pyproject3 = write_pyproject_toml(temp_dir, {"tatari-foo": ">=3.3.2,<=3.4.1"})
        assert validate_constraints([], pyproject3) == 1
        pyproject4 = write_pyproject_toml(temp_dir, {"tatari-foo": "~3.4.1"})
        assert validate_constraints([], pyproject4) == 1


def test_missing_pyproject():
    with raises(FileNotFoundError):
        validate_constraints([], f'{dirname(__file__)}/data/missing_pyproject.toml')
