# Design Document: No Non-Spark Buckets in Spark Projects Hook

**Author:** GitHub Copilot (via leslie)  
**Date:** 2026-02-05  
**Status:** Draft  
**Review Passes Completed:** 1/1

## Summary

A pre-commit hook to detect and prevent usage of non-Spark bucket utilities (`tatari_data_utils.buckets`) in PySpark and ML projects that depend on `python-tatari-pyspark` or `python-tatari-ml-utils`. This ensures proper region resolution for dev/staging environments after the us-west-2 → us-east-1 migration.

## Problem Statement

### Background

After the Databricks dev/staging migration from us-west-2 to us-east-1, Tatari maintains two versions of bucket resolution utilities:

1. **Non-Spark version** (`tatari_data_utils.buckets`):
   - Uses static region configuration
   - Dev/staging environments default to us-west-2 (pre-migration behavior)
   - Suitable for non-Spark Python services that may run in different regions

2. **Spark version** (`tatari_data_utils.buckets_spark`):
   - Added in `python-tatari-data-utils v1.0.0`
   - Forces `canonical_region='us-east-1'` for all environments after consolidation
   - Dev/staging environments correctly resolve to us-east-1 (post-migration)
   - Required for PySpark jobs and ML workloads running on Databricks
   - Wrapped by `tatari-pyspark v5.0.0` and `tatari-ml-utils v2.0.0`

**Region changes:**
| Environment | Pre-Migration | Post-Migration |
|-------------|---------------|----------------|
| Production  | us-east-1     | us-east-1 (unchanged) |
| Staging     | us-west-2     | **us-east-1** (migrated) |
| Dev         | us-west-2     | **us-east-1** (migrated) |

### Problem

During the migration analysis (February 2026), we discovered files across multiple repositories still using the non-Spark version in PySpark/ML projects:

**Confirmed Spark projects with violations:**
- `ml-impression-level-performance` (1 file) - Uses `tatari-pyspark ^5.0.0`
  
**Needs verification (may not be Spark projects):**
- `ml-affinity` (2 files) - Uses PySpark but no tatari-pyspark dependency
- `python-tatari-grey-shared` (1 file) - Shared utilities
- `python-tatari-reach-frequency-prediction` (2 files) - No Spark dependencies found

**Impact:**
- Jobs attempt to access us-west-2 buckets when running in us-east-1 environments
- Potential S3 access errors or permission issues
- Cross-region data transfer costs if reads/writes go to wrong region
- Data consistency issues if writes go to us-west-2 instead of us-east-1

**Root cause:**
The Data Platform team replaced most usages during the consolidation, new references may be introduced. Without automated enforcement, new violations can be introduced as developers use familiar but incorrect imports from `tatari-data-utils` instead of the Spark-aware wrappers.

### Goals

- **Detect** imports from `tatari_data_utils.buckets` (non-Spark version) in Spark projects
- **Detect** usage of `get_default_buckets_for_env` from `tatari_data_utils` in Spark projects
- **Allow** correct Spark-aware imports (`buckets_spark`)
- **Provide** clear error messages with fix suggestions
- **Support** opt-out via `noqa` comments for exceptional cases

### Non-Goals

- Detecting non-Spark imports in non-Spark projects - these are valid use cases
- Detecting dynamic imports using `importlib` - too complex to detect reliably
- Auto-fixing violations - too risky for imports that may have side effects
- Enforcing specific import patterns beyond preventing the anti-pattern
- Flagging test files that intentionally test both versions - use `noqa` for these

## Design

### Overview

Create a Python-based pre-commit hook (`no-non-spark-buckets-in-spark-projects`) that:
1. Detects if a project uses PySpark or ML utilities by checking `pyproject.toml`
2. Scans Python files for imports from the non-Spark bucket utilities
3. Reports violations with suggested fixes

The hook will be added to the existing `tatari-tv/pre-commit-hooks` repository.

### Architecture

```
pre-commit-hooks/
├── python_hooks/
│   └── no_non_spark_buckets_in_spark_projects.py    # Main hook implementation
├── tests/
│   └── test_no_non_spark_buckets_in_spark_projects.py # Test suite
├── .pre-commit-hooks.yaml                             # Hook definitions (update)
└── docs/
    └── design/
        └── 2026-02-05-no-non-spark-buckets-hook.md   # This document
```
Patterns

