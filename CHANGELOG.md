# Changelog

We are currently working on porting this changelog to the specifications in
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Version 0.3.3 - Unreleased


## Version 0.3.2 - Released 2026-08-04

### Added:
* `CmdQueueConfigMixin`, a :mod:`kwconf`-based equivalent of `CMDQueueConfig`
  carrying the same fields and the same `create_queue` / `run_queue` API. Use
  it for new code.
* A headless mode for the slurm backend's `monitor()`: it polls until every job
  is terminal without rendering a live table, and still prints per-job
  pass/fail/skip lines.
* Nine ordered planning documents under `docs/planning/`, from a full-repo
  audit: hygiene, shell-quoting hardening, core/tmux/slurm/airflow
  correctness, the test suite, packaging/CI/docs, and dead-code cleanup.

### Changed:
* The internal CLIs (`main.py`, `slurmify.py`) are now kwconf-based. kwconf does
  not auto-split comma strings, so `--depends` and `--gpus` use `parser='csv'`
  to preserve the documented comma-separated behavior.

  **For downstream CLIs:** kwconf's `cli()` takes `argv=` rather than
  `cmdline=`, and its sys.argv toggle is a `bool` rather than scriptconfig's
  `int` -- so `main(argv=1)` becomes `main(argv=True)`.
* `Job.depends` is typed `List[Job]` rather than `Optional[Iterable[Job]]`,
  which is what constructors actually receive: string references are resolved
  at the queue level before construction. A new `base_queue.JobDepends` alias
  and `coerce_job_depends()` helper normalize it, and `Queue._register_named_job()`
  narrows optional job names. This replaced blanket `type: ignore` comments with
  structural fixes.
* `TMUXMultiQueue.kill_other_queues` no longer requires the `parse` package,
  which was imported but declared in no requirements file -- so the tmux
  backend raised `ModuleNotFoundError` on any install that did not happen to
  have it.

### Deprecated:
* `CMDQueueConfig`, the scriptconfig-based boilerplate base. Subclassing it now
  emits a `DeprecationWarning` naming `CmdQueueConfigMixin` as the replacement.
  (The 0.3.2 migration documented this warning but never raised one.) The warning fires on
  subclassing rather than on import, because importing `cli_boilerplate` is
  also how a caller reaches the kwconf class. `scriptconfig` remains a
  dependency for as long as this class exists.

### Fixed:
* **serial/tmux: every job after a `cwd` job ran in the wrong directory.** The
  cwd restore was rendered as `[["$CHDIR_OK" == "1"]]` -- no space after `[[`,
  which bash resolves as an unknown command -- so `popd` never ran.
* **serial/tmux: a teardown could be skipped on `tmux kill-session`.** The
  teardown subshell now traps `HUP` explicitly rather than relying on bash's
  undocumented run-the-EXIT-trap-on-unhandled-group-HUP behavior, which the
  release-on-kill path was riding on.
* **slurm: boolean `sbatch` flags rendered with a stray trailing quote**
  (`--hold"`), malforming the sbatch line for any boolean in
  `SLURM_SBATCH_FLAGS`.
* **slurm: the monitor crashed on purged or unknown jobs.** `scontrol show job`
  returns no `JobState` once a job is past `MinJobAge`, so `info['JobState']`
  raised `KeyError` when re-attaching after a run. The final state is now
  recovered from accounting via `sacct`, all fields are read with `.get()`, and
  `TIMEOUT` / `OUT_OF_MEMORY` / `NODE_FAIL` and friends are treated as
  terminal-failed rather than `'unknown'`, which used to hang the completion
  check.
* **slurm: `parse_scontrol_output` raised on some slurm versions.** It assumed
  every whitespace token was `key=value`; a space-containing value for a
  non-special key yielded a bare token and "not enough values to unpack". Bare
  tokens are now skipped.
* **slurm: `run(block=True, monitor='none')` did not block.** It printed "Queue
  running detached" and returned immediately, so a scripted run could act on
  results before any job finished -- contradicting both the tmux backend and
  this backend's own docstring. `block=False` is now the genuinely
  non-blocking case, and carries the reattach hint.
