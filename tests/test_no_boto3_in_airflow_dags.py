"""Tests for no_boto3_in_airflow_dags hook."""
import tempfile
from pathlib import Path

from python_hooks.no_boto3_in_airflow_dags import check_file
from python_hooks.no_boto3_in_airflow_dags import main


def _write_py(tmpdir: Path, content: str) -> str:
    pyfile = tmpdir / 'test.py'
    pyfile.write_text(content)
    return str(pyfile)


def test_import_boto3_flagged():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'import boto3\n')
        violations = check_file(path)
        assert len(violations) == 1
        assert violations[0].import_line == 'import boto3'


def test_from_boto3_import_flagged():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'from boto3 import client\n')
        violations = check_file(path)
        assert len(violations) == 1


def test_from_boto3_session_flagged():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'from boto3.session import Session\n')
        violations = check_file(path)
        assert len(violations) == 1


def test_import_boto3_submodule_flagged():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'import boto3.session\n')
        violations = check_file(path)
        assert len(violations) == 1


def test_noqa_suppresses():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'import boto3  # tatari-noqa\n')
        violations = check_file(path)
        assert len(violations) == 0


def test_noqa_from_import_suppresses():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'from boto3 import client  # tatari-noqa\n')
        violations = check_file(path)
        assert len(violations) == 0


def test_no_boto3_clean():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(
            Path(tmpdir),
            'from utils.aws.s3 import get_datalake_bucket\n\nbucket = get_datalake_bucket()\n',
        )
        violations = check_file(path)
        assert len(violations) == 0


def test_botocore_not_flagged():
    """botocore imports are not boto3 imports and should not be flagged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'from botocore.exceptions import ClientError\n')
        violations = check_file(path)
        assert len(violations) == 0


def test_boto3_in_string_not_flagged():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), "x = 'import boto3'\n")
        violations = check_file(path)
        assert len(violations) == 0


def test_multiple_violations():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(
            Path(tmpdir),
            'import boto3\nfrom boto3 import client\n',
        )
        violations = check_file(path)
        assert len(violations) == 2


def test_main_returns_1_on_violation():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'import boto3\n')
        assert main([path]) == 1


def test_main_returns_0_on_clean():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'import os\n')
        assert main([path]) == 0


def test_non_python_file_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        txtfile = Path(tmpdir) / 'notes.txt'
        txtfile.write_text('import boto3\n')
        assert main([str(txtfile)]) == 0


def test_syntax_error_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_py(Path(tmpdir), 'def foo(\n')
        violations = check_file(path)
        assert len(violations) == 0
