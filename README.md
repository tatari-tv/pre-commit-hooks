# Tatari Pre-Commit Hooks

**Disclaimer!** This is a public repo.  Take care about what information and data you put here, since
it will be viewable on the internet.

Place to store all of Tatari's custom [pre-commit hooks](https://pre-commit.com/#creating-new-hooks).

## Adding a new hook

Depending in which language your hook is written, you will need to commit your hook script in different locations:
* [Python](https://pre-commit.com/#python): [python_hooks/](./python_hooks)
  * Ensure you add any dependencies necessary for your hook by running `poetry add <dep>` followed by `poetry lock`
* [Bash](https://pre-commit.com/#system): root of repo

Then define your hook in [.pre-commit-hooks.yaml](./.pre-commit-hooks.yaml).  Full format of hook definition can be found
[here](https://pre-commit.com/#creating-new-hooks).

Python example:
```yaml
- id: python-example
  name: python-example
  description: Run a Python pre-commit hook
  entry: poetry run python -m python_hooks.python_script.py
  language: python
  pass_filenames: false
```

Bash example:
```yaml
- id: bash-example
  name: bash-example
  description: Run a Bash pre-commit hook
  entry: bash-script.sh
  language: system
  pass_filenames: false
```

## Using hooks from this repo

Adding hook definitions to your repo's `.pre-commit-config.yaml` will add specific hooks from this repo to evaluate your code.

Example:
```yaml
  - repo: git@github.com:tatari-tv/pre-commit-hooks.git
    rev: v0.1.0
    hooks:
      - id: poetry-pkg-dep-constraint-format
```
