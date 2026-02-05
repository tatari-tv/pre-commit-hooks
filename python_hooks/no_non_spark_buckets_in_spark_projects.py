"""Pre-commit hook to detect non-Spark bucket imports in Spark projects.

This hook prevents incorrect bucket resolution in PySpark and ML projects by detecting:
1. Imports from tatari_data_utils.buckets (non-Spark version)
2. Imports of get_default_buckets_for_env from tatari_data_utils
in projects that depend on python-tatari-pyspark, python-tatari-ml-utils, or pyspark.

After the single-region consolidation, dev/staging environments migrated from us-west-2
to us-east-1. The non-Spark version still defaults to us-west-2, while the Spark version
(DefaultBucketsSpark/EnvironmentDefinitionSpark) correctly resolves to us-east-1.

Usage:
    python -m python_hooks.no_non_spark_buckets_in_spark_projects [files...]
"""
from __future__ import annotations

import argparse
import re
import sys
import toml
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


# Patterns to detect problematic imports
NON_SPARK_IMPORT_PATTERNS = [
    # Direct imports from tatari_data_utils.buckets
    re.compile(r"from\s+tatari_data_utils\.buckets\s+import\s+"),
    # Import of get_default_buckets_for_env from tatari_data_utils
    re.compile(r"from\s+tatari_data_utils\s+import\s+.*get_default_buckets_for_env"),
]

# Pattern to exclude imports from buckets_spark (which are correct)
SPARK_IMPORT_PATTERN = re.compile(r"buckets_spark")

# noqa comment pattern
NOQA_PATTERN = re.compile(r"#\s*noqa:\s*non-spark-buckets", re.IGNORECASE)

# Spark-related dependencies that require Spark bucket imports
SPARK_DEPENDENCIES = {
    "python-tatari-pyspark",  # v5.0.0+ wraps DefaultBucketsSpark
    "python-tatari-ml-utils", # v2.0.0+ wraps DefaultBucketsSpark
    "tatari-pyspark",         # Alternative naming
    "tatari-ml-utils",        # Alternative naming
    "pyspark",                # Direct PySpark usage (may need Spark buckets)
}


@dataclass
class Violation:
    """Represents a detected violation."""

    filename: str
    line: int
    message: str
    import_line: str


def find_pyproject_toml(start_path: Path) -> Path | None:
    """Find the pyproject.toml file by walking up the directory tree."""
    current = start_path.resolve()
    
    # If start_path is a file, start from its parent
    if current.is_file():
        current = current.parent
    
    # Walk up the directory tree
    while current != current.parent:
        pyproject = current / "pyproject.toml"
        if pyproject.exists():
            return pyproject
        current = current.parent
    
    return None


def is_spark_project(pyproject_path: Path) -> bool:
    """Check if project depends on PySpark or ML utilities."""
    try:
        with open(pyproject_path, "r") as f:
            data = toml.load(f)
        
        # Check poetry dependencies
        if "tool" in data and "poetry" in data["tool"]:
            dependencies = data["tool"]["poetry"].get("dependencies", {})
            
            for dep_name in dependencies:
                if dep_name in SPARK_DEPENDENCIES:
                    return True
        
        return False
    except Exception:
        # If we can't read the file, assume it's not a Spark project
        return False


def check_file(filename: str) -> list[Violation]:
    """Check a single Python file for non-Spark bucket imports."""
    violations = []
    
    # Find pyproject.toml
    file_path = Path(filename)
    pyproject = find_pyproject_toml(file_path)
    
    # Skip if no pyproject.toml found
    if not pyproject:
        return violations
    
    # Skip if not a Spark project
    if not is_spark_project(pyproject):
        return violations
    
    # Read the file
    try:
        with open(filename, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return violations
    
    # Check each line
    for line_num, line in enumerate(lines, start=1):
        # Skip if line has noqa comment
        if NOQA_PATTERN.search(line):
            continue
        
        # Skip if this is importing from buckets_spark (correct)
        if SPARK_IMPORT_PATTERN.search(line):
            continue
        
        # Check for problematic imports
        for pattern in NON_SPARK_IMPORT_PATTERNS:
            if pattern.search(line):
                violations.append(
                    Violation(
                        filename=filename,
                        line=line_num,
                        message=(
                            "Non-Spark bucket import detected in PySpark/ML project. "
                            "Use 'tatari_data_utils.buckets_spark' instead."
                        ),
                        import_line=line.strip(),
                    )
                )
                break
    
    return violations


def format_violations(violations: list[Violation]) -> str:
    """Format violations for output."""
    if not violations:
        return ""
    
    output = []
    output.append("\n" + "=" * 80)
    output.append("ERROR: Non-Spark bucket imports detected in Spark projects")
    output.append("=" * 80)
    output.append("")
    
    for v in violations:
        output.append(f"  {v.filename}:{v.line}")
        output.append(f"    {v.message}")
        output.append(f"    Import: {v.import_line}")
        output.append("")
    
    output.append("Why this matters:")
    output.append("  - After single-region consolidation (Feb 2026), dev/staging moved from")
    output.append("    us-west-2 to us-east-1")
    output.append("  - The non-Spark version still defaults to us-west-2 for dev/staging")
    output.append("  - The Spark version (DefaultBucketsSpark) forces us-east-1 for all")
    output.append("    Databricks environments")
    output.append("  - Using the wrong version causes access errors and cross-region transfers")
    output.append("")
    output.append("How to fix:")
    output.append("")
    output.append("  Option 1 - Use tatari-pyspark wrapper (recommended):")
    output.append("    # Bad")
    output.append("    from tatari_data_utils import get_default_buckets_for_env")
    output.append("    # Good")
    output.append("    from tatari_pyspark.utils.buckets import DefaultBuckets")
    output.append("    buckets = DefaultBuckets.get_from_environment()")
    output.append("")
    output.append("  Option 2 - Use tatari-ml-utils wrapper:")
    output.append("    # Bad")
    output.append("    from tatari_data_utils import get_default_buckets_for_env")
    output.append("    # Good")
    output.append("    from tatari_ml_utils.buckets import DefaultBuckets")
    output.append("    buckets = DefaultBuckets.get_from_environment()")
    output.append("")
    output.append("  Option 3 - Use Spark version directly:")
    output.append("    # Bad")
    output.append("    from tatari_data_utils.buckets import EnvironmentDefinition")
    output.append("    # Good")
    output.append("    from tatari_data_utils.buckets_spark import EnvironmentDefinitionSpark")
    output.append("")
    output.append("More info:")
    output.append("  https://tatari.atlassian.net/wiki/spaces/DATA/pages/2326528229")
    output.append("")
    output.append("To suppress this check for specific lines (use sparingly):")
    output.append("    from tatari_data_utils import get_default_buckets_for_env  # noqa: non-spark-buckets")
    output.append("")
    output.append("=" * 80)
    
    return "\n".join(output)


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for the pre-commit hook."""
    parser = argparse.ArgumentParser(
        description="Check for non-Spark bucket imports in Spark projects"
    )
    parser.add_argument("filenames", nargs="*", help="Filenames to check")
    args = parser.parse_args(argv)
    
    all_violations = []
    
    for filename in args.filenames:
        # Only check Python files
        if not filename.endswith(".py"):
            continue
        
        violations = check_file(filename)
        all_violations.extend(violations)
    
    if all_violations:
        print(format_violations(all_violations), file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
