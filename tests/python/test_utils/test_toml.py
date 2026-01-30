import os
from typing import Optional

import toml


def write_pyproject_toml(temp_dir: str, deps: dict[str, str]) -> str:
    toml_file_path = os.path.join(temp_dir, "pyproject.toml")
    data = {"tool": {"poetry": {"dependencies": deps}}}
    with open(toml_file_path, "w") as toml_file:
        toml.dump(data, toml_file)

    return toml_file_path


def write_uv_pyproject_toml(
    temp_dir: str,
    dependencies: list[str],
    *,
    requires_python: Optional[str] = None,
) -> str:
    """Write a uv/PEP 621 style pyproject.toml (project.dependencies)."""
    toml_file_path = os.path.join(temp_dir, "pyproject.toml")
    data: dict = {"project": {"name": "test", "version": "0.1.0", "dependencies": dependencies}}
    if requires_python is not None:
        data["project"]["requires-python"] = requires_python
    with open(toml_file_path, "w") as toml_file:
        toml.dump(data, toml_file)
    return toml_file_path
