import tempfile
from os.path import dirname

from pytest import raises

from python_hooks.app_constraints import validate_constraints
from tests.python.test_utils.test_toml import write_uv_pyproject_toml


def test_uv_validate_constraints_correct_python():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(temp_dir, ["tatari-foo~=1.0"], requires_python="~=3.10")
        assert validate_constraints([], pyproject) == 0


def test_uv_validate_constraints_incorrect_python():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(temp_dir, ["tatari-foo~=1.0"], requires_python=">=3.10")
        assert validate_constraints([], pyproject) == 1


def test_uv_validate_constraints_correct_pkg():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(temp_dir, ["tatari-foo~=1.0", "tatari-bar~=2.0"], requires_python="~=3.10")
        assert validate_constraints([], pyproject) == 0


def test_uv_validate_constraints_incorrect_pkg():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(temp_dir, ["tatari-foo>=1.0"], requires_python="~=3.10")
        assert validate_constraints([], pyproject) == 1
        pyproject2 = write_uv_pyproject_toml(temp_dir, ["tatari-foo==1.0"], requires_python="~=3.10")
        assert validate_constraints([], pyproject2) == 1


def test_uv_validate_constraints_ignore():
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(temp_dir, ["tatari-foo>=1.0", "ignored~=1.0"], requires_python="~=3.10")
        assert validate_constraints(["ignored"], pyproject) == 1
        pyproject2 = write_uv_pyproject_toml(temp_dir, ["tatari-foo~=1.0", "ignored>=1.0"], requires_python="~=3.10")
        assert validate_constraints(["ignored"], pyproject2) == 0


def test_uv_fails_on_non_uv_project(capsys):
    """Non-uv (e.g. Poetry-only) pyproject.toml fails with error message."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os
        import toml

        pyproject_path = os.path.join(temp_dir, "pyproject.toml")
        data = {"tool": {"poetry": {"dependencies": {"python": "~3.10"}}}}
        with open(pyproject_path, "w") as f:
            toml.dump(data, f)
        assert validate_constraints([], pyproject_path) == 1
        out, err = capsys.readouterr()
        assert "ERROR" in (out + err)
        assert "uv" in (out + err)


def test_uv_no_requires_python_ok():
    """UV project without requires-python passes (only packages checked)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(temp_dir, ["tatari-foo~=1.0"])
        assert validate_constraints([], pyproject) == 0


def test_uv_dependency_with_semicolon_marker_passes():
    """Dependency with semicolon is validated by constraint only; ~= passes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(
            temp_dir,
            ["tatari-foo~=1.0; python_version>='3.10'"],
            requires_python="~=3.10",
        )
        assert validate_constraints([], pyproject) == 0


def test_uv_dependency_with_semicolon_marker_multiple():
    """Multiple deps, some with markers; constraint part is validated correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(
            temp_dir,
            [
                "tatari-foo~=1.0",
                "tatari-bar~=2.0; sys_platform=='linux'",
            ],
            requires_python="~=3.10",
        )
        assert validate_constraints([], pyproject) == 0


def test_uv_dependency_with_semicolon_marker_fails():
    """Dependency with marker but wrong constraint (>=) fails; marker is stripped before check."""
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(
            temp_dir,
            ["tatari-foo>=1.0; python_version>='3.10'"],
            requires_python="~=3.10",
        )
        assert validate_constraints([], pyproject) == 1


def test_uv_dependency_with_extras_passes():
    """Dependency with extras (brackets) is validated by constraint only; name_part strips [extra]."""
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(
            temp_dir,
            ["tatari-foo[dev]~=1.0"],
            requires_python="~=3.10",
        )
        assert validate_constraints([], pyproject) == 0


def test_uv_dependency_with_extras_multiple():
    """Dependency with multiple extras [dev,test]; constraint ~= passes for app."""
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(
            temp_dir,
            ["tatari-foo[dev,test]~=1.0", "tatari-bar[extra]~=2.0"],
            requires_python="~=3.10",
        )
        assert validate_constraints([], pyproject) == 0


def test_uv_dependency_with_extras_fails():
    """Dependency with extras but wrong constraint (>=) fails; extras are stripped before name check."""
    with tempfile.TemporaryDirectory() as temp_dir:
        pyproject = write_uv_pyproject_toml(
            temp_dir,
            ["tatari-foo[dev]>=1.0"],
            requires_python="~=3.10",
        )
        assert validate_constraints([], pyproject) == 1


def test_missing_pyproject():
    with raises(FileNotFoundError):
        validate_constraints([], f'{dirname(__file__)}/data/missing_pyproject.toml')
