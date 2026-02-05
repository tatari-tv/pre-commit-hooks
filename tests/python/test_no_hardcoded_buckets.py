"""Tests for no_hardcoded_buckets hook."""
import tempfile
from pathlib import Path

import pytest

from python_hooks.no_hardcoded_buckets import BUCKET_REGEX
from python_hooks.no_hardcoded_buckets import check_file
from python_hooks.no_hardcoded_buckets import find_bucket_violations
from python_hooks.no_hardcoded_buckets import find_conditional_bucket_violations
from python_hooks.no_hardcoded_buckets import format_violation
from python_hooks.no_hardcoded_buckets import get_suggestion
from python_hooks.no_hardcoded_buckets import has_noqa_comment
from python_hooks.no_hardcoded_buckets import is_comment_or_docstring_line
from python_hooks.no_hardcoded_buckets import main
from python_hooks.no_hardcoded_buckets import REGION_REGEX
from python_hooks.no_hardcoded_buckets import Violation

SAMPLE_FILE = Path(__file__).parent / "data" / "hardcoded_buckets_sample.py"


class TestBucketRegex:
    """Test regex patterns for bucket detection."""

    @pytest.mark.parametrize(
        "bucket_name",
        [
            "tatari-datalake",
            "tatari-datalake-dev",
            "tatari-datalake-staging",
            "tatari-datalake-prod",
            "tatari-datalake-dev-us-east-1",
            "tatari-datalake-staging-us-west-2",
            "tatari-scratch",
            "tatari-scratch-dev-us-east-1",
            "tatari-scratch-useast1",  # Legacy prod format
            "tatari-datalake-temp-dev-us-east-1",
            "tatari-datalake-temp-prod-us-west-2",
            "tatari-gx-dev",
            "tatari-gx-prod-us-east-1",
            "tatari-xcom-staging",
            "tatari-xcom-prod-us-east-1",
            "tatari-data-science",  # Legacy
        ],
    )
    def test_matches_bucket_names(self, bucket_name):
        """Verify regex matches known bucket name patterns."""
        assert BUCKET_REGEX.search(bucket_name), f"Should match: {bucket_name}"

    @pytest.mark.parametrize(
        "non_bucket",
        [
            "my-bucket",
            "tatari-something-else",
            "datalake-dev",
            "tatari_datalake",  # Underscore instead of hyphen
        ],
    )
    def test_does_not_match_non_buckets(self, non_bucket):
        """Verify regex does not match non-bucket strings."""
        assert not BUCKET_REGEX.search(non_bucket), f"Should not match: {non_bucket}"


class TestRegionRegex:
    """Test regex patterns for region detection."""

    @pytest.mark.parametrize(
        "region",
        [
            "us-east-1",
            "us-west-2",
            "useast1",
            "uswest2",
        ],
    )
    def test_matches_regions(self, region):
        """Verify regex matches AWS region patterns."""
        assert REGION_REGEX.search(region), f"Should match: {region}"

    @pytest.mark.parametrize(
        "non_region",
        [
            "eu-west-1",  # Not a Tatari region
            "us-east-2",  # Not a Tatari region
            "useast",  # Missing number
            "east-1",  # Missing prefix
        ],
    )
    def test_does_not_match_non_regions(self, non_region):
        """Verify regex does not match non-Tatari regions."""
        assert not REGION_REGEX.search(non_region), f"Should not match: {non_region}"


class TestNoqaComment:
    """Test noqa comment detection."""

    def test_detects_noqa_comment(self):
        assert has_noqa_comment('bucket = "x"  # noqa: hardcoded-bucket')
        assert has_noqa_comment('bucket = "x"  # NOQA: hardcoded-bucket')
        assert has_noqa_comment('bucket = "x"  #noqa:hardcoded-bucket')

    def test_ignores_other_comments(self):
        assert not has_noqa_comment('bucket = "x"  # this is fine')
        assert not has_noqa_comment('bucket = "x"  # noqa: something-else')
        assert not has_noqa_comment('bucket = "x"')


class TestCommentDocstringDetection:
    """Test comment and docstring line detection."""

    def test_detects_comment_lines(self):
        skip, _ = is_comment_or_docstring_line("# this is a comment", False)
        assert skip

        skip, _ = is_comment_or_docstring_line("  # indented comment", False)
        assert skip

    def test_detects_docstring_boundaries(self):
        # Single-line docstring
        skip, in_ds = is_comment_or_docstring_line('"""Single line docstring"""', False)
        assert skip
        assert not in_ds  # State unchanged for single-line

        # Enter docstring
        skip, in_ds = is_comment_or_docstring_line('"""Start of docstring', False)
        assert skip
        assert in_ds  # Now in docstring

        # Inside docstring
        skip, in_ds = is_comment_or_docstring_line("some text inside", True)
        assert skip
        assert in_ds

        # Exit docstring
        skip, in_ds = is_comment_or_docstring_line('end of docstring"""', True)
        assert skip
        assert not in_ds  # Exited docstring

    def test_normal_code_lines(self):
        skip, in_ds = is_comment_or_docstring_line('bucket = "tatari-datalake"', False)
        assert not skip
        assert not in_ds


