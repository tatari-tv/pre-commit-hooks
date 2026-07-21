import os
import tempfile

import pytest
import toml

from python_hooks.app_constraints import validate_constraints
from tests.python.test_utils.test_toml import write_uv_pyproject_toml


@pytest.mark.parametrize(
    "dependencies, requires_python, expected",
    [
        # bounded ranges + bounded requires-python -> pass
        (["tatari-foo>=1.2.0,<2.0.0"], "~=3.12.0", 0),
        (["tatari-foo>=0.5.8,<0.6.0", "tatari-bar>=5.0.0,<6.0.0"], "==3.12.*", 0),
        (["acryl-datahub[datahub-rest]>=0.14.1.6,<0.15.0"], ">=3.12,<3.13", 0),
        # unbounded / exact / compatible-release dep -> fail
        (["tatari-foo>=1.2.0"], "~=3.12.0", 1),
        (["tatari-foo==1.2.0"], "~=3.12.0", 1),
        (["tatari-foo~=1.2"], "~=3.12.0", 1),
        # unbounded requires-python -> fail
        (["tatari-foo>=1.2.0,<2.0.0"], ">=3.12", 1),
    ],
)
def test_app_constraints(dependencies, requires_python, expected):
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(temp_dir, dependencies, requires_python=requires_python)
        assert validate_constraints([], pyproject) == expected


def test_app_constraints_ignore_runtime_pins():
    with tempfile.TemporaryDirectory() as temp_dir:
        dependencies = ["pyspark==3.5.3", "delta-spark==3.3.1", "tatari-foo>=1.2.0,<2.0.0"]
        pyproject = write_uv_pyproject_toml(temp_dir, dependencies, requires_python="~=3.12.0")
        assert validate_constraints(["pyspark", "delta-spark"], pyproject) == 0
        # without ignore, the exact pins fail the app bounded-range rule
        assert validate_constraints([], pyproject) == 1


def test_app_constraints_skips_unpinned_and_url_deps():
    with tempfile.TemporaryDirectory() as temp_dir:
        dependencies = ["some-pkg", "foo @ git+https://example.com/foo.git", "tatari-foo>=1.2.0,<2.0.0"]
        pyproject = write_uv_pyproject_toml(temp_dir, dependencies, requires_python="~=3.12.0")
        assert validate_constraints([], pyproject) == 0


def test_app_constraints_rejects_poetry_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "pyproject.toml")
        with open(path, "w") as f:
            toml.dump({"tool": {"poetry": {"dependencies": {"python": "~3.12"}}}}, f)
        assert validate_constraints([], path) == 1
