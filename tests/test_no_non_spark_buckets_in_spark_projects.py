"""Tests for no_non_spark_buckets_in_spark_projects hook."""
import tempfile
from pathlib import Path

from python_hooks.no_non_spark_buckets_in_spark_projects import check_file
from python_hooks.no_non_spark_buckets_in_spark_projects import is_spark_project
from python_hooks.no_non_spark_buckets_in_spark_projects import main


def test_is_spark_project():
    """Test detection of Spark projects via pyproject.toml."""
    # Create a temporary directory with pyproject.toml
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Test with python-tatari-pyspark dependency
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.9"
python-tatari-pyspark = "^5.0.0"
"""
        )
        assert is_spark_project(pyproject) is True

        # Test with ml-utils dependency
        pyproject.write_text(
            """
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.9"
python-tatari-ml-utils = "^2.0.0"
"""
        )
        assert is_spark_project(pyproject) is True

        # Test with direct pyspark dependency
        pyproject.write_text(
            """
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.9"
pyspark = "3.5.0"
"""
        )
        assert is_spark_project(pyproject) is True

        # Test without Spark dependencies
        pyproject.write_text(
            """
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.9"
requests = "^2.0.0"
"""
        )
        assert is_spark_project(pyproject) is False


def test_check_file_with_violations():
    """Test detection of violations in Spark projects."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create pyproject.toml
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
python-tatari-pyspark = "^5.0.0"
"""
        )

        # Create Python file with problematic import
        pyfile = tmppath / "test.py"
        pyfile.write_text(
            """
from tatari_data_utils.buckets import EnvironmentDefinition

bucket = EnvironmentDefinition.get_default_buckets_for_env().datalake
"""
        )

        violations = check_file(str(pyfile))
        assert len(violations) == 1
        assert "Non-Spark bucket import" in violations[0].message


def test_check_file_with_noqa():
    """Test that noqa comments suppress violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create pyproject.toml
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
python-tatari-pyspark = "^5.0.0"
"""
        )

        # Create Python file with noqa comment
        pyfile = tmppath / "test.py"
        pyfile.write_text(
            """
from tatari_data_utils.buckets import EnvironmentDefinition  # noqa: non-spark-buckets

bucket = EnvironmentDefinition.get_default_buckets_for_env().datalake
"""
        )

        violations = check_file(str(pyfile))
        assert len(violations) == 0


def test_check_file_with_spark_import():
    """Test that Spark imports are not flagged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create pyproject.toml
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
python-tatari-pyspark = "^5.0.0"
"""
        )

        # Create Python file with correct Spark import
        pyfile = tmppath / "test.py"
        pyfile.write_text(
            """
from tatari_data_utils.buckets_spark import EnvironmentDefinitionSpark

bucket = EnvironmentDefinitionSpark.get_default_buckets_for_env().datalake
"""
        )

        violations = check_file(str(pyfile))
        assert len(violations) == 0


def test_check_file_non_spark_project():
    """Test that non-Spark projects are not checked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create pyproject.toml without Spark dependencies
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
python = "^3.9"
requests = "^2.0.0"
"""
        )

        # Create Python file with non-Spark import (should be allowed)
        pyfile = tmppath / "test.py"
        pyfile.write_text(
            """
from tatari_data_utils.buckets import EnvironmentDefinition

bucket = EnvironmentDefinition.get_default_buckets_for_env().datalake
"""
        )

        violations = check_file(str(pyfile))
        assert len(violations) == 0


def test_main_with_violations():
    """Test main function returns error code on violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create pyproject.toml
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
python-tatari-pyspark = "^5.0.0"
"""
        )

        # Create Python file with violation
        pyfile = tmppath / "test.py"
        pyfile.write_text(
            """
from tatari_data_utils import get_default_buckets_for_env
"""
        )

        result = main([str(pyfile)])
        assert result == 1


def test_main_without_violations():
    """Test main function returns 0 on success."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create pyproject.toml
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
python-tatari-pyspark = "^5.0.0"
"""
        )

        # Create Python file without violations
        pyfile = tmppath / "test.py"
        pyfile.write_text(
            """
from tatari_pyspark.utils.buckets import DefaultBuckets
"""
        )

        result = main([str(pyfile)])
        assert result == 0


def test_real_world_ml_impression_level_performance():
    """Test real-world example from ml-impression-level-performance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create pyproject.toml with tatari-pyspark
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry]
name = "impression-level-performance"

[tool.poetry.dependencies]
python = "~3.11"
pyspark = "3.5.0"
tatari-pyspark = "^5.0.0"
"""
        )

        # Create problematic config file
        config_file = tmppath / "config.py"
        config_file.write_text(
            """
from tatari_data_utils import get_default_buckets_for_env
from tatari_pyspark.utils.catalog import get_full_table_path

class AffinityConfig:
    @property
    def scratch_bucket(self):
        return get_default_buckets_for_env().scratch
"""
        )

        violations = check_file(str(config_file))
        assert len(violations) == 1
        assert "get_default_buckets_for_env" in violations[0].import_line


def test_multiple_violations_in_file():
    """Test detection of multiple violations in one file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create pyproject.toml
        pyproject = tmppath / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
pyspark = "3.5.0"
"""
        )

        # Create Python file with multiple violations
        pyfile = tmppath / "test.py"
        pyfile.write_text(
            """
from tatari_data_utils.buckets import EnvironmentDefinition
from tatari_data_utils import get_default_buckets_for_env

bucket1 = EnvironmentDefinition.get_default_buckets_for_env().datalake
bucket2 = get_default_buckets_for_env().scratch
"""
        )

        violations = check_file(str(pyfile))
        assert len(violations) == 2