class TestFindBucketViolations:
    """Test regex-based bucket detection."""

    def test_finds_hardcoded_buckets(self):
        content = 'BUCKET = "tatari-datalake-dev-us-east-1"'
        lines = content.splitlines()
        violations = find_bucket_violations("test.py", content, lines)
        assert len(violations) == 1
        assert violations[0].violation_type == "bucket"
        assert "tatari-datalake-dev-us-east-1" in violations[0].matched_text

    def test_finds_hardcoded_regions(self):
        content = 'REGION = "us-east-1"'
        lines = content.splitlines()
        violations = find_bucket_violations("test.py", content, lines, check_regions=True)
        assert len(violations) == 1
        assert violations[0].violation_type == "region"

    def test_skips_regions_when_disabled(self):
        content = 'REGION = "us-east-1"'
        lines = content.splitlines()
        violations = find_bucket_violations("test.py", content, lines, check_regions=False)
        assert len(violations) == 0

    def test_skips_noqa_lines(self):
        content = 'BUCKET = "tatari-datalake-dev"  # noqa: hardcoded-bucket'
        lines = content.splitlines()
        violations = find_bucket_violations("test.py", content, lines)
        assert len(violations) == 0

    def test_skips_comments(self):
        content = '# BUCKET = "tatari-datalake-dev-us-east-1"'
        lines = content.splitlines()
        violations = find_bucket_violations("test.py", content, lines)
        assert len(violations) == 0

    def test_skips_docstrings(self):
        content = '''"""
This is a docstring with tatari-datalake-dev-us-east-1
"""
code = "clean"
'''
        lines = content.splitlines()
        violations = find_bucket_violations("test.py", content, lines)
        assert len(violations) == 0


class TestFindConditionalViolations:
    """Test AST-based conditional bucket detection."""

    def test_detects_if_statement_pattern(self):
        content = '''
def get_bucket():
    if is_production():
        return "tatari-scratch-useast1"
    return "tatari-scratch-dev-us-east-1"
'''
        violations = find_conditional_bucket_violations("test.py", content)
        assert len(violations) >= 1
        assert any(v.violation_type == "conditional" for v in violations)

    def test_detects_ternary_pattern(self):
        content = '''
bucket = "tatari-datalake" if is_production() else "tatari-datalake-dev"
'''
        violations = find_conditional_bucket_violations("test.py", content)
        assert len(violations) >= 1
        assert any(v.violation_type == "conditional" for v in violations)

    def test_detects_assignment_pattern(self):
        content = '''
def get_bucket():
    if is_staging():
        bucket = "tatari-scratch-staging-us-west-2"
    else:
        bucket = "tatari-scratch-prod-us-east-1"
    return bucket
'''
        violations = find_conditional_bucket_violations("test.py", content)
        assert len(violations) >= 2

    def test_ignores_non_env_conditionals(self):
        content = '''
if some_other_condition():
    bucket = "tatari-scratch-dev"
'''
        violations = find_conditional_bucket_violations("test.py", content)
        assert len(violations) == 0

    def test_handles_syntax_errors(self):
        content = "def broken(:\n    pass"
        violations = find_conditional_bucket_violations("test.py", content)
        assert len(violations) == 0  # Graceful handling


class TestCheckFile:
    """Test the main file checking function."""

    def test_check_sample_file(self):
        violations = check_file(str(SAMPLE_FILE))
        # Should find multiple violations
        assert len(violations) > 0

        # Should find bucket violations
        bucket_violations = [v for v in violations if v.violation_type == "bucket"]
        assert len(bucket_violations) > 0

        # Should find conditional violations
        conditional_violations = [v for v in violations if v.violation_type == "conditional"]
        assert len(conditional_violations) > 0

    def test_check_clean_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                '''
from tatari_data_utils import EnvironmentDefinition
bucket = EnvironmentDefinition.get_default_buckets_for_env().datalake
'''
            )
            f.flush()
            violations = check_file(f.name)
            assert len(violations) == 0

    def test_check_nonexistent_file(self):
        violations = check_file("/nonexistent/path.py")
        assert len(violations) == 0


class TestFormatViolation:
    """Test violation formatting."""

    def test_basic_format(self):
        v = Violation(
            filename="test.py",
            line=10,
            col_offset=5,
            message="Hardcoded bucket detected.",
            violation_type="bucket",
            matched_text="tatari-datalake",
        )
        output = format_violation(v)
        assert "test.py:10" in output
        assert "Hardcoded bucket detected." in output

    def test_format_with_suggestion(self):
        v = Violation(
            filename="test.py",
            line=10,
            col_offset=5,
            message="Hardcoded bucket detected.",
            violation_type="bucket",
            matched_text="tatari-datalake",
        )
        output = format_violation(v, suggest=True)
        assert "tatari_data_utils" in output or "tatari_pyspark" in output


class TestGetSuggestion:
    """Test suggestion generation."""

    def test_datalake_suggestion(self):
        v = Violation("test.py", 1, 0, "msg", "bucket", "tatari-datalake-dev")
        suggestion = get_suggestion(v)
        assert ".datalake" in suggestion

    def test_scratch_suggestion(self):
        v = Violation("test.py", 1, 0, "msg", "bucket", "tatari-scratch-dev")
        suggestion = get_suggestion(v)
        assert ".scratch" in suggestion

    def test_conditional_suggestion(self):
        v = Violation("test.py", 1, 0, "msg", "conditional", "tatari-scratch")
        suggestion = get_suggestion(v)
        assert "is_production()" in suggestion
        assert "EnvironmentDefinition" in suggestion


class TestMain:
    """Test CLI entry point."""

    def test_no_files(self):
        result = main([])
        assert result == 0

    def test_clean_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            result = main([f.name])
            assert result == 0

    def test_file_with_violations(self):
        result = main([str(SAMPLE_FILE)])
        assert result == 1

    def test_warn_only_mode(self):
        result = main(["--warn-only", str(SAMPLE_FILE)])
        assert result == 0  # Even with violations

    def test_check_regions_flag(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('REGION = "us-east-1"\n')
            f.flush()
            # Without regions (default)
            result = main([f.name])
            assert result == 0

            # With regions enabled
            result = main(["--check-regions", f.name])
            assert result == 1
