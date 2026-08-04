# Phase 6: airflow backend, textual monitor, CLI boilerplate

**Goal:** Fix a destructive airflow bug, a crash in the interactive monitor, and
assorted CLI-layer defects.

**Prerequisites:** Phase 1. Independent of Phases 4-5 except where noted.
**Testing note:** airflow is an optional extra (`pip install cmd_queue[airflow]`,
pinned `apache-airflow>=3.1.3`); airflow tests use `importorskip`. The textual
fix is testable with textual's `run_test` harness (textual is in the optional
extras and was verified against 8.2.8).

> Line numbers reference commit `0635f9c`.

## 6.1 [CRITICAL] `AirflowQueue.run()` can wipe an external Airflow metadata DB
`backends/airflow.py:197-200, 253-254`. `_airflow_env` only **setdefault**s
`AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`, so a value exported in the user's shell
(standard for anyone operating a real Airflow deployment) is kept — and `run()`
then unconditionally prefers `db.resetdb()` (drops and recreates ALL tables,
true on every supported Airflow 3.x since `hasattr(db, 'resetdb')`). A user with
a production connection string in their environment who runs a cmd_queue
airflow queue destroys their production metadata DB. Lesser variant: a shared
`airflow_home=` (as the module doctest at line 18 uses) erases all prior run
history on every `run()`.
**Fix:** force-set (not setdefault) the connection string to the per-queue
sqlite path; only `resetdb()` when that sqlite file does not yet exist,
preferring `db.migratedb()`/upgrade otherwise. Add a test asserting the env
override wins over an ambient `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`.

## 6.2 [HIGH] Pressing `k` (kill) in the textual monitor crashes the UI
`monitor_app.py:118-120`. `ConfirmKillScreen.on_mount` calls `self.bind(...)`,
but textual defines `bind()` only on `App`, never on `Screen`/`ModalScreen`
(verified on textual 8.2.8; no 4.x+ version has it). Since
`TMUXMultiQueue._textual_monitor` always passes `kill_fn=self.kill`
(tmux.py:1113-1115), every interactive tmux-monitor user who presses `k` gets
an `AttributeError` crash instead of a confirm dialog.
**Fix:** replace the `on_mount` binds with a `BINDINGS` class variable on
`ConfirmKillScreen`: `[('y', 'confirm_kill', ...), ('n', 'cancel_kill', ...)]`.
The `q`/`k`/`a` binds in `CmdQueueMonitorApp.on_mount` are fine (`App.bind`
exists).
**Test:** textual `run_test` harness — press `k`, assert the modal appears;
press `n`, assert it dismisses without killing; press `k` then `y`, assert
`kill_fn` was called. (Coordinate with Phase 4.9, which adds a
stop-watching-without-kill path through this same app.)

## 6.3 [HIGH] `--backend=airflow --run=1` via the CLI boilerplate crashes
`backends/airflow.py:226`. `AirflowQueue.run(block, system)` takes no
`**kwargs`, but both `CMDQueueConfig.run_queue` (cli_boilerplate.py:372-377)
and `CmdQueueConfigMixin.run_queue` (cli_boilerplate.py:596-602) always pass
`with_textual=`, `other_session_handler=`, `monitor=` →
`TypeError: run() got an unexpected keyword argument` after the queue is built.
**Fix:** add `**kwargs` to `AirflowQueue.run` matching the other backends.
**Test:** extend `tests/test_airflow_queue.py` (importorskip'd) to drive
`run_queue`-style kwargs; or at minimum an inspection test that every
registered backend's `run` accepts the boilerplate kwargs (this also protects
future backends — see Phase 7's backend-contract suite).

## 6.4 [MEDIUM] `demo()` broken on every supported Airflow version
`backends/airflow.py:528-547`. Imports `airflow.operators.bash` (removed in
Airflow 3.0) and calls `dag.run()` (removed; `dag.test()` is the replacement
the real `run()` already uses). Port to
`airflow.providers.standard.operators.bash` + `dag.test()`, or delete `demo()`
and the `__main__` block. Also fix stale CommandLine pointers
(`airflow.py:6-7, 553`) that target the `cmd_queue.airflow_queue` shim (whose
docstring has no doctests), and refresh the `+SKIP`'d class doctest
(`:86-96`) that calls a pre-refactor `read_state()` flow.

## 6.5 [MEDIUM] `onfail=kill` means opposite things in tmux vs slurm
`main.py:385-394` (help text: "`kill` cancels still-running workers" on
failure), vs tmux (`tmux.py:1023-1027, 1093`): kill on *clean exit*, keep on
failure; slurm (`slurm.py:998-1002`): kill on failure, as the help says.
**Fix (decide once, document in CHANGELOG):** reconcile to one semantic across
backends — recommended: `onfail='kill'` cancels remaining work when a failure
occurs (the plain reading, and slurm's behavior), and tmux's
keep-alive-for-debugging behavior moves to `onfail='keep'` (already the tmux
docstring's vocabulary). Update `main.py` help, both backends' docstrings, and
Phase 4.1's gating logic together.

## 6.6 [LOW-MEDIUM] `resolve_manifest` lets a stray cwd file shadow a queue name
`monitor_manifest.py:88-94`. `candidate.is_file()` is checked before the
active-index lookup, so `cmd_queue monitor foo` with an unrelated `./foo` file
(this repo currently has one!) dies with `JSONDecodeError`. Validate that the
file parses as a manifest (or has the expected suffix) before accepting;
fall through to the index otherwise. **Test:** create a junk file matching a
registered name; monitor resolves the registered queue.

## 6.7 [LOW] airflow dead parameters and duplication
- `AirflowJob.__init__` accepts `partition` (`airflow.py:52`) but never stores
  it; `submit()` computes an `output_fpath` log path (`:442-443`) that
  `finalize_text` never uses, so the promised per-job log is never written.
  Wire the log through (redirect in `bash_command`) or drop both.
- `read_state` (`:332-345`): try/except bodies identical except the import —
  deduplicate.
- BashOperator Jinja-templates `bash_command`: user commands containing
  `{{ }}` are rewritten and commands ending in `.sh` trigger "template file not
  found". Document, or render tasks with templating disabled
  (`Template fields`/`render_template_as_native_obj` — investigate the
  supported knob on Airflow 3.x).

## 6.8 [LOW] cli_boilerplate cleanups
- `run_queue` duplicated verbatim between `CMDQueueConfig` and
  `CmdQueueConfigMixin` (cli_boilerplate.py:327-377 vs 554-602), and it mutates
  the caller's config in place (`config['print_commands'] = 1`). Factor into a
  shared helper using locals. (The class is deprecated but still shipped —
  keep it working until removal, see Phase 9.)
- `cli_boilerplate.py:324` calls deprecated `add_header_command` → use
  `add_preamble_command` (the Mixin already does at `:551`).
- `monitor_app.py`: `JobTable.refresh_status` runs `table_fn` synchronously on
  the UI loop every 0.5s; tmux's table_fn shells out — offload via
  `run_worker`/thread so a slow call doesn't stall the UI.
- `main.py:146-148` `workers` help ("number of concurrent queues") vs
  `tmux_workers` in cli_boilerplate — align wording.

## Verification

- With airflow installed (`pip install -e .[airflow]`): `pytest
  tests/test_airflow_queue.py` green; run the module doctest flow with a
  poisoned `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` env var pointing at a scratch
  sqlite file and assert that file is untouched.
- With textual installed: monitor `run_test` tests green; manual smoke of the
  tmux hybrid monitor (`k` → dialog → `n` keeps running; `y` kills).
- Full suite + doctests + ruff + ty green.
