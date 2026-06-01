# Design Document: No boto3 in Airflow DAGs Hook

**Author:** Russell Simco
**Date:** 2026-02-12
**Status:** Draft
**Ticket:** [DAT-4649](https://tatari.atlassian.net/browse/DAT-4649)

## Summary

A pre-commit hook to prevent direct `boto3` imports in the `airflow-dags` repository. There are two failure modes, both bad:

1. **Inside an operator** — boto3 calls run with the Airflow worker's service role, which is not the scoped IAM role for that workload's K8s namespace. The call will fail or hit the wrong resources.
2. **Outside an operator** (module level / DAG body) — boto3 calls execute on every scheduler parse cycle (30s–5 min), causing AWS API throttling and scheduler stalls.

## Problem Statement

### Background

The `airflow-dags` architecture delegates AWS work to Kubernetes pod operators (`BaseKubernetesPodOperator` subclasses). Each operator namespace (e.g. `ingestion-jobs`, `data-operations`) has a dedicated K8s service account with an IAM role scoped to the resources that namespace needs (`compositions/service-roles/`). This is how we enforce least-privilege AWS access.

The limited boto3 usage that legitimately runs in the scheduler/worker context is centralised in `utils/aws/`:
- `utils/aws/__init__.py` — `AWS_ACCOUNT_ID`, `DEFAULT_REGION`
- `utils/aws/s3.py` — bucket resolution, scratch sessions, xcom helpers
- `utils/aws/ecr.py` — image path resolution, tag lookups

All other AWS work should happen inside pod operators, which inherit their namespace's service account role.

### Problem

AI coding agents (Copilot, Cursor, etc.) are proposing PRs that introduce direct `boto3` imports in DAG files and services, bypassing the pod operator pattern. This was caught in [airflow-dags PR #11336](https://github.com/tatari-tv/airflow-dags/pull/11336/changes).

**Impact:**
- **boto3 inside an operator** — runs as the Airflow worker, not the pod's scoped service role. The call will fail or access the wrong resources, and circumvents the namespace-level least-privilege model.
- **boto3 outside an operator** (module/import level) — executes on every scheduler parse cycle, causing AWS API throttling, credential failures, and scheduler stalls across all DAGs.
- **Difficult to audit** — AWS access spread across DAG files instead of contained in pod operators and `utils/aws/`.

### Goals

- **Detect** `import boto3` and `from boto3 import ...` in Python files
- **Provide** a concise error message that guides both humans and AI agents to the correct pattern
- **Support** `# tatari-noqa` inline suppression
- **Allow** the consumer to exclude sanctioned paths (e.g. `utils/aws/`) via `.pre-commit-config.yaml`

### Non-Goals

- Detecting `botocore` imports — these are type/exception imports and don't make API calls
- Detecting dynamic imports via `importlib`
- Auto-fixing violations
- Enforcing this in repositories other than `airflow-dags` (though it could be reused)

## Design

### Overview

A Python-based pre-commit hook (`no-boto3-in-airflow-dags`) that uses AST parsing to detect `import boto3` and `from boto3 import ...` statements, then reports one-line violations to stderr.

### Architecture

```
pre-commit-hooks/
├── python_hooks/
│   └── no_boto3_in_airflow_dags.py          # Hook implementation
├── tests/
│   └── test_no_boto3_in_airflow_dags.py     # Test suite
├── .pre-commit-hooks.yaml                    # Hook definitions (updated)
└── docs/
    └── design/
        └── 2026-02-12-no-boto3-in-airflow-dags.md  # This document
```

### Detection Logic

Uses `ast.walk()` to find `Import` and `ImportFrom` nodes where the module is `boto3` or starts with `boto3.`. This avoids false positives from string literals, comments, or `botocore` imports.

```python
# Flagged
import boto3
import boto3.session
from boto3 import client
from boto3.session import Session

# Not flagged
from botocore.exceptions import ClientError
x = 'import boto3'
from utils.aws.s3 import get_datalake_bucket
```

### Inline Suppression

Lines containing `# tatari-noqa` are skipped, consistent with other hooks in this repo (`disallowed-identifiers`, `image-tag-branch-constraint`).

```python
import boto3  # tatari-noqa
```

### Consumer Configuration

In `airflow-dags/.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/tatari-tv/pre-commit-hooks
  rev: <tag>
  hooks:
    - id: no-boto3-in-airflow-dags
      exclude: ^utils/aws/
```

The `exclude` pattern allows the existing `utils/aws/` module to continue using boto3 directly.

### Output Format

One line per violation:

```
dags/my_dag.py:5: Direct boto3 import – use utils/aws/ instead (suppress with # tatari-noqa)
```

### Exit Codes

- `0` — no violations
- `1` — violations detected (details on stderr)

## Rollout

### Phase 1: Hook Implementation (Complete)
- Hook, tests, and `.pre-commit-hooks.yaml` entry in `pre-commit-hooks` repo

### Phase 2: Adopt in airflow-dags
1. Merge this PR and tag a release
2. Update `airflow-dags/.pre-commit-config.yaml` to add the hook with `exclude: ^utils/aws/`
3. Verify no existing violations outside `utils/aws/`

## Trade-offs

| Aspect | Trade-off | Mitigation |
|--------|-----------|------------|
| **Scope** | Only catches static imports, not `importlib` | Dynamic boto3 imports are rare in DAG files |
| **False positives** | None expected outside `utils/aws/` | Consumer excludes `utils/aws/` in config |
| **Agent guidance** | Error message must be useful to AI agents | Message names the correct alternative directly |
| **Maintenance** | If `utils/aws/` path changes, consumer config needs updating | Low likelihood; path has been stable |

## References

- [DAT-4649](https://tatari.atlassian.net/browse/DAT-4649) — Ticket
- [airflow-dags PR #11336](https://github.com/tatari-tv/airflow-dags/pull/11336/changes) — Example of the antipattern
- [pre-commit-hooks PR #39](https://github.com/tatari-tv/pre-commit-hooks/pull/39) — Prior art (no-non-spark-buckets hook)
