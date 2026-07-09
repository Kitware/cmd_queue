# Phase 4: tmux backend correctness

**Goal:** Fix verified defects in `cmd_queue/backends/tmux.py` and
`cmd_queue/util/util_tmux.py`. The theme: the monitor's lifecycle decisions
(kill/keep/finished) are made from incomplete state, and re-running a queue
reuses stale on-disk state.

**Prerequisites:** Phases 1-2 (quoting/name validation removes several tmux
failure modes: unquoted session names, `.`/`:` in names, unquoted semaphore
paths). **Testing note:** tmux is available in CI's test lanes and skip-gated
locally; write tests with the existing `is_available` skip pattern used in
`tests/test_backend_execution.py`.

> Line numbers reference commit `0635f9c`.

## 4.1 [HIGH] Early monitor exit kills a running queue it promised to keep alive
`tmux.py:1090-1095`. `monitor()` ends with
`if onfail == 'kill' and not agg_state.get('failed'): self.kill()` with no check
that the queue actually finished. `run()` defaults to `onfail='kill'`, and two
early-exit paths return while jobs still run:

- pressing `q` in `_run_live_with_attach` (`:1653-1654`) — whose on-screen hint
  says "[q] to stop watching (queue keeps running)" (`:1594-1596`);
- Ctrl-C in `_simple_rich_monitor` then answering **No** to "kill the procs?"
  (`:1291-1296`) — the user explicitly declines, and we kill anyway.

Both then hit the unconditional kill, destroying all worker sessions mid-run.
`_print_done_summary` also prints "Queue complete: PASSED" with partial counts.
**Fix:** thread the `finished` flag from `_build_status_table()` out of the
monitor loops; gate the `onexit`/`onfail` cleanup AND the done-summary on it.
Early exits return a distinct "detached/aborted" state.
**Test:** monkeypatch/simulate: run a 2-job queue where job 2 sleeps; drive the
monitor loop to the early-exit path; assert sessions still alive, then clean up.
(A unit-level test of the gating logic with a fake `agg_state`/`finished` is
acceptable if driving the interactive loop is impractical.)

## 4.2 [HIGH] `self.workers` never initialized
`tmux.py:257`. `__init__` calls `self._new_workers()` and discards the result
(the method is pure). `self.workers` only exists after `order_jobs()`.
`kill()`, `read_state()`, `current_output()`, `monitor()`, and
`_write_monitor_manifest()` on a not-yet-run queue raise `AttributeError`.
**Fix:** `self.workers = self._new_workers()`.
**Test:** `q = TMUXMultiQueue(1, 'x'); q.submit('echo hi'); q.kill()` does not
raise (skip-gated on tmux availability; `kill` of never-started sessions must
also tolerate missing sessions).

## 4.3 [HIGH] `kill_other_queues` parses session names ambiguously
`tmux.py:664-673`. `parse.Parser('cmdq_{name}_{rootid}')` uses lazy groups, but
worker names embed `_{idx:03d}_` and rootids contain underscores
(`YYYY-MM-DD_<hash>`), so `name` always matches up to the first underscore.
Consequences: (a) headless default `other_session_handler='auto'` → `'kill'`
(`:693-704`) makes queue `train` kill queue `train_v2`'s live sessions;
(b) a queue named `my_queue` never matches its own conflicting sessions.
**Fix:** match `f'{self._tmux_session_prefix}{self.name}_' + r'\d{3}_' + rootid
pattern` exactly (regex, not `parse` with lazy groups).
**Test:** pure-function test on the matcher with the four name/session
combinations above.

## 4.4 [MEDIUM-HIGH] No stale-state cleanup on re-run
`tmux.py:574-611, 638-642, 770-777`. Semaphore flags
(`rank_flag_*.done`), per-job `.pass`/`.fail` files, and worker `state_fpath`s
are deterministic for a fixed `rootid` and never cleared. A second `run()` on
the same object: stale rank flags let later ranks start before earlier ranks
finish (dependency order violated); stale `.pass` files satisfy dep checks for
jobs still re-running; a stale `status: done` state file read in the window
before bash writes `init` makes the monitor declare finished instantly and (with
default `onfail='kill'`) kill the fresh sessions. The driver's
`tmux new-session -d -s {pathid}` also fails on the duplicate name (driver has
no `set -e`) and then `tmux send` types into the *old* session.
**Fix:** in `run()`/`write()`: clear the semaphore dir, remove per-job status
flag files and worker state files before launching; fail loudly (or kill first)
if the target session already exists.
**Test:** run a small queue twice on the same object; second run passes with
correct ordering (job with a dep on a sleeping job must not start early — encode
via timestamps written by each job).

