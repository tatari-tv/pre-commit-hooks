import os
import tempfile

import pytest
import toml

from python_hooks.pkg_constraints import validate_constraints
from tests.python.test_utils.test_toml import write_uv_pyproject_toml


@pytest.mark.parametrize(
    "dependencies, requires_python, expected",
    [
        # open >= lower bound + >=/~= requires-python -> pass
        (["tatari-foo>=1.2.0"], ">=3.12", 0),
        (["tatari-foo>=1.2.0", "tatari-bar>=5.0.0"], "~=3.12", 0),
        # upper cap / exact / compatible-release dep -> fail
        (["tatari-foo>=1.2.0,<2.0.0"], ">=3.12", 1),
        (["tatari-foo==1.2.0"], ">=3.12", 1),
        (["tatari-foo~=1.2"], ">=3.12", 1),
        # requires-python without >= or ~= -> fail
        (["tatari-foo>=1.2.0"], "==3.12.*", 1),
    ],
)
def test_pkg_constraints(dependencies, requires_python, expected):
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(temp_dir, dependencies, requires_python=requires_python)
        assert validate_constraints([], pyproject) == expected


def test_pkg_constraints_ignore():
    with tempfile.TemporaryDirectory() as temp_dir:
        dependencies = ["tatari-foo>=1.2.0", "pinned==1.0.0"]
        pyproject = write_uv_pyproject_toml(temp_dir, dependencies, requires_python=">=3.12")
        assert validate_constraints(["pinned"], pyproject) == 0
        assert validate_constraints([], pyproject) == 1


def test_pkg_constraints_rejects_poetry_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "pyproject.toml")
        with open(path, "w") as f:
            toml.dump({"tool": {"poetry": {"dependencies": {"python": "^3.12"}}}}, f)
        assert validate_constraints([], path) == 1
