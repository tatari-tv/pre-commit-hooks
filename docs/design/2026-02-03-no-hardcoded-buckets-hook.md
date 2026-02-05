# Design Document: No Hardcoded Buckets Pre-commit Hook

**Author:** Scott Idler
**Date:** 2026-02-03
**Status:** Draft
**Review Passes Completed:** 5/5

## Summary

A pre-commit hook to detect and prevent hardcoded S3 bucket names and environment-specific bucket logic in Tatari codebases. This enforces usage of the centralized `tatari-data-utils` package, preventing the configuration sprawl that required coordinated multi-repo cleanup efforts.

## Problem Statement

### Background

Tatari operates data infrastructure across multiple AWS regions (us-east-1, us-west-2) and environments (dev, staging, prod). S3 buckets follow naming conventions like:
- `tatari-datalake-{env}-{region}` (e.g., `tatari-datalake-dev-us-east-1`)
- `tatari-scratch-{env}-{region}` (e.g., `tatari-scratch-staging-us-west-2`)
- `tatari-datalake-temp-{env}-{region}`

Historically, developers implemented environment/bucket selection logic inline:

```python
# Anti-pattern found across dozens of files
if is_production():
    return 'tatari-scratch-useast1'
else:
    return 'tatari-scratch-staging-us-west-2'
```

This pattern was duplicated across repositories including:
- airflow-dags
- pyspark-data-science-jobs
- pyspark-calculation-jobs
- python-tatari-pyspark
- python-tatari-ml-utils

### Problem

When Tatari consolidated Databricks environments to a single AWS region (us-east-1), the migration required:
- Updating 20+ files per repository
- Coordinating changes across 5+ repositories
- Major version bumps to multiple packages (tatari-data-utils 1.0.0, tatari-pyspark 5.0.0)

Even after the cleanup, new hardcoded patterns continue to appear because there's no automated enforcement.

### Goals

- **Detect** hardcoded Tatari S3 bucket names in Python files
- **Detect** environment-conditional bucket logic (`if is_production(): bucket = "..."`)
- **Enforce** usage of `tatari-data-utils` APIs for bucket resolution
- **Provide** clear error messages guiding developers to the correct approach
- **Integrate** with pre-commit framework for easy adoption across repos

### Non-Goals

- Detecting bucket names in configuration files (YAML, JSON, Terraform `.tf`/`.tfvars`) - these may be intentional
- Detecting bucket names in test fixtures - these are often intentional mocks
- Auto-fixing violations - too complex and risky
- Enforcing specific import patterns - just prevent the anti-patterns
- Flagging the source-of-truth packages themselves (`python-tatari-data-utils`, `python-tatari-pyspark`) - they define the buckets legitimately
- Detecting bucket names in comments or docstrings - these are documentation

## Proposed Solution

### Overview

Create a Python-based pre-commit hook (`no-hardcoded-buckets`) that scans Python files for:
1. Hardcoded Tatari bucket name strings
2. Environment-conditional bucket assignment patterns

The hook will be added to the existing `tatari-tv/pre-commit-hooks` repository.

### Architecture

```
pre-commit-hooks/
├── python_hooks/
│   ├── no_hardcoded_buckets.py    # Main hook implementation
│   └── utills/
│       └── ignore_check.py        # Existing utility (reuse)
├── tests/
│   └── python/
│       ├── test_no_hardcoded_buckets.py
│       └── data/
│           └── hardcoded_buckets_sample.py
├── .pre-commit-hooks.yaml          # Hook definitions (update)
└── pyproject.toml                  # Dependencies (update)
```

This follows the existing repository structure where hooks live in `python_hooks/` and tests in `tests/python/`.

### Detection Patterns

#### Pattern 1: Hardcoded Bucket Names

Regex pattern to match Tatari bucket naming conventions:

