"""Pre-commit hook to prevent direct boto3 usage in Airflow DAG files.

Direct boto3 in airflow-dags is wrong in two ways:

1. Inside an operator — runs as the Airflow worker, not the pod's scoped
   K8s service-account role. The call will fail or hit the wrong resources.
2. Outside an operator (module level) — executes on every scheduler parse
   cycle (30s–5 min), causing AWS API throttling and scheduler stalls.

AWS work should happen inside BaseKubernetesPodOperator subclasses, which
inherit their namespace's scoped IAM role. The limited boto3 usage that
legitimately runs in the scheduler/worker context lives in ``utils/aws/``.

Usage:
    python -m python_hooks.no_boto3_in_airflow_dags [files...]

Consumers should exclude the sanctioned boto3 wrapper module in their
``.pre-commit-config.yaml``::

    - id: no-boto3-in-airflow-dags
      exclude: ^utils/aws/
"""
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

NOQA_PATTERN = 'tatari-noqa'


@dataclass
class Violation:
    """Represents a detected violation."""

    filename: str
    line: int
    import_line: str


def check_file(filename: str) -> list[Violation]:
    """Check a single Python file for boto3 imports."""
    violations: list[Violation] = []

    try:
        with open(filename, encoding='utf-8') as f:
            source = f.read()
    except Exception:
        return violations

    lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'boto3' or alias.name.startswith('boto3.'):
                    line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ''
                    if NOQA_PATTERN in line_text:
                        continue
                    violations.append(
                        Violation(
                            filename=filename,
                            line=node.lineno,
                            import_line=line_text.strip(),
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == 'boto3' or node.module.startswith('boto3.')):
                line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ''
                if NOQA_PATTERN in line_text:
                    continue
                violations.append(
                    Violation(
                        filename=filename,
                        line=node.lineno,
                        import_line=line_text.strip(),
                    )
                )

    return violations


def format_violations(violations: list[Violation]) -> str:
    """Format violations for output."""
    lines = []
    for v in violations:
        lines.append(
            f'{v.filename}:{v.line}: Direct boto3 import violation – use a BaseKubernetesPodOperator child class instead to fetch data from AWS, return the s3 prefix to xCom, and read the data from the xCom in the main task'
        )
    return '\n'.join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for the pre-commit hook."""
    parser = argparse.ArgumentParser(description='Check for direct boto3 imports in Airflow DAG files')
    parser.add_argument('filenames', nargs='*', help='Filenames to check')
    args = parser.parse_args(argv)

    all_violations = []

    for filename in args.filenames:
        if not filename.endswith('.py'):
            continue
        violations = check_file(filename)
        all_violations.extend(violations)

    if all_violations:
        print(format_violations(all_violations), file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
