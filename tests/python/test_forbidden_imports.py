from python_hooks.forbidden_imports import check_imports

from os.path import dirname

from pytest import raises

from python_hooks.poetry_app_constraints import validate_constraints


def test_good_imports():
    assert check_imports(f'{dirname(__file__)}/data/forbidden_imports_sample.py', ['SomeOKClass', 'AnotherOKClass']) == 0

# sample file imports date from datetime, which we will say is forbidden
def test_bad_from_imports():
    assert check_imports(f'{dirname(__file__)}/data/forbidden_imports_sample.py', ['date', 'AnotherOKClass']) == 1


# sample file imports tuple, which we will say is forbidden
def test_bad_imports():
    assert check_imports(f'{dirname(__file__)}/data/forbidden_imports_sample.py', ['tuple']) == 1