```python
BUCKET_PATTERNS = [
    # Datalake buckets (various naming conventions)
    r'tatari-datalake(?:-(?:dev|staging|prod|test))?(?:-us-(?:east|west)-\d)?',

    # Scratch buckets (note: prod uses 'tatari-scratch-useast1' without hyphen)
    r'tatari-scratch(?:-(?:dev|staging|prod|test))?(?:-us-(?:east|west)-\d)?',
    r'tatari-scratch-useast\d',  # Legacy production format

    # Temp buckets (90-day expiration)
    r'tatari-datalake-temp-(?:dev|staging|prod)-us-(?:east|west)-\d',

    # Great Expectations buckets
    r'tatari-gx-(?:dev|staging|prod)(?:-us-(?:east|west)-\d)?',

    # XCom buckets (Airflow)
    r'tatari-xcom-(?:dev|staging|prod)(?:-us-(?:east|west)-\d)?',

    # Analysis validation buckets
    r'tatari-analysis-validation-temp-(?:dev|staging|prod)-us-(?:east|west)-\d',

    # Legacy/special buckets
    r'tatari-data-science',  # Legacy production bucket
]

# Hardcoded region strings (outside of bucket context)
REGION_PATTERNS = [
    r'\bus-east-1\b',
    r'\bus-west-2\b',
    r'\buseast1\b',   # Legacy format without hyphens
    r'\buswest2\b',
]
```

Note: These patterns are derived from actual bucket names found in `tatari-data-utils` and the cleanup PRs. The production scratch bucket uses a non-standard format (`tatari-scratch-useast1`) which must be explicitly matched.

Region patterns use word boundaries (`\b`) to avoid false positives in unrelated strings.

#### Pattern 2: Environment-Conditional Bucket Logic

AST-based detection for patterns where environment checks are combined with bucket-like string literals:

```python
# Pattern 2a: If statement with environment check and bucket string
# AST: If node where test calls is_production/is_staging/is_prodlike
#      and body/orelse contains Assign with bucket string value
if is_production():
    bucket = 'tatari-scratch-useast1'      # FLAGGED
else:
    bucket = 'tatari-scratch-dev-us-east-1' # FLAGGED

# Pattern 2b: Ternary with environment check
# AST: IfExp node where test calls is_production/is_staging/is_prodlike
#      and body/orelse are Constant strings matching bucket pattern
bucket = 'tatari-datalake' if is_production() else 'tatari-datalake-dev-us-east-1'  # FLAGGED

# Pattern 2c: Return statements with conditional buckets
# AST: Return node inside If block with environment check
def get_bucket():
    if is_production():
        return 'tatari-scratch-useast1'  # FLAGGED
    return 'tatari-scratch-dev-us-east-1' # FLAGGED
```

**Implementation approach:** Walk AST looking for `If` or `IfExp` nodes where:
1. The test is a `Call` to `is_production`, `is_staging`, `is_prodlike`, `is_dev`
2. The body or orelse contains string constants matching bucket patterns

### API Design

#### Command Line Interface

```bash
# Direct invocation (matches existing hook patterns)
python -m python_hooks.no_hardcoded_buckets [files...]

# With suggestions for fixes
python -m python_hooks.no_hardcoded_buckets --suggest [files...]

# Warn only (exit 0 even with violations)
python -m python_hooks.no_hardcoded_buckets --warn-only [files...]

# Also check for hardcoded region strings
python -m python_hooks.no_hardcoded_buckets --check-regions [files...]

# Via pre-commit
pre-commit run no-hardcoded-buckets --all-files
```

#### CLI Flags

