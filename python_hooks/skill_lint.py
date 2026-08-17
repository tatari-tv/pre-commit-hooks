"""Lint Claude Code SKILL.md skill definitions.

Shared implementation of the skill-lint hook, reconciling the rule sets that
previously lived in tatari-tv/conductor (scripts/skill_lint.py) and
tatari-tv/tatari-skills (bin/skillzy validate). See docs/design/2026-08-17-skill-lint-hook.md
for the reconciliation rationale. The defaults follow published Anthropic limits;
every stricter house rule is opt-in through a hook arg, never a module constant:

- --max-description-chars (default 1024): Anthropic's published hard cap for a skill's
  `description`. Measured over description + when_to_use combined, because the platform
  concatenates both fields into the skill's one listing entry paid on every session;
  in a repo that does not use when_to_use this equals measuring description alone.
- --max-body-lines (default 500): Anthropic's published authoring best practice
  ("keep SKILL.md under 500 lines"). 0 disables the check.
- --required-key (default: description): the platform's only required frontmatter key
  (`name` falls back to the directory name). Repeat the flag to require more keys;
  passing it replaces the default set.
- --allowed-key: extends the closed frontmatter-key allowlist, which defaults to the 14
  keys documented by the platform. The allowlist exists to catch typos (`descripton:`)
  that would otherwise silently disable the real key. Required keys are always allowed.
- --key-values KEY=V1,V2: closed value set for a key when it is present (house taxonomies
  such as conductor's classification). No defaults.
- --require-spec: require tests/spec.json in every skill directory (house rule for eval
  coverage). Off by default.

Discovery: --skills-root is a repeatable glob, default `skills` and `plugins/*/skills`,
covering both consumer layouts. Skill directories that git ignores are skipped.
A scan that finds zero skills fails: a broken root must never look like a clean tree.

Baseline: pre-existing violations can be absorbed by a JSON file passed via --baseline.
Each entry records the violation's magnitude at baseline time and every run re-checks it
two ways: the violation must still be real (else the entry is stale - remove it), and it
must not have grown (else the debt grew - fix it or deliberately update the magnitude).
No --baseline means an empty baseline: nothing is absorbed and every violation fails,
which is the right default for a repo with no debt. To adopt the hook in a repo with
existing debt, run once with --baseline PATH --write-baseline to capture it. A --baseline
path that does not exist is an error, so a typo cannot silently mean zero tolerance.

Each check can run as its own hook via --only, so a failing commit names the specific
rule; running with no flag runs every check.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from glob import glob
from typing import Any
from typing import TypedDict

DEFAULT_SKILLS_ROOTS = ('skills', 'plugins/*/skills')
DEFAULT_MAX_DESCRIPTION_CHARS = 1024
DEFAULT_MAX_BODY_LINES = 500
DEFAULT_REQUIRED_KEYS = ('description',)
# The frontmatter surface documented by the platform for plugin skills.
PLATFORM_FRONTMATTER_KEYS = frozenset(
    (
        'name',
        'description',
        'argument-hint',
        'disable-model-invocation',
        'user-invocable',
        'allowed-tools',
        'model',
        'context',
        'agent',
        'hooks',
        'license',
        'memory',
        'metadata',
        'compatibility',
    )
)

CHECKS = (
    'missing_frontmatter',
    'unexpected_frontmatter',
    'oversized_body',
    'oversized_description',
    'invalid_value',
    'missing_spec',
)
# Checks whose magnitude is a list of key names; the ratchet compares them as sets.
SET_MAGNITUDE_CHECKS = frozenset(('missing_frontmatter', 'unexpected_frontmatter', 'invalid_value'))

Magnitude = int | list[str] | None
Baseline = dict[str, dict[str, dict[str, Any]]]


class Violation(TypedDict):
    detail: str
    magnitude: Magnitude


@dataclass(frozen=True)
class Rules:
    max_body_lines: int = DEFAULT_MAX_BODY_LINES
    max_description_chars: int = DEFAULT_MAX_DESCRIPTION_CHARS
    required_keys: tuple[str, ...] = DEFAULT_REQUIRED_KEYS
    allowed_keys: frozenset[str] = PLATFORM_FRONTMATTER_KEYS
    key_values: tuple[tuple[str, frozenset[str]], ...] = ()
    require_spec: bool = False

    def all_allowed_keys(self) -> frozenset[str]:
        return self.allowed_keys | frozenset(self.required_keys)


def split_frontmatter(content: str) -> str | None:
    """Return the raw YAML frontmatter text, or None if the file has none."""
    m = re.match(r'^---\n(.*?\n)---\n', content, re.DOTALL)
    return m.group(1) if m else None


def parse_frontmatter_keys(fm_text: str) -> dict[str, str]:
    """Minimal frontmatter reader: {key: value} for top-level scalar and block-scalar keys.

    Handles plain scalars (quoted or not) and '|'/'>' block scalars - the shapes SKILL.md
    files actually use. Not a general YAML parser; stdlib only so the hook needs no deps.
    """
    lines = fm_text.split('\n')
    keys: dict[str, str] = {}
    key_re = re.compile(r'^([A-Za-z0-9_-]+):\s*(.*)$')
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = key_re.match(line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest in ('|', '>', '|-', '>-', '|+', '>+'):
            style = rest[0]
            i += 1
            block_lines = []
            base_indent = None
            while i < n:
                block_line = lines[i]
                if block_line.strip() == '':
                    block_lines.append('')
                    i += 1
                    continue
                indent = len(block_line) - len(block_line.lstrip(' '))
                if base_indent is None:
                    base_indent = indent
                if indent < base_indent:
                    break
                block_lines.append(block_line[base_indent:])
                i += 1
            if style == '>':
                text, para = '', ''
                for bl in block_lines:
                    if bl == '':
                        text += para.strip() + '\n'
                        para = ''
                    else:
                        para += bl + ' '
                text += para.strip()
                keys[key] = text.strip()
            else:
                keys[key] = '\n'.join(block_lines).strip()
        else:
            val = rest
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            keys[key] = val
            i += 1
    return keys


def discover_skill_dirs(roots: Sequence[str]) -> list[str]:
    """Return skill directories (relative paths) under every root glob, sorted and deduped."""
    dirs = []
    for pattern in roots:
        for root in sorted(glob(pattern)):
            if not os.path.isdir(root):
                continue
            for name in sorted(os.listdir(root)):
                path = os.path.join(root, name)
                if os.path.isdir(path) and not name.startswith('.'):
                    dirs.append(path)
    return sorted(dict.fromkeys(dirs))


def filter_gitignored(skill_dirs: list[str]) -> list[str]:
    """Drop directories that git ignores. Outside a repo (or without git), keep everything."""
    if not skill_dirs:
        return skill_dirs
    try:
        # Trailing slashes so directory-only .gitignore patterns (`foo/`) match.
        result = subprocess.run(
            ['git', 'check-ignore', '--stdin'],
            input='\n'.join(d.rstrip('/') + '/' for d in skill_dirs),
            text=True,
            capture_output=True,
        )
    except OSError:
        print('skill-lint: git not found; skipping .gitignore filtering', file=sys.stderr)
        return skill_dirs
    if result.returncode not in (0, 1):  # 0: some ignored, 1: none ignored, else: not a repo / error
        return skill_dirs
    ignored = {line.rstrip('/') for line in result.stdout.splitlines()}
    return [d for d in skill_dirs if d.rstrip('/') not in ignored]


def scan_skill_dir(skill_dir: str, rules: Rules) -> tuple[dict[str, Violation], int]:
    """Return (violations, listing_length) for one skill directory.

    listing_length is len(description) + len(when_to_use) - the two fields the platform
    concatenates into the skill's one listing entry.

    violations maps violation type to detail plus a magnitude the baseline ratchet compares
    run-over-run: an int for the size checks, a list of key names for the key checks, and
    None for missing_spec (a presence check has no size).
    """
    skill_md = os.path.join(skill_dir, 'SKILL.md')
    violations: dict[str, Violation] = {}

    if rules.require_spec and not os.path.isfile(os.path.join(skill_dir, 'tests', 'spec.json')):
        violations['missing_spec'] = {'detail': 'no tests/spec.json', 'magnitude': None}

    if not os.path.isfile(skill_md):
        violations['missing_frontmatter'] = {
            'detail': 'no SKILL.md found',
            'magnitude': sorted(rules.required_keys),
        }
        return violations, 0

    with open(skill_md) as f:
        content = f.read()

    line_count = len(content.splitlines())
    if rules.max_body_lines and line_count > rules.max_body_lines:
        violations['oversized_body'] = {
            'detail': f'{line_count} lines (budget {rules.max_body_lines})',
            'magnitude': line_count,
        }

    fm_text = split_frontmatter(content)
    keys = parse_frontmatter_keys(fm_text) if fm_text is not None else {}

    # Present-but-empty counts as missing: `description:` with nothing after it would
    # otherwise satisfy the presence check while saying nothing.
    missing_keys = sorted(k for k in rules.required_keys if not keys.get(k, '').strip())
    if missing_keys:
        violations['missing_frontmatter'] = {
            'detail': f'missing key(s): {", ".join(missing_keys)}',
            'magnitude': missing_keys,
        }

    allowed = rules.all_allowed_keys()
    unexpected_keys = sorted(k for k in keys if k not in allowed)
    if unexpected_keys:
        violations['unexpected_frontmatter'] = {
            'detail': f'unexpected key(s): {", ".join(unexpected_keys)} (allowed: {", ".join(sorted(allowed))})',
            'magnitude': unexpected_keys,
        }

    bad_values = {}
    for key, allowed_values in rules.key_values:
        value = keys.get(key, '').strip()
        if value and value not in allowed_values:
            bad_values[key] = f'{key}: {value!r} (allowed: {", ".join(sorted(allowed_values))})'
    if bad_values:
        violations['invalid_value'] = {
            'detail': '; '.join(bad_values[k] for k in sorted(bad_values)),
            'magnitude': sorted(bad_values),
        }

    desc_len = len(keys.get('description', ''))
    wtu_len = len(keys.get('when_to_use', ''))
    listing_len = desc_len + wtu_len
    if rules.max_description_chars and listing_len > rules.max_description_chars:
        parts = [f'description {desc_len}']
        if wtu_len:
            parts.append(f'when_to_use {wtu_len}')
        violations['oversized_description'] = {
            'detail': f'{listing_len} chars combined ({" + ".join(parts)}, budget {rules.max_description_chars})',
            'magnitude': listing_len,
        }

    return violations, listing_len


def magnitude_grew(vtype: str, baseline_magnitude: Magnitude, current_magnitude: Magnitude) -> bool:
    """True if a baselined violation is worse now than what the baseline recorded."""
    if vtype in SET_MAGNITUDE_CHECKS:
        baseline_keys = baseline_magnitude if isinstance(baseline_magnitude, list) else []
        current_keys = current_magnitude if isinstance(current_magnitude, list) else []
        return not set(current_keys) <= set(baseline_keys)
    if vtype == 'missing_spec':
        return False  # presence check only - no size to grow
    if not isinstance(baseline_magnitude, int) or not isinstance(current_magnitude, int):
        return True  # malformed baseline entry - fail closed
    return current_magnitude > baseline_magnitude


def lint(
    skill_dirs: Sequence[str],
    rules: Rules,
    baseline: Baseline,
    baseline_name: str,
    only: str | None = None,
) -> tuple[list[str], int]:
    """Scan skill_dirs against baseline, optionally restricted to one check.

    Returns (failures, total_listing_chars). only, when set, restricts findings and
    baseline reconciliation to that one violation type (one hook per check).
    """
    failures = []
    total_listing_chars = 0
    seen = set()

    for skill_dir in skill_dirs:
        key = skill_dir.replace(os.sep, '/')
        seen.add(key)
        violations, listing_len = scan_skill_dir(skill_dir, rules)
        total_listing_chars += listing_len
        allowed = baseline.get(key, {})

        for vtype, info in violations.items():
            if only is not None and vtype != only:
                continue
            entry = allowed.get(vtype)
            if entry is None:
                failures.append(f'{key}: {vtype} - {info["detail"]}')
                continue
            if magnitude_grew(vtype, entry.get('magnitude'), info['magnitude']):
                failures.append(
                    f'{key}: {vtype} grew past its baselined magnitude '
                    f'({entry.get("magnitude")!r} -> {info["magnitude"]!r}) - {info["detail"]}. '
                    f'Fix it, or if the growth is deliberate, update {baseline_name}.'
                )

        for vtype in allowed:
            if only is not None and vtype != only:
                continue
            if vtype not in violations:
                failures.append(f'{key}: baseline entry "{vtype}" is stale (no longer violated) - remove it from {baseline_name}')

    for key in baseline:
        if key in seen:
            continue
        if only is not None and only not in baseline[key]:
            continue
        failures.append(f'{key}: baselined skill directory no longer exists - remove its entry from {baseline_name}')

    return failures, total_listing_chars


def load_baseline(path: str) -> Baseline:
    with open(path) as f:
        baseline: Baseline = json.load(f)
    return baseline


def write_baseline(skill_dirs: Sequence[str], rules: Rules, path: str) -> int:
    """Capture every current violation into a fresh baseline file at path."""
    baseline: Baseline = {}
    for skill_dir in skill_dirs:
        violations, _ = scan_skill_dir(skill_dir, rules)
        if violations:
            baseline[skill_dir.replace(os.sep, '/')] = {
                vtype: {'magnitude': info['magnitude'], 'reason': 'pre-existing when the baseline was created'}
                for vtype, info in violations.items()
            }
    with open(path, 'w') as f:
        json.dump(baseline, f, indent=2, sort_keys=True)
        f.write('\n')
    print(f'skill-lint: wrote baseline for {len(baseline)} skill(s) to {path}')
    return 0


def parse_key_values(specs: Sequence[str], parser: argparse.ArgumentParser) -> tuple[tuple[str, frozenset[str]], ...]:
    parsed = []
    for spec in specs:
        key, sep, values = spec.partition('=')
        allowed_values = frozenset(v.strip() for v in values.split(',') if v.strip())
        if not sep or not key.strip() or not allowed_values:
            parser.error(f'--key-values expects KEY=VALUE1,VALUE2,... (got {spec!r})')
        parsed.append((key.strip(), allowed_values))
    return tuple(parsed)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the skill-lint pre-commit hook."""
    parser = argparse.ArgumentParser(description='Lint Claude Code SKILL.md skill definitions')
    parser.add_argument(
        '--skills-root',
        action='append',
        dest='skills_roots',
        metavar='GLOB',
        help=f'glob for directories whose subdirectories are skills; repeatable (default: {", ".join(DEFAULT_SKILLS_ROOTS)})',
    )
    parser.add_argument('--baseline', metavar='PATH', help='JSON file of absorbed pre-existing violations; omit to absorb nothing')
    parser.add_argument('--write-baseline', action='store_true', help='capture current violations into --baseline PATH and exit')
    parser.add_argument(
        '--max-body-lines',
        type=int,
        default=DEFAULT_MAX_BODY_LINES,
        metavar='N',
        help=f'max SKILL.md lines, 0 disables (default {DEFAULT_MAX_BODY_LINES}: Anthropic authoring best practice)',
    )
    parser.add_argument(
        '--max-description-chars',
        type=int,
        default=DEFAULT_MAX_DESCRIPTION_CHARS,
        metavar='N',
        help='max combined description + when_to_use chars, 0 disables '
        f'(default {DEFAULT_MAX_DESCRIPTION_CHARS}: Anthropic hard cap for description)',
    )
    parser.add_argument(
        '--required-key',
        action='append',
        dest='required_keys',
        metavar='KEY',
        help=f'frontmatter key that must be present and non-empty; repeatable, replaces the default ({", ".join(DEFAULT_REQUIRED_KEYS)})',
    )
    parser.add_argument(
        '--allowed-key',
        action='append',
        dest='allowed_keys',
        default=[],
        metavar='KEY',
        help='extra frontmatter key to allow beyond the platform-documented set; repeatable',
    )
    parser.add_argument(
        '--key-values',
        action='append',
        dest='key_values',
        default=[],
        metavar='KEY=V1,V2',
        help='closed value set for a frontmatter key when present; repeatable',
    )
    parser.add_argument('--require-spec', action='store_true', help='require tests/spec.json in every skill directory')
    parser.add_argument('--only', choices=CHECKS, default=None, help='run a single check (one hook per check); default runs all')
    args = parser.parse_args(argv)

    if args.write_baseline and not args.baseline:
        parser.error('--write-baseline requires --baseline PATH')
    if args.write_baseline and args.only:
        parser.error('--write-baseline cannot be combined with --only (a partial baseline would silently absorb the other checks)')

    rules = Rules(
        max_body_lines=args.max_body_lines,
        max_description_chars=args.max_description_chars,
        required_keys=tuple(args.required_keys) if args.required_keys else DEFAULT_REQUIRED_KEYS,
        allowed_keys=PLATFORM_FRONTMATTER_KEYS | frozenset(args.allowed_keys),
        key_values=parse_key_values(args.key_values, parser),
        require_spec=args.require_spec,
    )

    baseline: Baseline = {}
    if args.baseline and not args.write_baseline:
        if not os.path.isfile(args.baseline):
            # Fail closed: a typo'd baseline path must be an error, not silent zero tolerance.
            print(f'skill-lint: baseline file not found: {args.baseline} (create it with --write-baseline, or fix the path)')
            return 1
        baseline = load_baseline(args.baseline)

    roots = args.skills_roots if args.skills_roots else list(DEFAULT_SKILLS_ROOTS)
    skill_dirs = filter_gitignored(discover_skill_dirs(roots))
    if not skill_dirs:
        # Fail closed: a broken or empty scan must never look like a clean tree.
        print(f'skill-lint: no skill directories found under {", ".join(roots)} - refusing to treat an empty scan as a pass')
        return 1

    if args.write_baseline:
        return write_baseline(skill_dirs, rules, args.baseline)

    failures, total_listing_chars = lint(skill_dirs, rules, baseline, args.baseline or 'the --baseline file', only=args.only)

    if args.only in (None, 'oversized_description'):
        print(
            f'skill-lint: {len(skill_dirs)} skills, {total_listing_chars} listing chars '
            f'(description + when_to_use, ~{total_listing_chars // 4} tokens) paid every session regardless of which skill fires.'
        )

    if failures:
        print(f'\n{len(failures)} skill-lint violation(s):\n')
        for failure in failures:
            print(f'  FAIL {failure}')
        return 1

    print('skill-lint: all skills within budget (or covered by the baseline).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
