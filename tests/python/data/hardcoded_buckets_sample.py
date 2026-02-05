"""Sample file for testing no_hardcoded_buckets hook.

This file contains various patterns that should be detected or ignored.
"""
# Pattern 1: Hardcoded bucket names (SHOULD FLAG)
DATALAKE_BUCKET = "tatari-datalake-dev-us-east-1"
SCRATCH_BUCKET = "tatari-scratch-staging-us-west-2"
PROD_SCRATCH = "tatari-scratch-useast1"  # Legacy production format
TEMP_BUCKET = "tatari-datalake-temp-prod-us-east-1"
GX_BUCKET = "tatari-gx-prod"
XCOM_BUCKET = "tatari-xcom-dev-us-east-1"
LEGACY_BUCKET = "tatari-data-science"

# Pattern 2: Hardcoded regions (SHOULD FLAG)
REGION = "us-east-1"
LEGACY_REGION = "useast1"


# Pattern 3: Environment-conditional bucket logic (SHOULD FLAG)
def get_bucket_conditional():
    if is_production():
        return "tatari-scratch-useast1"
    return "tatari-scratch-dev-us-east-1"


def get_bucket_ternary():
    bucket = "tatari-datalake" if is_production() else "tatari-datalake-dev-us-east-1"
    return bucket


def get_bucket_with_staging():
    if is_staging():
        bucket = "tatari-scratch-staging-us-west-2"
    else:
        bucket = "tatari-scratch-prod-us-east-1"
    return bucket


# Should NOT flag - noqa comment
ALLOWED_BUCKET = "tatari-datalake-test-us-east-1"  # noqa: hardcoded-bucket

# Should NOT flag - in comments
# The bucket tatari-datalake-dev-us-east-1 is used for dev testing

# Should NOT flag - in docstrings (this is a standalone triple-quoted string, not a docstring)
_EXAMPLE_DOCSTRING = """
Example bucket names:
- tatari-datalake-dev-us-east-1
- tatari-scratch-staging-us-west-2
"""


def documented_function():
    """This function uses tatari-datalake-prod-us-east-1 for production."""
    pass


# Clean code - no flags expected
def clean_function():
    from tatari_data_utils import EnvironmentDefinition

    buckets = EnvironmentDefinition.get_default_buckets_for_env()
    return buckets.datalake


# Helper for conditional tests (not flagged, just used as env check)
def is_production():
    return False


def is_staging():
    return False