#### Pattern 1:
### Detection Logic

#### 1. Spark Project Detection

Walks up directory tree to find `pyproject.toml`, then parses it to check for dependencies:

```python
SPARK_DEPENDENCIES = {
    "python-tatari-pyspark",  # v5.0.0+ wraps DefaultBucketsSpark
    "python-tatari-ml-utils", # v2.0.0+ wraps DefaultBucketsSpark
    "tatari-pyspark",         # Alternative naming
    "tatari-ml-utils",        # Alternative naming
    "pyspark",                # Direct PySpark usage (may need Spark buckets)
}
```

If any dependency is found in `[tool.poetry.dependencies]`, the project is classified as a Spark project requiring the Spark-aware bucket utilities.

**Note:** Projects using `pyspark` directly without `tatari-pyspark` wrapper may or may not need Spark-aware buckets, depending on whether they run on Databricks in migrated environments.

#### Pattern 2: Non-Spark Import Detection

Flags these patterns:

```python
NON_SPARK_IMPORT_PATTERNS = [
    # Direct imports
    r"from\s+tatari_data_utils\.buckets\s+import\s+",
    
    # Convenience function import
    r"from\s+tatari_data_utils\s+import\s+.*get_default_buckets_for_env",
]
```

Excludes these patterns (allowed):

```python
SPARK_IMPORT_PATTERN = r"buckets_spark"
```

#### Pattern 3: Inline Suppression Support

Lines with `# noqa: non-spark-buckets` are skipped:

```python
from tatari_data_utils import get_default_buckets_for_env  # noqa: non-spark-buckets
```

### API Design

#### Command Line Interface

```bash
# Direct invocation
python -m python_hooks.no_non_spark_buckets_in_spark_projects [files...]

# Via pre-commit
pre-commit run no-non-spark-buckets-in-spark-projects --all-files
```

#### Exit Codes

- `0` - No violations found
- `1` - Violations detected (with details printed to stderr)

#### Output Format

