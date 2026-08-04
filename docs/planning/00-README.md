# cmd_queue quality-improvement plan

Full-repo audit performed 2026-07-09 on branch `dev/0.3.2` at commit `0635f9c`.
Five parallel deep-audit passes (core, tmux, slurm, airflow/monitor/CLI,
utils/tests/packaging/hygiene) produced ~45 verified bugs and ~60 improvement
items; the highest-severity findings were reproduced by executing code, and the
plans note which. This directory turns those findings into an ordered,
executable plan.

## How to execute this plan

- **Work the phases in order.** Ordering is load-bearing: Phase 1 gives you a
  green baseline to verify against; Phase 2 fixes the *defect class* (shell
  quoting / name validation) that many Phase 3-5 bugs are instances of, so
  doing it first avoids fixing the same lines twice.
- **One commit per numbered task (or tight cluster), regression test in the
  same commit.** Every bug entry states file:line, the defect, a concrete
  failure scenario, a suggested fix, and (usually) a test recipe. Line numbers
  reference commit `0635f9c` — locate by symbol/content if drifted.
- **Verify each phase before moving on** using the phase's Verification
  section. The universal gate: `python3 -m pytest tests/ -q`,
  `./run_doctests.sh`, `ruff check cmd_queue tests`, `ty check cmd_queue tests`
  all green.
- **Suggested-fix humility:** the fixes were written from careful reading and
  reproduction, but if the surrounding code contradicts a suggestion, trust the
  code and the stated failure scenario over the suggested patch — the scenario
  is the spec.
- **Keep `CHANGELOG.md` 0.3.2 current** as you land user-visible changes
  (Phase 1.6 backfills; later phases append).
- Environment note: tmux-dependent and slurm-dependent tests are skip-gated on
  availability (`dev/slurm` has a test-cluster toolkit). airflow and textual
  are optional extras. The audit machine lacked `kwconf` initially — it IS
  declared in `requirements/runtime.txt`; `pip install -e .` first.

## Phases

| # | Doc | Theme | Severity of contents | Size |
|---|-----|-------|----------------------|------|
| 1 | [01-repo-hygiene-and-tooling.md](01-repo-hygiene-and-tooling.md) | Junk removal, real linting, CHANGELOG backfill | low, but unblocks everything | S |
| 2 | [02-shell-quoting-and-name-validation.md](02-shell-quoting-and-name-validation.md) | The top defect class: unescaped interpolation into generated bash; incl. command-injection paths | **critical** | M-L |
| 3 | [03-core-correctness.md](03-core-correctness.md) | base_queue/serial/CLI bugs: tee masks failures, duplicate-name corruption, broken CLI quickstart | high | M |
| 4 | [04-tmux-correctness.md](04-tmux-correctness.md) | Monitor kills running queues, uninitialized `workers`, wrong-queue kills, stale re-run state | high | M-L |
| 5 | [05-slurm-correctness.md](05-slurm-correctness.md) | squeue-parse crashes, malformed sbatch flags, DAG-integrity holes, slurmify broken OOTB | high | M-L |
| 6 | [06-airflow-monitor-and-cli-boilerplate.md](06-airflow-monitor-and-cli-boilerplate.md) | **airflow can wipe an external metadata DB**, textual kill-key crash, backend `run()` signature mismatch | critical/high | M |
| 7 | [07-test-suite-strengthening.md](07-test-suite-strengthening.md) | Tests that can't fail, uncollected files, untested modules, isolation | medium | M |
| 8 | [08-packaging-ci-and-docs.md](08-packaging-ci-and-docs.md) | Inverted airflow pins, honest CI, stale Sphinx autodoc tree | medium | S-M |
| 9 | [09-code-quality-and-dead-code.md](09-code-quality-and-dead-code.md) | Dead code, lying annotations, API consistency, perf | low | M |

## Top 10 most severe findings (cross-reference)

1. **airflow `run()` can drop a production Airflow DB** — ambient
   `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` + unconditional `db.resetdb()` (6.1)
2. **environ export command injection** — `export K="{v}"` unescaped (2.2.3)
3. **tmux monitor kills a running queue after promising it keeps running** —
   `q`-detach and Ctrl-C+decline paths both hit unconditional kill (4.1)
4. **CLI Quickstart is broken** — single-arg `shlex.quote` hack turns
   `'a && b'` into one quoted word, exit 127 (2.2.7 / 3.3.1)
5. **Failing job reported PASSED** — `log=True` without pipefail captures tee's
   exit code; dependents run on failed deps (3.1.1)
6. **slurm monitor dies on any multi-word squeue REASON** — cluster-wide
   pending jobs crash `pd.read_csv` mid-run (5.1.1)
7. **`kill_other_queues` kills other people's queues** — ambiguous lazy-parse
   of session names + headless auto-kill default (4.3)
8. **slurm duplicate names silently mis-wire the DAG** — SlurmQueue.submit
   bypasses the base duplicate check (5.3.2)
9. **textual monitor crashes on the kill key** — `Screen.bind` doesn't exist in
   textual >= 4 (6.2)
10. **tmux re-run reuses stale semaphores/state** — dependency order violated,
    or fresh sessions instantly killed (4.4)

## Meta: what NOT to change

The audit also confirmed strengths worth preserving: the newer test suites
(`test_bash_variants`, `test_slurm_variants`, `test_backend_execution`) are
well-designed; CI's build-wheel-then-test-from-sandbox flow, strict/loose lock
lanes, and xdoctest-over-installed-module are all good practice; README
examples match the current API (except the CLI quoting bug above). Don't churn
these while executing the phases.
