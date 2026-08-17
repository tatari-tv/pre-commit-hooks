# Design Document: skill-lint Hook

**Author:** Brad Yinger
**Date:** 2026-08-17
**Status:** Draft
**Ticket:** [MINT-4819](https://tatari.atlassian.net/browse/MINT-4819)

## Summary

A pre-commit hook that lints Claude Code `SKILL.md` skill definitions.
It replaces two divergent validators: `scripts/skill_lint.py` in `tatari-tv/conductor` and the skill-frontmatter checks in `tatari-tv/tatari-skills` `bin/skillzy validate`.
Both repos consume this repo already, so both can pin one shared implementation.

## Problem

The two validators disagreed on every rule.
conductor capped descriptions at 500 chars combined, required five frontmatter keys, and enforced a body line budget and a `tests/spec.json` check.
tatari-skills capped descriptions at 1,024 chars, required only `description`, allowed 14 frontmatter keys, and had neither a body check nor a spec check.
Centralizing without reconciling would freeze the disagreement into a shared contract.

## Reconciled rule set

The principle: **defaults follow published Anthropic limits; every stricter rule is an explicitly owned house margin, passed as a hook arg by the repo that owns it.**
Nothing house-specific is hardcoded in the shared implementation.

| Rule | Default | Justification |
| --- | --- | --- |
| `--max-description-chars` | 1024 | Published Anthropic hard cap for a skill's `description`. Measured over `description` + `when_to_use` combined, a house decision: the platform concatenates both fields into the skill's one listing entry, so trigger text must not dodge the budget by moving between fields. In a repo that does not use `when_to_use`, this equals measuring `description` alone. conductor tightens to 500 as an owned house margin for per-session context cost. `0` disables. |
| `--max-body-lines` | 500 | Published Anthropic authoring best practice: keep `SKILL.md` under 500 lines. `0` disables (an owned house choice for a repo that is not ready to enforce it). |
| `--required-key` (repeatable) | `description` | The platform's only required frontmatter key; `name` falls back to the directory name. Passing the flag replaces the default set. conductor's extra required keys (`name`, `allowed-tools`, `classification`, `classification-reason`) are house margins passed as args. |
| `--allowed-key` (repeatable) | the 14 platform-documented keys | Closed allowlist to catch typos (`descripton:`) that silently disable the real key. The default is the platform's documented frontmatter surface: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`, `hooks`, `license`, `memory`, `metadata`, `compatibility`. House keys (conductor's `when_to_use`, `classification`, `classification-reason`) are added per repo. Required keys are always allowed. |
| `--key-values KEY=V1,V2` (repeatable) | none | Generic closed value set for a key when it is present. House rule mechanism: conductor uses `classification=capability,preference,mixed` without that taxonomy living in the shared repo. |
| `--require-spec` | off | House rule (conductor's eval-coverage requirement that every skill has `tests/spec.json`). Not a platform concept, so it is opt-in. |

Rules from the old validators that did not move here: skillzy's kebab-case name checks, angle-bracket description check, and all marketplace/plugin/cursor-rule validation stay in skillzy, which tatari-skills keeps for its marketplace concerns.

## Discovery

`--skills-root` is a repeatable glob whose matches are directories of skill directories.
The default is `skills` and `plugins/*/skills`, which covers conductor's bare layout and tatari-skills' plugin layout with no configuration.
Discovered directories are filtered through `git check-ignore`, so gitignored scratch skills are skipped.
A scan that finds zero skill directories fails: a broken root must never look like a clean tree.

## Baseline

Pre-existing violations are absorbed by a JSON file passed via `--baseline`, keyed by the skill directory's path relative to the repo root (for example `skills/conduct` or `plugins/general/skills/codex`).
Each entry records the violation's magnitude at baseline time, and every run re-checks it two ways: the violation must still be real (else the entry is stale and the run fails until it is removed), and it must not have grown (else the debt grew and the run fails).
The baseline can therefore only shrink without a deliberate, reviewed edit.

No-baseline behavior is defined explicitly:

- **No `--baseline` supplied**: the hook runs with an empty baseline. Nothing is absorbed and every violation fails. This is the right default for a repo with no debt, and it is a deliberate choice, not an accident of a missing file.
- **`--baseline PATH` where PATH does not exist**: hard error. A typo'd path must not silently mean zero tolerance.
- **Adopting with existing debt**: run once with `--baseline PATH --write-baseline` to capture every current violation with its magnitude, review the file, commit it, and land the hook green. This replaces conductor's hand-maintained baseline and gives tatari-skills a one-command adoption path for its ~46 missing specs if it ever opts into `--require-spec`.

## Consumer configuration

conductor (all house rules on, one hook per check via `--only`):

```yaml
- repo: https://github.com/tatari-tv/pre-commit-hooks
  rev: vX.Y.Z
  hooks:
    - id: skill-lint
      files: ^(skills/|scripts/skill_lint_baseline\.json)
      args:
        - --max-description-chars=500
        - --required-key=name
        - --required-key=description
        - --required-key=allowed-tools
        - --required-key=classification
        - --required-key=classification-reason
        - --allowed-key=when_to_use
        - --key-values=classification=capability,preference,mixed
        - --require-spec
        - --baseline=scripts/skill_lint_baseline.json
```

tatari-skills (platform defaults are already its rule set, but a default run is not green as of 2026-08-17: three skills exceed the 500-line body budget - `dbr-migrate` at 1096 lines, `dp-foundations` at 518, `tech-spec-review` at 506 - so adoption needs a baseline):

```yaml
- repo: https://github.com/tatari-tv/pre-commit-hooks
  rev: vX.Y.Z
  hooks:
    - id: skill-lint
      files: ^(plugins/|skill_lint_baseline\.json)
      args:
        - --baseline=skill_lint_baseline.json
```

Generate the baseline once at adoption with `skill-lint --baseline skill_lint_baseline.json --write-baseline`, review it, and commit it.
The ratchet then blocks new debt while the three oversized bodies get trimmed.
Passing `--max-body-lines=0` instead would disable the body check entirely; that is a deliberate opt-out, not the recommended path.

The hook's default `files` pattern only fires when a `SKILL.md` changes.
Consumers should widen it to their skills tree (as above) so deleting a spec or editing the baseline also retriggers the scan.

## Out of scope

Cutting the new tag and bumping `rev:` in both consumer repos is sequenced separately after this lands.
