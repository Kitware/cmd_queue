# Phase 8: Packaging, CI, and documentation

**Goal:** Make declared dependencies true, CI honest, and the Sphinx docs match
the post-refactor package layout.

**Prerequisites:** Phase 1 (deleted dead config). Mostly independent of 2-7.

## 8.1 Requirements fixes

- `requirements/airflow.txt:2-5` — version floors are **inverted**: py3.11
  requires `apache-airflow>=3.2.1` while py3.12/3.13 require only `>=3.1.3`.
  Almost certainly a typo — fix so newer pythons get the newer floor (verify
  against airflow's actual python-support matrix before choosing values).
- Same file: the py3.14 row is commented out, so
  `pip install cmd_queue[airflow]` on 3.14 silently installs no airflow, while
  the CI `full-strict/cp314` job still passes `INSTALL_EXTRAS=...airflow` —
  the extra resolves to nothing, airflow tests skip, job goes green as a
  de-facto minimal job. Either add a 3.14 row (if airflow supports it now) or
  make the cp314 full lanes explicitly non-airflow so nobody mistakes them for
  airflow coverage.
- `requirements/runtime.txt` — prune the dead py3.6-3.9 marker rows
  (numpy/pandas); the package requires >=3.10.
- `requirements/runtime.txt:21` — act on the existing
  `# TODO: lets make pandas an optional dependency`. pandas is heavy for a
  bash-DAG tool; its main use is the slurm monitor's squeue table, which
  Phase 5.1.1 rewrites without pandas — after that lands, demote pandas to
  the `optional` extra and guard imports. Same review for `pint`
  (`slurm.py:74-100` uses it only to parse "4GB"-style strings — a 10-line
  suffix parser removes the dependency and its doctest gating).
- `pyproject.toml` `package-data."*" = ["requirements/*.txt"]` is ineffective
  (requirements/ is outside any package; sdist gets them via MANIFEST.in).
  Remove the stanza or move requirements inside the package if runtime access
  is actually needed (check whether anything reads them at runtime first —
  xcookie-style `__requires__` loaders sometimes do).

## 8.2 CI improvements (`.gitlab-ci.yml` — xcookie-generated; prefer changing
the xcookie config and regenerating; hand-edit only if regeneration is not set
up, and say so in the commit)

- Lint job: drop `allow_failure: true` once Phase 1.4 lands; run
  `ruff check cmd_queue tests`.
- The four ~120-line test job templates differ only in 3 variable lines
  (`INSTALL_EXTRAS`, `USE_UV_LOCK`, `LOCK_REQUIREMENTS`); convert to one
  template + per-job `variables:` (~400 lines removed, drift risk eliminated).
- Keep (do not regress): wheel-built-then-tested-from-sandbox flow, xdoctest
  over the installed module, strict/loose lanes, sdist smoke lane, twine
  check, GPG fingerprint verification.

## 8.3 Sphinx docs

- **Delete the stale page** `docs/source/auto/cmd_queue.util.util_network_text.rst`
  (module no longer exists; also remove its entry from
  `docs/source/auto/cmd_queue.util.rst:13`).
- **Regenerate the autodoc tree** — it predates the backends refactor: there
  are no pages for `cmd_queue.backends` (serial/tmux/slurm/airflow — the real
  implementations), `monitor_manifest`, `slurmify`, `_graph`, `_registry`,
  `_rendering`, `_types`, or `util.util_bash`. Use sphinx-apidoc/xcookie's
  generator, then build docs and fix warnings.
- If Phase 7.5 deleted `util/texter.py`, remove its docs page in the same pass.
- Build check: `cd docs && make html` with `-W` (warnings as errors) if the
  warning count is manageable; otherwise record the count and ratchet down.

## 8.4 README and CHANGELOG

- README spot-checks passed in the audit (Quickstart API and CLI subcommands
  match the code) — after Phase 3.3.1/2.2.7, re-verify the
  `cmd_queue submit ... -- 'a && b'` example actually runs, since it is broken
  today and the fix must keep the documented form working.
- Keep CHANGELOG 0.3.2 current as phases land (started in Phase 1.6). Items
  worth explicit CHANGELOG entries because they change behavior: name
  validation (Phase 2), `onfail` semantics reconciliation (Phase 6.5), pandas/
  pint demotion to optional (8.1), any removed modules (`texter.py`).

## Verification

- `pip install -e .[all]` in a fresh 3.10 venv and in the newest supported
  python; `python -c "import cmd_queue; cmd_queue.Queue.create(backend='serial')"`.
- `python -m build` (or the CI equivalent) produces sdist+wheel; install the
  wheel in a clean venv and run `pytest --pyargs` / the xdoctest lane against
  the installed package.
- Docs build clean; the rendered API index lists the backends package.
