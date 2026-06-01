# Tatari Pre-Commit Hooks

**Disclaimer!** This is a public repo.  Take care about what information and data you put here, since
it will be viewable on the internet.

Place to store all of Tatari's custom [pre-commit hooks](https://pre-commit.com/#creating-new-hooks).

## Adding a new hook

### Python hooks

1. **Write the module** in [`python_hooks/`](./python_hooks).  Add a no-arg `main()` function that is the CLI entry point:

   ```python
   def main():
       """CLI entry point for the my-hook pre-commit hook."""
       parser = argparse.ArgumentParser(...)
       args = parser.parse_args()
       sys.exit(run(args))

   if __name__ == "__main__":
       main()
   ```

2. **Register the console script** in [`pyproject.toml`](./pyproject.toml) under `[tool.poetry.scripts]`:

   ```toml
   [tool.poetry.scripts]
   my-hook = "python_hooks.my_hook:main"
   ```

3. **Add any required dependencies** with `poetry add <dep>` followed by `poetry lock`.

4. **Define the hook** in [`.pre-commit-hooks.yaml`](./.pre-commit-hooks.yaml) using the console script name as `entry`:

   ```yaml
   - id: my-hook
     name: my-hook
     description: Run a Python pre-commit hook
     entry: my-hook
     language: python
     pass_filenames: false
   ```

   > **Why a console script?** Tools like [prek](https://github.com/domodwyer/prek) resolve `entry` as an installed binary rather than a shell command, so `python -m ...` does not work. Registering a console script in `pyproject.toml` ensures the hook runs correctly with both pre-commit and prek.

### Bash hooks

Place the script at the root of the repo and define the hook in [`.pre-commit-hooks.yaml`](./.pre-commit-hooks.yaml):

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
