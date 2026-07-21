import pytest

from python_hooks.dockerfile_uv import check_uv


@pytest.mark.parametrize(
    "content, expected",
    [
        # ARG UV_VERSION pin (pyspark Databricks style)
        ('ARG UV_VERSION="0.7.14"\nRUN pip install uv==${UV_VERSION}\n', 0),
        # direct pinned install
        ("RUN pip install uv==0.7.14\n", 0),
        # uv-pinned base image tag (lambda ONBUILD style)
        ("FROM base/python:3.11-uv0.9.16-onbuild-lambda\n", 0),
        # unpinned uv install -> fail
        ("RUN pip install uv\n", 1),
        # poetry-pinned Dockerfile has no uv pin -> fail
        ("RUN pip install poetry~=1.7.1\n", 1),
        # commented-out pin must not satisfy the check
        ("RUN pip install uv\n# uv==0.7.14\n", 1),
    ],
)
def test_dockerfile_uv(tmp_path, content, expected):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(content)
    assert check_uv(str(dockerfile)) == expected
