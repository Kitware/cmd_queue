# Notes for Future Agents

## Repository Scope
These notes cover the entire repository (no nested AGENTS files exist). Keep this
file updated when workflows change.

## Project Overview
- `cmd_queue` builds and executes DAGs of shell commands with backends for
  serial execution, tmux workers, and slurm. An Airflow backend exists but is
  labeled experimental.
- CLI entrypoint: `cmd_queue/main.py` (also aliased via `python -m cmd_queue`).
  Bash-focused helpers live in `cmd_queue/cli_boilerplate.py`.
- Core queue abstractions are defined in `cmd_queue/base_queue.py` with backend
  implementations in `serial_queue.py`, `tmux_queue.py`, and `slurm_queue.py`.
- `cmd_queue/__init__.py` contains extensive usage examples and backend demos.

## Development Workflow
- **Environment setup:** `./run_developer_setup.sh` installs requirements and
  sets the package in editable mode.
- **Tests:** run `python run_tests.py` (pytest + coverage + xdoctest). You can
  scope to `tests/` or `cmd_queue/` directly if needed.
- **Linting:** `./run_linter.sh` executes flake8 against package and tests.
- **Doctests only:** `./run_doctests.sh` is available if you want to focus on
  embedded examples.
- **Docs:** build Sphinx docs with `make -C docs html`. Source lives in
  `docs/source/`; the landing page pulls from `docs/source/index.rst`.

## CLI Queues
- The CLI stores queue definitions as JSON under `~/.cache/cmd_queue/cli` by
  default. `--dpath` can override the location.
- Actions include `new`, `submit`, `show`, `run`, and `cleanup` (kills tmux
  sessions starting with `cmdq_`). See `CmdQueueCLI` in `cmd_queue/main.py` for
  supported options.

## Backends
- **Serial:** always available; writes a runnable bash script that executes jobs
  sequentially. Uses `cmd_queue/serial_queue.py`.
- **Tmux:** requires `tmux` installed; spins up worker sessions and streams jobs
  with optional GPU pinning. See `cmd_queue/tmux_queue.py`.
- **Slurm:** requires an active slurm deployment; generates `sbatch` commands
  with dependency wiring. See `cmd_queue/slurm_queue.py` and `cmd_queue/slurmify.py`.
- **Airflow:** generates a Python DAG skeleton in `cmd_queue/airflow_queue.py`,
  but the execution story is not fully documented/tested.

## Examples and Utilities
- Check `examples/` for sample queues.
- `run_tests.py` collects coverage reports to `htmlcov/` by default.
- Helper scripts in repository root (e.g., `run_developer_setup.sh`) are used in
  CI configs like `.gitlab-ci.yml` (not present locally) and `appveyor.yml`.

## TODO / Open Questions
- Airflow backend execution steps and required environment are unclear; add
  guidance when available.
- CLI queue persistence currently rewrites the entire JSON file per mutation;
  see TODO in `cmd_queue/main.py` for planned database abstraction.
