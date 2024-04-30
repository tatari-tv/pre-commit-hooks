# custom python hooks

## Linters:
### disallowed_identifiers
These hooks are designed to ward off unrecommended patterns in python code. The specific references flagged are determined in the calling repository's `pre-commit-config.yaml` file

In exceptional cases where the identifier is needed, you can ignore the check by writing `# tatari-noqa` on the line flagged by the pre-commit hook.

Identifiers are [here](https://github.com/tatari-tv/pre-commit-hooks/blob/8fa5c661f16e62a085c5625cc3719f3f12d96b59/python_hooks/disallowed_identifiers.py#L12-L15) and as of version 2.1.0 are attributes and functions.
