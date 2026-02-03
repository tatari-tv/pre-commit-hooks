"""Pre-commit hook to detect hardcoded Tatari S3 bucket names.

This hook prevents configuration sprawl by detecting:
1. Hardcoded Tatari bucket name strings
2. Hardcoded AWS region strings
3. Environment-conditional bucket assignment patterns (AST-based)

Usage:
    python -m python_hooks.no_hardcoded_buckets [--warn-only] [--suggest] [--no-regions] [files...]
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


# Regex patterns for Tatari bucket names
BUCKET_PATTERNS = [
    # Datalake buckets (various naming conventions)
    r"tatari-datalake(?:-(?:dev|staging|prod|test))?(?:-us-(?:east|west)-\d)?",
    # Scratch buckets (note: prod uses 'tatari-scratch-useast1' without hyphen)
    r"tatari-scratch(?:-(?:dev|staging|prod|test))?(?:-us-(?:east|west)-\d)?",
    r"tatari-scratch-useast\d",  # Legacy production format
    # Temp buckets (90-day expiration)
    r"tatari-datalake-temp-(?:dev|staging|prod)-us-(?:east|west)-\d",
    # Great Expectations buckets
    r"tatari-gx-(?:dev|staging|prod)(?:-us-(?:east|west)-\d)?",
    # XCom buckets (Airflow)
    r"tatari-xcom-(?:dev|staging|prod)(?:-us-(?:east|west)-\d)?",
    # Analysis validation buckets
    r"tatari-analysis-validation-temp-(?:dev|staging|prod)-us-(?:east|west)-\d",
    # Legacy/special buckets
    r"tatari-data-science",  # Legacy production bucket
]

# Hardcoded region strings
REGION_PATTERNS = [
    r"\bus-east-1\b",
    r"\bus-west-2\b",
    r"\buseast1\b",  # Legacy format without hyphens
    r"\buswest2\b",
]

# Combined pattern for bucket detection
BUCKET_REGEX = re.compile("|".join(f"({p})" for p in BUCKET_PATTERNS))
REGION_REGEX = re.compile("|".join(f"({p})" for p in REGION_PATTERNS))

# Environment check function names
ENV_CHECK_FUNCTIONS = {"is_production", "is_staging", "is_prodlike", "is_dev"}

# noqa comment pattern
NOQA_PATTERN = re.compile(r"#\s*noqa:\s*hardcoded-bucket", re.IGNORECASE)


@dataclass
class Violation:
    """Represents a detected violation."""

    filename: str
    line: int
    col_offset: int
    message: str
    violation_type: str  # 'bucket', 'region', or 'conditional'
    matched_text: str | None = None


def is_comment_or_docstring_line(line: str, in_docstring: bool) -> tuple[bool, bool]:
    """Check if a line is a comment or inside a docstring.

    Returns (should_skip, new_in_docstring_state).
    """
    stripped = line.strip()

    # Check for docstring boundaries
    if '"""' in stripped or "'''" in stripped:
        # Count occurrences to handle single-line docstrings
        triple_double = stripped.count('"""')
        triple_single = stripped.count("'''")

        if triple_double >= 2 or triple_single >= 2:
            # Single-line docstring, skip this line but don't change state
            return True, in_docstring
        elif triple_double == 1 or triple_single == 1:
            # Entering or exiting docstring
            return True, not in_docstring

    if in_docstring:
        return True, in_docstring

    # Check for comment-only lines
    if stripped.startswith("#"):
        return True, in_docstring

    return False, in_docstring


def has_noqa_comment(line: str) -> bool:
    """Check if a line has a noqa: hardcoded-bucket comment."""
    return bool(NOQA_PATTERN.search(line))


def find_bucket_violations(filename: str, content: str, lines: list[str], check_regions: bool = True) -> list[Violation]:
    """Find hardcoded bucket names and regions using regex."""
    violations = []
    in_docstring = False

    for line_num, line in enumerate(lines, start=1):
        # Skip comments and docstrings
        should_skip, in_docstring = is_comment_or_docstring_line(line, in_docstring)
        if should_skip:
            continue

        # Skip lines with noqa comment
        if has_noqa_comment(line):
            continue

        # Check for bucket patterns
        for match in BUCKET_REGEX.finditer(line):
            violations.append(
                Violation(
                    filename=filename,
                    line=line_num,
                    col_offset=match.start(),
                    message=f"Hardcoded bucket '{match.group()}' detected.",
                    violation_type="bucket",
                    matched_text=match.group(),
                )
            )

        # Check for region patterns
        if check_regions:
            for match in REGION_REGEX.finditer(line):
                # Skip if this is part of a bucket pattern (already caught)
                if BUCKET_REGEX.search(line):
                    continue
                violations.append(
                    Violation(
                        filename=filename,
                        line=line_num,
                        col_offset=match.start(),
                        message=f"Hardcoded region '{match.group()}' detected.",
                        violation_type="region",
                        matched_text=match.group(),
                    )
                )

    return violations


