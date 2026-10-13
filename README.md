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

### Plugin and skill checks

- `check-claude-plugin-names` fails on a plugin directory that does not match its `plugin.json` name, and on any symlink at or under `plugins/<name>/skills`, at any depth.
- `check-root-agent-docs` fails when the root `CLAUDE.md` or `AGENTS.md` is a symlink. A missing file is not checked.
- `skill-lint --body-excludes-frontmatter` counts `--max-body-lines` over the lines after the frontmatter instead of the whole file.

### Plugin version bumps

For a Claude plugin marketplace where each PR carries its own version bump:

- `check-version-bumps` fails when a changed plugin, or marketplace `metadata.version`, is below the version the change requires. It runs at `pre-push` and `manual`.
- `compute-version-bump [base_ref] [head_ref]` raises those versions in place in each `plugin.json` and `marketplace.json`. It defaults to `origin/main` and `HEAD`. Run it with `uvx --from git+https://github.com/tatari-tv/pre-commit-hooks@<rev> compute-version-bump`.
- Required versions: patch for any change, minor when a skill or agent is added, `0.1.0` for a new plugin. A larger manual version, such as a major bump, is kept. Reruns only touch what still needs a bump.
- Details: `metadata.version` takes the highest level any changed plugin needed. A `plugin.json` edit that changes only `version`, and marketplace entries pointing outside `plugins/`, are skipped. A moved file counts as a delete plus an add. Versions must be plain `X.Y.Z`; a pre-release such as `1.0.0-rc1` is an error. Rewritten manifests are normalised to two-space JSON.
- The check compares against the local `origin/main`, so a stale ref can flag plugins others changed. CI needs full history (`fetch-depth: 0`).
- `stages: [pre-push]` installs nothing alone. Set `default_install_hook_types: [pre-commit, pre-push]` in your config.
