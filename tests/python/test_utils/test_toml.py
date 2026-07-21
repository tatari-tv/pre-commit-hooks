import os

import toml


def write_pyproject_toml(temp_dir: str, deps: dict[str, str]) -> str:
    toml_file_path = os.path.join(temp_dir, "pyproject.toml")
    data = {"tool": {"poetry": {"dependencies": deps}}}
    with open(toml_file_path, "w") as toml_file:
        toml.dump(data, toml_file)

    return toml_file_path


def write_uv_pyproject_toml(temp_dir: str, dependencies: list[str], requires_python: str | None = None) -> str:
    toml_file_path = os.path.join(temp_dir, "pyproject.toml")
    project: dict = {"dependencies": list(dependencies)}
    if requires_python is not None:
        project["requires-python"] = requires_python
    with open(toml_file_path, "w") as toml_file:
        toml.dump({"project": project}, toml_file)

    return toml_file_path
