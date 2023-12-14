from os.path import dirname

from python_hooks.forbidden_imports import check_imports


def test_good_imports():
    assert check_imports(f'{dirname(__file__)}/data/forbidden_imports_sample.py', ['SomeOKClass', 'AnotherOKClass']) == 0


# sample file imports date from datetime, which we will say is forbidden
def test_bad_from_imports():
    assert check_imports(f'{dirname(__file__)}/data/forbidden_imports_sample.py', ['date', 'AnotherOKClass']) == 1


# sample file imports dataclass, which we will say is forbidden
def test_bad_imports():
    assert check_imports(f'{dirname(__file__)}/data/forbidden_imports_sample.py', ['dataclass']) == 1


# sample file imports enum aliased en, which we will say is forbidden
def test_bad_imports_aliased():
    assert check_imports(f'{dirname(__file__)}/data/forbidden_imports_sample.py', ['enum']) == 1