```
ERROR: Non-Spark bucket imports detected in Spark projects

  data_sources/loaders/clickhouse/loader.py:12
    Non-Spark bucket import detected in PySpark/ML project. 
    Use 'tatari_data_utils.buckets_spark' instead.
    Import: from tatari_data_utils import get_default_buckets_for_env

Why this matters:
  - The non-Spark version (tatari_data_utils.buckets) uses static
    region configuration: dev/staging → us-west-2
  - After migration, dev/staging environments use us-east-1
  - The Spark version (buckets_spark) correctly resolves regions

How to fix:

  Option 1 - Change import (for Spark jobs):
    # Bad
    from tatari_data_utils.buckets import EnvironmentDefinition
    # Good
    from tatari_data_utils.buckets_spark import EnvironmentDefinitionSpark

  Option 2 - For tatari-pyspark users:
    # Bad
    from tatari_data_utils import get_default_buckets_for_env
  # Exclusions

Allow legitimate uses via:

1. **File-level exclusion** in `.pre-commit-config.yaml`:
   ```yaml
   - id: no-non-spark-buckets-in-spark-projects
     exclude: ^tests/integration/bucket_comparison\.py$
   ```

2. **Inline suppression** comment:
   ```python
   from tatari_data_utils.buckets import EnvironmentDefinition  # noqa: non-spark-buckets
   ```

3. **Non-Spark projects**: Hook automatically skips projects without Spark dependencies

### Implementation Plan

#### Phase 1: Core Implementation (Completed)
- ✅ Implement project type detection via `pyproject.toml` parsing
  ```yaml
  - id: no-non-spark-buckets-in-spark-projects
    name: no-non-spark-buckets-in-spark-projects
    description: Check for non-Spark bucket imports in Spark projects
    additional_dependencies: [tomli]
    entry: python -m python_hooks.no_non_spark_buckets_in_spark_projects
    language: python
    types: [python]
  ```

#### Phase 2: Testing (Completed)
- ✅ Add comprehensive test suite
- ✅ Test Spark project detection
- ✅ Test violation detection
- ✅ Test noqa suppression

#### Phase 3: Rollout (In Progress)
1. Merge hook to `pre-commit-hooks` repo
2. Tag release (e.g., `v2.5.0`)
3. Fix existing violations in affected repositories
4. Add to template `.pre-commit-config.yaml`

### Phase 2: Fix Existing Violations
1. Create PRs for affected Spark projects:
   - `ml-impression-level-performance` - Uses tatari-pyspark
   - `ml-affinity` - Uses PySpark (needs verification if it's a Spark project)

   Note: `python-tatari-grey-shared` and `python-tatari-reach-frequency-prediction` 
   may be non-Spark projects and should be verified before changes.

2. For each PR:
   - Update imports to use Spark-aware versions
   - Add pre-commit hook to `.pre-commit-config.yaml`
   - Run tests to verify functionality

### Phase 3: Enforce in New Projects
1. Add hook to template repositories
2. Update developer documentation
3. Add to CI/CD pipelines for Spark projects

## Trade-offs and Alternatives

### Considered Alternatives

#### 1. Runtime Detection
**Approach:** Detect incorrect bucket usage at runtime via environment checks.

**Pros:**
- Catches issues in all codepaths
- Works for dynamic imports

**Cons:**
- Fails in production environments
- Harder to debug
- No prevention, only detection

**Decision:** Pre-commit hook provides earlier feedback

#### 2. Centralized Import in Base Classes
**Approach:** Force all bucket access through base classes that enforce correct imports.

**Pros:**
- Compile-time enforcement
- Clearer architecture

**Cons:**
- Requires refactoring all existing code
- Doesn't prevent direct imports
- Breaking change

**Decision:** Too disruptive for existing codebases

#### 3. Linter Rule (Pylint/Flake8)
**Approach:** Implement as custom linter rule.

**Pros:**
- Integrates with existing linting infrastructure
- More familiar to developers

**Cons:**
- Requires dependency on project structure (pyproject.toml)
- Pre-commit hooks already established at Tatari
- Would still need pre-commit integration

**Decision:** Pre-commit hook is simpler and sufficient

### Alternative 4: Deprecation Warnings Only

**Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False positives in test files | Medium | Low | Provide inline `noqa` suppression |
| Performance impact on large repos | Low | Low | Regex-only detection is fast; cache project type |
| Developers bypass with `noqa` | Low | Low | Acceptable - conscious choice; monitor usage |
| Missing dynamic imports | Medium | Low | Document limitation; these are rare |
| Project type detection fails | Low | Medium | Handle TOML parse errors gracefully |

## Resolved Questions
After rollout, track:
- **Adoption rate**: Number of Spark repos with hook enabled
- **Violations caught**: Count of violations flagged in pre-commit (before merge)
- **Bypass rate**: Frequency of `# noqa: non-spark-buckets` usage (should be <5%)
- **Fix time**: Time to resolve all existing violations in affected repo
### Dependencies

- Python 3.9+ (matches tatari-data-utils requirement)
- `tomli` for parsing `pyproject.toml` (Python 3.9/3.10; stdlib `tomllib` in 3.11+)

### Performance

- TOML parsing: O(1) per directory (cached during run)
- Regex scanning: O(n) per file, negligible for typical file sizes
- Expected: <100ms for typical repository scan

### Security

No security implications - this is a read-only static analysis tool.

### Testing Strategy

1. **Unit tests** for project type detection with various `pyproject.toml` formats
2. **Unit tests** for import pattern detection with sample code
3. **Integration tests** with temporary files/directories
4. **Edge cases to test:**
   - Missing `pyproject.toml` (should skip checking)
   - Invalid TOML syntax (should handle gracefully)
   - Multiple Poetry tool sections
   - Comments in import lines
   - Multiline imports
   - Dynamic imports via `importlib` (acceptable to miss these)

### Risks and Mitigations