## 4.5 [MEDIUM] Dead worker session blocks the monitor forever
`tmux.py:955-969, 1298-1358`. Completion is judged purely from worker state
files; worker scripts are *sourced* into the session's interactive bash
(`:639-641`), so a job script that calls `exit`, or an externally killed/OOM'd
session, leaves `status: run` forever and `run(block=True)` never returns
(production default has no timeout, `util_tmux.py:47`); later-rank sessions spin
in the `sleep 1` semaphore loop as orphans.
**Fix:** each poll tick, cross-check `tmux.has_session(worker.pathid)`; session
gone + state != done → mark worker failed/aborted, stop blocking, and reflect it
in `agg_state`.
**Test:** start a queue whose job is `sleep 60`, kill the worker session
out-of-band, assert `run(block=True)` returns with a failure within a few ticks.

## 4.6 [MEDIUM] `capture-pane` hardcodes `:0.0`
`util_tmux.py:103-105`. Users with `base-index 1`/`pane-base-index 1` (very
common tmux config) have no window 0 → every `onexit='capture'` /
`current_output()` call errors.
**Fix:** target just the session (`-t <session>` captures its active pane) or
resolve the first pane via `list-panes -F '#{window_index}.#{pane_index}'`.

## 4.7 [MEDIUM] Ctrl-C in `block_with_attach_prompt` masquerades as completion
`util_tmux.py:298-301` + `tmux.py:941-949`. The enclosing
`except KeyboardInterrupt: return` makes an abort indistinguishable from
"finished"; the caller prints "Queue complete: PASSED passed=3 ... total=40"
while 37 jobs still run.
**Fix:** propagate KeyboardInterrupt or return an "aborted" sentinel; only print
the completion summary when `is_finished_fn()` returned true. (Coordinate with
4.1's finished-flag threading.)

## 4.8 [LOW-MEDIUM] Explicit `with_textual=True` without textual → TypeError
`tmux.py:1079-1087, 1113`. Only `'auto'` is mapped through the availability
check; explicit `True` with the import failed (`:1680-1687`,
`CmdQueueMonitorApp = None`) crashes after jobs launched.
**Fix:** coerce truthy `with_textual` to False with a warning when the app class
is None. **Test:** monkeypatch `CmdQueueMonitorApp = None`, call with
`with_textual=True`, assert no crash + warning.

## 4.9 [LOW-MEDIUM] Textual monitor has no "stop watching without killing" path
`tmux.py:1110-1140` + `monitor_app.py:241-242`. `q` exits the app with
`graceful_exit=False` → kill-confirm prompt; answering No re-launches the app.
The hybrid hint advertises "[q] to stop watching (queue keeps running)".
**Fix:** treat `q` without kill-confirmation as "stop watching" and return
(requires 4.1 so returning doesn't kill). Depends on Phase 6's monitor_app fix
for the `k` binding crash — coordinate.

## 4.10 [LOW] Hybrid side-session name collision aborts `run()` mid-flight
`tmux.py:861-874` + `util_tmux.py:183`. `spawn_monitor_session` uses
`check=True` on `tmux new-session -s cmdq-monitor-{pathid}`; a stale session
from a hard-killed previous run makes `run()` raise after workers launched (no
monitoring, no cleanup, no summary).
**Fix:** kill or reuse the existing session first (`new-session -A` or
pre-`kill_session`). Also move the "Spawned attachable monitor..." message
(`:864-867`) to after the spawn succeeds.

## 4.11 [LOW] `list_panes` crashes on missing session / empty output
`util_tmux.py:383-397`. Unchecked `ub.cmd`; empty stdout →
`json.loads('')` raises. Check the return code and skip empty lines. (Note:
`list_panes`/`kill_pane` currently have no in-repo callers — if 9.x dead-code
cleanup removes them, skip this.)

## Verification

- New/updated tests pass locally with tmux installed (`tmux -V`), and are
  properly skip-gated where tmux is unavailable.
- Manual smoke: `python examples/tmux_example.py` (or the README tmux snippet)
  through `run(monitor='hybrid')`; press `q`; verify with `tmux ls` that
  `cmdq_*` worker sessions survive; re-attach monitor via `cmd_queue monitor`;
  let it finish; verify cleanup per `onexit`.
- Full suite + doctests + ruff + ty green.
