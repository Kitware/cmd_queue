# Phase 1: Repo hygiene and tooling baseline

**Goal:** Remove accumulated junk, make the linter meaningful, and establish a clean
baseline so every later phase can verify itself against green checks.

**Prerequisites:** none. **Estimated scope:** small (~1 session).

> Line numbers throughout these planning docs reference commit `0635f9c`
> (branch `dev/0.3.2`). Locate code by symbol/content if lines have drifted.

## 1.1 Delete untracked junk at the repo root

These are confirmed leftovers, not project files. Delete (do NOT commit them):

- `cmd_queue-source-2026-05-15T193853-5-6c345ab182cf.tar.gz` — source snapshot tarball
- `emissions.csv` — codecarbon log from 2024
- `foo`, `foo.log`, `out`, `out.json`, `err.log` — scratch output (out.json is `{}`,
  likely from executing a `util_bash` doctest)
- `git-of-theseus/` — repo-stats artifacts from 2025
- `queue_root/`, `airflow_home/` — leftovers from an older airflow test that wrote
  into the repo root (the current `tests/test_airflow_queue.py` correctly uses
  `ub.Path.appdir`)
- `htmlcov/`, `.coverage`, `cmd_queue.egg-info/` — build/test artifacts (already
  gitignored; just clean them locally if convenient)

Decide-and-act items (default to deleting; note the decision in the commit message):

- `dev/poc/` — two proof-of-concept scripts from 2025. Move under `dev/` tracked
  content only if they still run; otherwise delete.
- `examples/slurm_example2.py` — WIP; note it calls
  `Queue.create(backend='serial', partition=..., account=...)` despite the slurm
  name. Either fix it to actually use the slurm backend and commit it, or delete it.

## 1.2 Extend .gitignore for artifacts this project generates

Add to `.gitignore`:

```
queue_root/
airflow_home/
emissions.csv
out
out.json
.mypy_cache/
.ruff_cache/
```

(`.mypy_cache/`/`.ruff_cache/` are currently invisible only because of one
machine's global excludes; other contributors will see them.)

## 1.3 Remove dead config files

- `appveyor.yml` — tests Python 2.7/3.5 against a package requiring `>=3.10` and
  `setuptools>=77`; any real run would fail at `pip install -e .`. Delete it.
- `.rules.yml` — GitLab rules template not `include:`d by `.gitlab-ci.yml`. Delete
  (or wire it in if xcookie expects it — check `git log .rules.yml` first).
- `.coveragerc` — duplicates `[tool.coverage]` in `pyproject.toml`. CI passes
  `--cov-config ../pyproject.toml` and `run_tests.py` passes `pyproject.toml`, so
  `.coveragerc` is unused. Delete it.
- `docs/requirements.txt` — diverges from `requirements/docs.txt` (unpinned,
  includes `six`, missing `myst_parser`/`sphinx-reredirects`); `.readthedocs.yml`
  uses `requirements/docs.txt`. Replace the file's contents with a single line
  `-r ../requirements/docs.txt`, or delete it if nothing references it.

## 1.4 Make lint real

Current state: the GitLab `lint` job is `allow_failure: true`; `run_linter.sh` runs
two flake8 invocations with no `set -e` (so only the second command's exit code
counts — E9/F82 errors in `cmd_queue/` pass as long as `tests/` is clean); ruff is
fully configured in `pyproject.toml` (`[tool.ruff]`) but nothing ever runs it.

1. Rewrite `run_linter.sh` to use ruff, with strict shell settings:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   ruff check cmd_queue tests
   ```
   (Keep a flake8 fallback only if some workflow depends on it; ruff's default
   rules cover the E9/F63/F7/F82 subset.)
2. Add `ruff` to `requirements/linting.txt`.
3. Fix the existing 11 `ruff check` findings (unused variables, unsorted imports —
   6 are `ruff check --fix`-able; review the unsafe ones manually).
4. In `.gitlab-ci.yml`, remove `allow_failure: true` from the lint job once the
   tree is clean. Note the CI file is xcookie-generated; if regenerating, make the
   change in the xcookie config instead of hand-editing, and record that in the
   commit message.

## 1.5 Fix misplaced module docstring

`cmd_queue/util/util_tmux.py:1-5` — the `"""Generic tmux helpers"""` docstring sits
*after* `from __future__ import annotations`, so it is a discarded expression and
`__doc__` is `None`. Move the docstring above the import.

## 1.6 Update CHANGELOG for 0.3.2

`CHANGELOG.md` has an empty `## Version 0.3.2 - Unreleased` section while the
branch already contains user-visible changes. Backfill from `git log e5d07ff..HEAD`:

- `--run=0` flag parsing fix in `CmdQueueConfigMixin`
- CLI migration to kwconf; `cli_boilerplate` (scriptconfig) deprecated
- slurm monitor survives purged/unknown jobs; more terminal states recognized
- `parse_scontrol_output` tolerates bare tokens
- `monitor='none'` blocks headlessly (consistent with tmux)
- popd guard syntax, defined HUP semantics, sbatch flag quoting fixes

Keep this section updated as later phases land fixes.

## Verification

- `git status` shows a clean tree (no untracked junk).
- `./run_linter.sh && echo OK` prints OK; introduce a deliberate unused import in
  `cmd_queue/__init__.py`, confirm the script now FAILS, then revert it.
- `python3 -m pytest tests/ -q` still passes (76+ passed / few env-dependent skips).
- `ty check cmd_queue tests` passes.
