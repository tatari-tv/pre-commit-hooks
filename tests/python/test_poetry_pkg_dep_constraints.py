from os.path import dirname

from pytest import raises

from python_hooks.poetry_pkg_dep_constraints import validate_constraints


def test_good_pyproject():
    assert validate_constraints(f'{dirname(__file__)}/data/pkg_good_pyproject.toml') == 0


def test_bad_pyproject():
    assert validate_constraints(f'{dirname(__file__)}/data/pkg_bad_pyproject.toml') == 1


def test_missing_pyproject():
    with raises(FileNotFoundError):
        validate_constraints(f'{dirname(__file__)}/data/missing_pyproject.toml')