| Flag | Description |
|------|-------------|
| `--warn-only` | Print violations as warnings but exit 0 (don't fail the hook) |
| `--suggest` | Include suggested fixes in output |
| `--check-regions` | Enable detection of hardcoded region strings (disabled by default) |

#### Exit Codes

- `0` - No violations found (or `--warn-only` specified)
- `1` - Violations detected (with details printed to stderr)

#### Output Format

```
pyspark_jobs/bi/pacing.py:42: Hardcoded bucket 'tatari-scratch-useast1' detected.
  Use centralized bucket utilities instead:

  For PySpark/Databricks jobs:
    from tatari_pyspark.utils.buckets import DefaultBuckets
    bucket = DefaultBuckets.get_from_environment().scratch['us-east-1']

  For other Python code:
    from tatari_data_utils import EnvironmentDefinition
    bucket = EnvironmentDefinition.get_default_buckets_for_env().scratch

pyspark_jobs/etl/base.py:15: Environment-conditional bucket logic detected.
  Avoid: if is_production(): bucket = "tatari-..."
  The bucket utilities handle environment detection automatically:

    from tatari_data_utils import EnvironmentDefinition
    bucket = EnvironmentDefinition.get_default_buckets_for_env().datalake
```

**Bucket type mapping for suggestions:**
| String contains | Suggested accessor |
|-----------------|-------------------|
| `datalake` | `.datalake` |
| `scratch` | `.scratch` or `.scratch['region']` |
| `temp` | `.temp` or `.temp['region']` |

### Exclusions

Allow legitimate uses via:

1. **File-level exclusion** in `.pre-commit-config.yaml`:
   ```yaml
   - id: no-hardcoded-buckets
     exclude: ^tests/fixtures/
   ```

2. **Inline suppression** comment:
   ```python
   BUCKET = 'tatari-datalake-test-us-east-1'  # noqa: hardcoded-bucket
   ```

3. **Test file detection**: Automatically more lenient in files matching `test_*.py` or `*_test.py`

4. **Source-of-truth packages**: The hook should NOT be enabled for:
   - `python-tatari-data-utils` - defines the bucket mappings
   - `python-tatari-pyspark` - re-exports bucket utilities

   These repos should exclude the hook in their `.pre-commit-config.yaml`:
   ```yaml
   - id: no-hardcoded-buckets
     exclude: ^tatari_data_utils/buckets.*\.py$
   ```

   **GX bucket exclusions**: The following repos currently define `tatari-gx-*` buckets in base classes and should exclude those paths until consolidated into `tatari-data-utils` (see [GX Upgrade Tech Spec](https://tatari.atlassian.net/wiki/spaces/ir/pages/2325053494/Tech+Spec+Great+Expectations+Upgrade)):
   - `philo` - excludes `script/data_quality/gx_base.py`
   - `python-tatari-pyspark` - excludes `tatari_pyspark/job/gx_base.py`

   ```yaml
   - id: no-hardcoded-buckets
     exclude: gx_base\.py$
   ```

5. **Comments and docstrings**: AST-based detection naturally ignores these since they're not `Constant` nodes in executable code. Regex-based detection should skip lines that are comments (`#`) or inside docstrings.

### Implementation Plan

#### Phase 1: Core Detection
- Implement regex-based hardcoded bucket detection
- Add CLI entry point following existing patterns (argparse, sys.exit)
- Add to `.pre-commit-hooks.yaml`:

```yaml
- id: no-hardcoded-buckets
  name: no-hardcoded-buckets
  description: Check for hardcoded Tatari S3 bucket names
  entry: python -m python_hooks.no_hardcoded_buckets
  language: python
  types: [python]
```

#### Phase 2: AST Analysis
- Add AST-based detection for conditional bucket logic
- Handle ternary expressions and if/else blocks

#### Phase 3: Polish
- Add inline suppression support
- Improve error messages with suggested fixes
- Add comprehensive test suite

## Alternatives Considered

### Alternative 1: Grep-based Hook (Shell Script)

- **Description:** Simple shell script using grep/ripgrep
- **Pros:** No Python dependencies, fast, simple
- **Cons:** Can't do AST analysis for conditional patterns, harder to maintain complex regex
- **Why not chosen:** Need AST analysis to detect `if is_production()` patterns reliably

### Alternative 2: Semgrep Rules

- **Description:** Use Semgrep for pattern matching
- **Pros:** Powerful pattern matching, language-aware, existing ecosystem
- **Cons:** External dependency, learning curve, may be overkill
- **Why not chosen:** Adds external tool dependency; custom Python hook is sufficient and keeps tooling in-house

### Alternative 3: Ruff Custom Rules

- **Description:** Write custom Ruff lint rules
- **Pros:** Fast, integrates with existing Ruff usage
- **Cons:** Custom rules require Rust, complex to maintain
- **Why not chosen:** Rust maintenance burden too high for this use case

### Alternative 4: Import Enforcement Only

- **Description:** Only check that `tatari-data-utils` is imported, not that buckets are hardcoded
- **Pros:** Simpler implementation
- **Cons:** Doesn't catch the actual anti-pattern; importing doesn't mean using correctly
- **Why not chosen:** Doesn't solve the core problem

## Technical Considerations

### Dependencies

- Python 3.9+ (matches tatari-data-utils requirement)
- No external dependencies beyond stdlib (ast, re, argparse)

### Performance

- Regex scanning: O(n) per file, negligible for typical file sizes
- AST parsing: Performed on all Python files to detect conditional patterns accurately
- Existing hooks in this repo (e.g., `forbidden_imports.py`) already parse AST for every file
- Expected: <100ms for typical repository scan (consistent with existing hooks)

### Security

No security implications - this is a read-only static analysis tool.

### Testing Strategy

1. **Unit tests** for regex patterns against known bucket name variations
2. **Unit tests** for AST detection with sample code snippets
3. **Integration tests** with actual files from past PRs as test fixtures
4. **Edge cases to test:**
   - F-strings: `f"s3://{BUCKET}/path"` where BUCKET is a hardcoded constant
   - String concatenation: `"tatari-datalake-" + env` (harder to detect, may skip)
   - Comments containing bucket names (should NOT flag)
   - Docstrings with bucket examples (should NOT flag)
   - Databricks notebooks (`.py` files with `# COMMAND ----------`)
   - Multiline strings and triple-quoted strings
   - Bucket names in dict keys vs values

### Rollout Plan

1. Add hook to `pre-commit-hooks` repo
2. Test on `pyspark-data-science-jobs` (known to have violations)
3. Document in README with migration guide
4. Announce to Data Platform team
5. Add to recommended `.pre-commit-config.yaml` template
6. Optionally: Add as required hook in CI for data repos

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False positives in test files | Medium | Low | Auto-detect test files, provide exclusion mechanisms |
| False positives in config/fixture files | Medium | Medium | Limit to `.py` files, provide `exclude` pattern |
| Developers bypass with `# noqa` | Low | Low | Acceptable - conscious choice to bypass |
| Missing bucket name patterns | Medium | Medium | Start comprehensive, add patterns as discovered |
| AST parsing fails on syntax errors | Low | Low | Fall back to regex-only, let other linters catch syntax |
| String concatenation patterns missed | Medium | Low | Document limitation; these are rarer and harder to detect |
| F-string with hardcoded bucket in variable | Medium | Medium | AST can detect f-strings; check JoinedStr nodes |
| Source-of-truth repos flagged incorrectly | Low | High | Document required exclusions; repos must opt-out |

## Resolved Questions

- [x] **Should the hook also detect hardcoded region strings (`us-east-1`, `us-west-2`) outside of bucket contexts?**
  - **Not yet** - Region detection is available via `--check-regions` but disabled by default. We are not in a position to enforce this yet.

- [x] **Should violations be warnings or hard failures by default?**
  - **Hard failures by default** - Use `--warn-only` flag to suppress failures and show warnings instead.

- [x] **Should we provide a `--fix` mode that suggests replacements (not auto-apply)?**
  - **Yes** - Provide `--suggest` flag that shows recommended replacements (does not auto-apply).

## Quick Start for Adopting Repos

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/tatari-tv/pre-commit-hooks
    rev: v1.x.x  # Use latest version with no-hardcoded-buckets
    hooks:
      - id: no-hardcoded-buckets
        # Optional: exclude test fixtures or legacy code during migration
        # exclude: ^tests/fixtures/|^legacy/
```

Then run:
```bash
pre-commit install
pre-commit run no-hardcoded-buckets --all-files  # Check existing codebase
```

## Success Metrics

After rollout, track:
- **Adoption rate**: Number of repos with hook enabled
- **Violations caught**: Count of violations flagged in CI (before merge)
- **Bypass rate**: Frequency of `# noqa: hardcoded-bucket` usage (should be low)
- **Future cleanup effort**: If another bucket migration happens, how many files need changes in repos with the hook vs without

## References

- [DAT-4082: Single Region Consolidation](https://tatari.atlassian.net/browse/DAT-4082)
- [pyspark-data-science-jobs PR #884](https://github.com/tatari-tv/pyspark-data-science-jobs/pull/884)
- [pyspark-calculation-jobs PR #610](https://github.com/tatari-tv/pyspark-calculation-jobs/pull/610)
- [python-tatari-data-utils](https://github.com/tatari-tv/python-tatari-data-utils) - Source of truth for bucket configuration
- [python-tatari-environments](https://github.com/tatari-tv/python-tatari-environments) - Environment detection