def find_conditional_bucket_violations(filename: str, content: str) -> list[Violation]:
    """Find environment-conditional bucket logic using AST analysis."""
    violations: list[Violation] = []

    try:
        tree = ast.parse(content, filename=filename)
    except SyntaxError:
        # If we can't parse, fall back to regex-only detection
        return violations

    for node in ast.walk(tree):
        # Check If statements
        if isinstance(node, ast.If):
            if _is_env_check(node.test):
                violations.extend(_check_body_for_buckets(filename, node.body, "if"))
                violations.extend(_check_body_for_buckets(filename, node.orelse, "else"))

        # Check ternary expressions (IfExp)
        elif isinstance(node, ast.IfExp):
            if _is_env_check(node.test):
                for child in [node.body, node.orelse]:
                    if isinstance(child, ast.Constant) and isinstance(child.value, str):
                        if BUCKET_REGEX.search(child.value):
                            violations.append(
                                Violation(
                                    filename=filename,
                                    line=node.lineno,
                                    col_offset=node.col_offset,
                                    message="Environment-conditional bucket logic detected.",
                                    violation_type="conditional",
                                    matched_text=child.value,
                                )
                            )

    return violations


def _is_env_check(node: ast.expr) -> bool:
    """Check if an AST node is a call to an environment check function."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id in ENV_CHECK_FUNCTIONS
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr in ENV_CHECK_FUNCTIONS
    return False


def _check_body_for_buckets(filename: str, body: list[ast.stmt], branch: str) -> list[Violation]:
    """Check an if/else body for bucket assignments or returns."""
    violations = []

    for stmt in body:
        # Check assignments
        if isinstance(stmt, ast.Assign):
            if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                if BUCKET_REGEX.search(stmt.value.value):
                    violations.append(
                        Violation(
                            filename=filename,
                            line=stmt.lineno,
                            col_offset=stmt.col_offset,
                            message="Environment-conditional bucket logic detected.",
                            violation_type="conditional",
                            matched_text=stmt.value.value,
                        )
                    )

        # Check return statements
        elif isinstance(stmt, ast.Return):
            if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                if BUCKET_REGEX.search(stmt.value.value):
                    violations.append(
                        Violation(
                            filename=filename,
                            line=stmt.lineno,
                            col_offset=stmt.col_offset,
                            message="Environment-conditional bucket logic detected.",
                            violation_type="conditional",
                            matched_text=stmt.value.value,
                        )
                    )

    return violations


def get_suggestion(violation: Violation) -> str:
    """Generate a suggestion for fixing the violation."""
    matched = violation.matched_text or ""

    if violation.violation_type == "conditional":
        return """  Avoid: if is_production(): bucket = "tatari-..."
  The bucket utilities handle environment detection automatically:

    from tatari_data_utils import EnvironmentDefinition
    bucket = EnvironmentDefinition.get_default_buckets_for_env().datalake"""

    # Determine bucket type from matched text
    if "datalake" in matched and "temp" in matched:
        accessor = ".temp or .temp['region']"
    elif "datalake" in matched:
        accessor = ".datalake"
    elif "scratch" in matched:
        accessor = ".scratch or .scratch['region']"
    elif "gx" in matched:
        accessor = ".gx"
    elif "xcom" in matched:
        accessor = ".xcom"
    else:
        accessor = ".<bucket_type>"

    return f"""  Use centralized bucket utilities instead:

  For PySpark/Databricks jobs:
    from tatari_pyspark.utils.buckets import DefaultBuckets
    bucket = DefaultBuckets.get_from_environment().scratch['us-east-1']

  For other Python code:
    from tatari_data_utils import EnvironmentDefinition
    bucket = EnvironmentDefinition.get_default_buckets_for_env(){accessor}"""


def format_violation(violation: Violation, suggest: bool = False) -> str:
    """Format a violation for output."""
    output = f"{violation.filename}:{violation.line}: {violation.message}"
    if suggest:
        output += "\n" + get_suggestion(violation)
    return output


def check_file(filename: str, check_regions: bool = True) -> list[Violation]:
    """Check a file for hardcoded bucket violations."""
    try:
        with open(filename) as f:
            content = f.read()
    except OSError as e:
        print(f"Error reading {filename}: {e}", file=sys.stderr)
        return []

    lines = content.splitlines()

    # Find regex-based violations
    violations = find_bucket_violations(filename, content, lines, check_regions)

    # Find AST-based violations
    violations.extend(find_conditional_bucket_violations(filename, content))

    # Deduplicate violations at the same location
    seen = set()
    unique_violations = []
    for v in violations:
        key = (v.filename, v.line, v.col_offset, v.violation_type)
        if key not in seen:
            seen.add(key)
            unique_violations.append(v)

    return unique_violations


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for the hook."""
    parser = argparse.ArgumentParser(description="Check for hardcoded Tatari S3 bucket names")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print violations as warnings but exit 0",
    )
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="Include suggested fixes in output",
    )
    parser.add_argument(
        "--no-regions",
        action="store_true",
        help="Disable detection of hardcoded region strings",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to check",
    )
    args = parser.parse_args(argv)

    if not args.files:
        return 0

    all_violations = []
    for filename in args.files:
        violations = check_file(filename, check_regions=not args.no_regions)
        all_violations.extend(violations)

    if all_violations:
        for violation in all_violations:
            print(format_violation(violation, suggest=args.suggest), file=sys.stderr)

        if args.warn_only:
            return 0
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