| Aspect | Trade-off | Mitigation |
|--------|-----------|------------|
| **False Positives** | May flag test files that intentionally use both versions | Support `noqa` comments |
| **Performance** | Parses `pyproject.toml` for every file | Cache project type detection per directory |
| **Maintenance** | Need to update if new Spark libraries added | Document dependency list clearly |
| **Developer Experience** | Additional check adds friction | Provide clear, actionable error messages |

## Success Metrics

### Key Performance Indicators
: Cross-Region Bucket Resolution](https://tatari.atlassian.net/wiki/spaces/DATA/pages/2326528229)
- [python-tatari-data-utils PR #25](https://github.com/tatari-tv/python-tatari-data-utils/pull/25) - Added `buckets_spark`
- [python-tatari-pyspark PR #141](https://github.com/tatari-tv/python-tatari-pyspark/pull/141) - v5.0.0 migration


## Appendix: Example Violations and Fixe
2. *Violation 1: Direct Import from buckets
   - Target: All existing violations fixed within 3 weeks
### Violation 1: ML Config Using Non-Spark Import

```python
# ❌ Bad - Uses non-Spark version in tatari-pyspark project
from tatari_data_utils import get_default_buckets_for_env

class AffinityConfig:
    @cached_property
    def scratch_bucket(self):
        return get_default_buckets_for_env().scratch
```

```python
# ✅ Good - Uses Spark version
from tatari_data_utils.buckets_spark import EnvironmentDefinitionSpark

class AffinityConfig:
    @cached_property
    def scratch_bucket(self):
        return EnvironmentDefinitionSpark.get_default_buckets_for_env().scratch
```

### Violation 2: Using tatari-pyspark Wrapper

```python
# ❌ Bad - Direct import from tatari_data_utils
from tatari_data_utils.buckets import EnvironmentDefinition

class JobConfig:
    def __init__(self):
        self.datalake = EnvironmentDefinition.get_default_buckets_for_env().datalake
```

```python
# ✅ Good - Use tatari-pyspark wrapper  
from tatari_pyspark.utils.buckets import DefaultBuckets

class JobConfig:
    def __init__(self):
        self.datalake = DefaultBuckets.get_from_environment().datalake
```

### Violation 3: Legitimate noqa Usage

```python
# Test file that compares both versions
from tatari_data_utils.buckets import EnvironmentDefinition  # noqa: non-spark-buckets
from tatari_data_utils.buckets_spark import EnvironmentDefinitionSpark

def test_bucket_parity():
    """Verify both versions return same production buckets."""
    non_spark = EnvironmentDefinition.get_default_buckets_for_env(env=Environments.PROD)
    spark = EnvironmentDefinitionSpark.get_default_buckets_for_env(env=Environments.PROD)
    assert non_spark.datalake == spark.datalake
```

### Example 1: ML Impression-Level Performance

**Before (Incorrect):**
```python
# impression_level_performance/affinity/config.py
from tatari_data_utils import get_default_buckets_for_env
from tatari_pyspark.utils.catalog import get_full_table_path

class AffinityConfig:
    @cached_property
    def scratch_path(self):
        bucket = get_default_buckets_for_env().scratch
        return f"s3a://{bucket}/affinity/"
```

**After (Correct):**
```python
# impression_level_performance/affinity/config.py
from tatari_pyspark.utils.buckets import DefaultBuckets
from tatari_pyspark.utils.catalog import get_full_table_path

class AffinityConfig:
    @cached_property
    def scratch_path(self):
        bucket = DefaultBuckets.get_from_environment().scratch
        return f"s3a://{bucket}/affinity/"
```

### Example 2: Using EnvironmentDefinitionSpark Directly

**Before (Incorrect):**
```python
from tatari_data_utils.buckets import EnvironmentDefinition

class SparkJobConfig:
    def __init__(self):
        self.datalake = EnvironmentDefinition.get_default_buckets_for_env().datalake
```

**After (Correct):**
```python
from tatari_data_utils.buckets_spark import EnvironmentDefinitionSpark

class SparkJobConfig:
    def __init__(self):
        self.datalake = EnvironmentDefinitionSpark.get_default_buckets_for_env().datalake
```

class Hyperparameters:
    def __init__(self, job, version):
        self.bucket = DefaultBuckets.get_from_environment().datalake
```