* **`--run=0` executed the queue.** `run` was declared
  `run: bool = kw.Flag(False, ...)`, and the `: bool` annotation made kwconf
  coerce with `bool()`, so `'0'` became `True`. Dropping the annotation
  restores `--run=0` falsy, `--run=1` truthy, bare `--run` true.
* `monitor='none'` was smartcast to `None` by scriptconfig in `CMDQueueConfig`.
* **`kill_other_queues` could offer to kill an unrelated queue's sessions.** It
  matched session ids with a non-greedy `{name}_{rootid}` template, so a queue
  named `my_queue` parsed as `my`: it missed its own sessions, and a queue
  actually named `my` matched `my_queue`'s. Session ownership is now decided by
  the full `<prefix><name>_` prefix.


## Version 0.3.1 - Released 2026-06-25

### Added:
* First-class job `setup` / `teardown` lifecycle on `BashJob` (serial/tmux) and `SlurmJob`. `setup` is a gating precondition (shares the preamble's `PREAMBLE_OK` gating; a failing setup skips the command and marks the job failed). `teardown` always runs after the command — on success, failure, and SIGINT/SIGTERM — provided setup succeeded. It is rendered as a per-job, signal-safe cleanup (a scoped subshell trap for serial/tmux so it cannot leak across the many jobs in one script; an in-`--wrap` trap for slurm). The main command's exit code stays authoritative (a teardown failure does not flip the job result). A hard SIGKILL cannot be trapped — an out-of-band reclaim (e.g. a lease TTL) is the only backstop for that. This is the job-level try/finally for bracketing an external resource (e.g. acquire/release a GPU lease).

* Backend execution tests (`tests/test_backend_execution.py`) that actually run a queue — simple DAGs and the `setup`/`teardown` lifecycle — on the serial backend, and on tmux/slurm when those backends report themselves available (skipped otherwise).

### Fixed:
* A list-valued `preamble` passed to `SlurmJob` (e.g. `submit(..., preamble=['a', 'b'])`) no longer crashes script construction; list steps are now flattened into the `&&` chain instead of being appended as a single element.
* Corrected the inverted ``is_available()`` guard in two ``SlurmQueue`` ``--run`` doctests (they read `if not self.is_available(): self.run()`, which would only submit when slurm was *un*available).


## Version 0.3.0 - Released 2026-05-21

### Added:
* generalized the monitor so it can be launched in an independent process and reports errors better.
* New `monitor='hybrid'` mode (now the default for tmux and slurm `run()`): renders the live status table inline in the current shell and *also* spawns a detached `cmd_queue monitor` tmux session. Press `[a]` from the inline UI to attach (or `switch-client` when already inside tmux), `[q]` to stop watching while the queue keeps running. The side session is killed when the inline monitor exits.

### Changed
* `monitor` kwarg accepted values are now `'hybrid' | 'inline' | 'tmux' | 'none'`. `'inline'` reverts to its original pure-current-shell meaning; the `'hybrid'` mode covers the inline+tmux combination. The default is `'hybrid'`, so a no-arg `run()` now spawns an attachable tmux side session whenever tmux is available.

### Fixed:
* cwd will now handle failures if the directory doesnt exist in the bash queue
* general improvements to bash script construction with per-job preamble commands
* slurm now correctly respects header/preamble commands

### Changed
* deprecate `header_commands` for `preamble`
* Dropped support for 3.8 and 3.9
* Transition from stubs to type annotations.


## Version 0.2.3 - Released 2025-12-09

### Fixed
* Issue with slurm 21.x

### Added
* Experimental feature to automatically handle activating virtual environments, currently disabled by default set  `--virtualenv_cmd=auto` to use with cmdqueue boilerplate scripts.
* Experimental airflow backend now has minimal functionality.


## Version 0.2.2 - Released 2025-02-19

### Added

* Add initial support for monitoring passed and failed jobs in slurm.


### Fixed

* Fixed compatibility issues with Slurm v23


## Version 0.2.1 - Released 2024-11-18

### Added
* Slurmify helper script
* Better slurm support

### Fixed
* fix `SlurmQueue.is_available` with slurm version 19.x


## Version 0.2.0 - Released 2024-06-27

### Added
* Add "gpus" as a CLI option

### Changed
* Made pint an optional requirement

### Removed

* Drop support for 3.6 and 3.7


## Version 0.1.20 - Released 2024-03-19


## Version 0.1.19 - Released 2024-02-01

### Fixed
* Fixed issue with single-argv commands in the bash interface


## Version 0.1.18 - Released 2023-08-09

### Changed

* CLI Boilerplate run-queue can now pass kwargs to the run method.


## Version 0.1.17 - Released 2023-07-07

### Changed
* Change the CLI to be modal


## Version 0.1.16 - Released 2023-06-22

### Changed:
* Added experimental `vertical_chains` argument to draw-network-text 


## Version 0.1.15 - Released 2023-06-15

### Added
* Add yes argument to CLI

### Changed
* Added more options to the serial queue `run` method.


## Version 0.1.14 - Released 2023-05-11


## Version 0.1.13 - Released 2023-05-11


## Version 0.1.12 - Released 2023-04-18

### Fixed
* allow workaround gres issue with slurm by explicitly specifying it.


### Changed
* consolidated print commands code, all backends use the same logic now.


## Version 0.1.11 - Released 2023-04-13

### Fixed
* Issue with `slurm_options`

## Version 0.1.10 - Released 2023-04-11

### Added
* the `cli_boilerplate` submodule for help writing consistent scriptconfig + cmdqueue CLIs
* util yaml


## Version 0.1.9 - Released 2023-04-04

### Added
* Support for more sbatch options in slurm backend

### Fixed
* Bugs in slurm backend


## Version 0.1.8 - Released 2023-03-05

### Added:
* New experimental CLI-queue feature. Create a pipeline in bash using the CLI.
  Very basic atm.

### Changed
* The log option to submit now default to False (due to non-obvious tee issues)

### Fixed:
* The serial queue now correctly reorders jobs into a topological order when necessary.

## Version 0.1.7 - Released 2023-01-28

### Added:
* Experimental CLI to help cleanup dangling tmux jobs

### Deprecated
* Deprecate `rprint` in favor of `print_commands`.
* Deprecate `use_rich` in `print_commands` in favor of `style='rich'`.

### Changed
* Tweaked text output
* Demo in the readme with better record demo scripts


## Version 0.1.6 - Released 2023-01-16

### Added:
* new `other_session_handler` arg to run, which can be ask, kill, ignore, or auto.

### Fixed:
* Textual monitor will now restart if you decide not to quit.

### Changed:
* tmux queue is condensed when size=1


## Version 0.1.5 - Released 2022-12-15

### Added
* UnknownBackendError and DuplicateJobError
* Add `tags` property to Jobs and `exclude_tags` to `rprint`.


## Version 0.1.4 - Released 2022-10-31

### Changed
* The kill-other-session logic now only asks to kill sessions with the same
  name.

* The serial / tmux queue now output stdout/stderr of each process to a log
  file and write a status indicating when a command has started to run.

* Slurm is available check now looks to see if any node exists that is not down.


## Version 0.1.3 - Released 2022-09-05


## Version 0.1.3 - Released 2022-09-05

### Fixed:
* Bug in serial queue when a dependency was None


## Version 0.1.2 - Released 2022-07-27

### Added
* Improved textual monitor for tmux queue
* Keep track of skipped jobs in tmux / serial queue
* The tmux queue can now clean up other existing sessions if you start fresh
* Basic airflow queue.

### Changed
* Job dependencies can now be given by name.

## Version 0.1.1 - Released 2022-07-27

### Fixed
* Bug where serial queue would execute jobs if any dependency passed.
* Minor dependency issues

## [Version 0.1.0] - Released

### Added
* Initial version

