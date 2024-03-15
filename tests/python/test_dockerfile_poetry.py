from os.path import dirname

from python_hooks.dockerfile_poetry import check_poetry


def test_good_poetry():
    assert check_poetry(f'{dirname(__file__)}/data/dockerfile_good_poetry') == 0


def test_bad_poetry():
    assert check_poetry(f'{dirname(__file__)}/data/dockerfile_bad_poetry') == 1
