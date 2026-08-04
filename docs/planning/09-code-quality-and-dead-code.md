# Phase 9: Code quality, dead code, and API consistency

**Goal:** Remove vestigial code and resolve API inconsistencies. Lowest urgency,
highest reviewer-goodwill. Everything here is behavior-preserving unless marked.

**Prerequisites:** Phases 2-6 (don't delete code a fix phase is about to touch).

## 9.1 Dead code to delete

- `slurm.py:594-632` — `_slurm_checks` never called, returns None.
- `slurm.py:571, 803, 1138` — vestigial `if 0:` / `if 1:` / `if True:` blocks.
  Note `:810` unconditionally resets `_include_monitor_metadata = True`, making
  the constructor/`_from_manifest` values meaningless — decide to honor the
  flag or remove it.
- `tmux.py:990-1004` — `serial_run()`, self-described as deprecated.
- `tmux.py:1690-1785` — `if 0:` `__tmux_notes__` block, ~95 lines of scratch
  notes in module body. Move anything worth keeping to `dev/notes/` or docs.
- `tmux.py:760-768` — deprecated `check_other_sessions` handling in `run()`;
  it can double-process conflicting sessions since `handle_other_sessions`
  already ran unconditionally at `:758`. Complete the deprecation.
- `util_tmux.py:328-397` — `list_panes`/`kill_pane` have no in-repo callers;
  delete or test-and-keep deliberately (see Phase 4.11).
- `serial.py:850-878` — ~30 lines of commented-out legacy `print_commands`
  after a `return`.
- `base_queue.py:234-237` — dead round-trip
  (`kwargs['depends'] = depends` then immediately `pop`).
- `serial.py:585-586, 813-827` — `SerialQueue.__init__` re-initializes
  `self.preamble`/`self.jobs` already set by `super().__init__()`, and
  re-defines `add_header_command`/`add_preamble_command` identical to the base
  class (one needs `# type: ignore` for its trouble). Delete the duplicates.
- `cli_boilerplate.py` — the module is deprecated (kwconf migration, commit
  `5642cc7`). Set a removal version (e.g. 0.4.0), say it in the module
  docstring's deprecation notice, and keep it working until then (Phase 6.8
  keeps it minimally healthy).

## 9.2 API consistency

- **Return annotations that lie:** `TMUXMultiQueue.run` (tmux.py:710-721,
  `-> None`) returns `agg_state`/`_dispatch_monitor(...)`; `monitor()`
  (tmux.py:1006-1014, `-> None`) returns `agg_state` (`:1096`). Fix
  annotations to the real (documented, `_print_done_summary`-shaped) dict —
  and add that shape to the Phase 7.3 contract test.
- **Base `Queue.monitor`** (base_queue.py:496-503) prints "monitor not
  implemented" and returns, while `run`/`kill`/`finalize_text`/`read_state`
  raise `NotImplementedError`. Make it raise for consistency.
- **`SerialQueue.run()` failure signaling** (deferred from Phase 3.4): script
  ends `set +e` → exit 0 even when jobs failed; `run()` returns None. Decide:
  return final state dict (matching tmux/slurm post-annotation-fix) and/or an
  opt-in raise-on-failure. Behavior change → CHANGELOG.
- **`BashJob.__init__` silently discards `gpus`/`cpus`/`mem`**
  (serial.py:103-125) — cross-backend acceptance is intentional, but stash
  them (e.g. `self.kwargs`) so introspection and `change_backend` don't lose
  resource requests.
- **`serial.py:124`** — `assert self.name is not None` vanishes under
  `python -O`; raise `ValueError`.
- **`agg_state` totals** (tmux.py:1329-1344) omit workers in `unknown` state,
  so the aggregate `total` fluctuates during startup; use
  `self.num_real_jobs`.
- **Facade `__all__` re-exports private names**: `serial_queue.py` exports
  `_check_bash_text_for_syntax_errors`; `tmux_queue.py` exports four
  underscore names. Remove privates from the facades' `__all__` (they invite
  external dependence on internals).
- **tmux.py:695** — `handle_other_sessions` imports `has_stdin` from the
  `cmd_queue.tmux_queue` facade, which imports it back from this very file
  (defined at `:1669`). Use the local name.
- **Error types:** `serial.py:993-1004` raises Python's builtin `SyntaxError`
  for a *bash* syntax error and prints stderr instead of attaching it — define
  `BashSyntaxError(Exception)` carrying stderr. `base_queue.py:352-360`
  swallows all exceptions from `transitive_reduction` and prints `ex=...` —
  catch `nx.NetworkXError` specifically and fall back to unreduced rendering
  with a clear message. `_graph.py:60-67` — guard edge-only nodes (deps never
  submitted) with a "dependency X was never submitted to this queue" error
  instead of latent KeyErrors downstream.

## 9.3 Performance / structure (optional, do last)

- `tmux.py` — `order_jobs()` runs 2-3× per operation (`write()` → itself, then
  `finalize_text()` again; `print_commands` triple-orders), rebuilding all
  SerialQueue workers and regenerating bookkeeper jobs with fresh uuid
  stat-paths each time (the written scripts and the monitor manifest can
  reference *different* bookkeeper paths — currently benign only because
  bookkeepers are excluded from failure accounting). Cache the ordering or
  make `finalize_text` reuse current workers. This is the riskiest change in
  this phase — do it with the Phase 4 tests already green.
- `tmux.py:511-512` — `for m in members: rankings[rank].update(members)`
  repeats the identical set-update len(members) times; hoist out of the loop.
- `tmux.py:1489` — the monitor manifest serializes each worker's full
  `environ` (the code comments at `:633-634` explicitly worry about logging
  secrets in plaintext); the monitor never reads `environ` — drop it from the
  manifest.
- `util_tmux.py:99-105, 131-133` — use tmux exact-match targets (`-t =name`)
  so prefix matching can't kill/find a different session extending the name
  (complements Phase 4.3).
- `tmux.py:74` — class doctest imports `from cmd_queue.serial_queue import *`
  which doesn't export `TMUXMultiQueue` (works only via doctest global
  seeding); use `tmux_queue`.
- `serial.py:969-990` — `indent`'s doctest lives inside `Returns:` (never
  runs); move to an `Example:` block. Consider replacing the local `indent`
  with `ub.indent` if equivalent.

## Verification

Behavior-preserving claims are backed by the (now-strengthened) suite:
full pytest + doctests + ruff + ty green after every deletion commit.
Grep for stragglers: `grep -rn "if 0:\|if False:" cmd_queue/` returns nothing
unexplained; `python -X dev -W error::DeprecationWarning -c "import cmd_queue"`
raises nothing from our own modules.
