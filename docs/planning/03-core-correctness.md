# Phase 3: Core correctness (base_queue, serial backend, CLI)

**Goal:** Fix verified logic bugs in the queue core and serial backend. Every fix
gets a regression test in the same commit.

**Prerequisites:** Phase 2 (several fixes below assume the quoting helpers exist).

> Line numbers reference commit `0635f9c`. Bugs marked [verified] were reproduced
> during the audit. Ordered by severity within each file.

## 3.1 serial backend (`cmd_queue/backends/serial.py`)

### 3.1.1 [HIGH, verified] `log=True` without guards masks failures via tee
`serial.py:330-336, 357-359`. With `log=True` the command renders as
`(cmd) 2>&1 | tee logfile`, but `set -o pipefail` is only emitted when
`with_gaurds` is true, so with `with_status=True, with_gaurds=False` the
`RETURN_CODE=$?` captures **tee's** exit status: a failing job writes
`{"ret": 0}` and creates its `.pass` file, and dependents run on a failed dep.
**Fix:** emit `set -o pipefail`/`set +o pipefail` whenever `self.log` is set,
independent of `with_gaurds` — or capture `${PIPESTATUS[0]}` in the no-guards
status branch.
**Test:** render `BashJob('false', name='j', log=True).finalize_text(
with_status=True, with_gaurds=False)`, execute with bash, assert the status JSON
has nonzero `ret` and no `.pass` file.

### 3.1.2 [MEDIUM, verified] `run(mode='source')` always fails where /bin/sh is dash
`serial.py:905-914`. `ub.cmd(f'source {self.fpath}', shell=True)` runs under
`/bin/sh`; `source` is a bashism → exit 127 on Debian/Ubuntu. Also note sourcing
in a child process can never affect the caller's environment, so the mode's
implied purpose is unachievable.
**Fix:** run via `bash -c 'source <fpath>'` (or `executable='/bin/bash'`), or
remove the mode. Additionally `run()`'s `mode` parameter accepts any string and
executes `f'{mode} {self.fpath}'` (the `raise KeyError` is commented out at
`serial.py:882-925`) — validate against known modes.
**Test:** `SerialQueue` with one job, `run(mode='source')` → passes;
`run(mode='bogus')` → raises.

### 3.1.3 [LOW] `exclude_tags` desynchronizes numbering and totals
`serial.py:655, 668, 753-757, 779`. `total = self.num_real_jobs` is computed
before tag filtering, so a queue of 8 with 2 excluded renders
`### Command 1 / 8` … `6 / 8` and status `{"passed": 6, "total": 8}` — reads as a
partial failure. **Fix:** count post-filter jobs for both banner and
`_CMD_QUEUE_TOTAL`. **Test:** finalize with `exclude_tags`, execute, assert
`read_state()['total']` equals the included-job count.

### 3.1.4 [LOW] `job_details` crashes on jobs that never ran
`serial.py:927-937`. `job.stat_fpath.read_text()` is unguarded; a skipped or
never-run job raises `FileNotFoundError` mid-printout. Guard on existence like the
adjacent `log_fpath` handling.

## 3.2 base_queue (`cmd_queue/base_queue.py`)

### 3.2.1 [MEDIUM, verified] Duplicate-name check runs after `jobs.append`
`base_queue.py:259-267`. On `DuplicateJobError` the duplicate job is already in
`self.jobs`; a caller that catches the error (it subclasses `KeyError`; "already
submitted, skip" is a natural pattern) leaves the queue permanently corrupted —
`order_jobs`/`finalize_text`/`print_graph` all raise `Job names must be unique`.
**Fix:** check (and `_register_named_job`) before appending. While here, delete
the no-op `try: ... raise ... except Exception: raise` wrapper (`:261-265`).
**Test:** submit dup name, catch `DuplicateJobError`, assert `len(q.jobs) == 1`
and `q.finalize_text()` succeeds.

### 3.2.2 [MEDIUM, verified] `coerce_job_depends` explodes strings into characters
`base_queue.py:65-77`. `list(depends)` on a str yields characters (historical
`ub.iterable` treated str as scalar). `Queue.submit` resolves strings first, so
this bites only direct construction: `BashJob('echo hi', name='a',
depends='job1')` → `['j','o','b','1']`, later an opaque
`AttributeError: 'str' object has no attribute 'pass_fpath'`.
**Fix:** raise `TypeError` on str input with a message pointing at
`Queue.submit(depends='name')` as the supported spelling.
**Test:** direct `BashJob(..., depends='x')` raises `TypeError`.

### 3.2.3 [LOW-MEDIUM, verified] `change_backend` KeyError + dropped preamble
`base_queue.py:145-159`. A dependency job never submitted to the source queue →
bare `KeyError`; jobs with `command=None` are silently dropped; `self.preamble`
is not carried to the new queue. **Fix:** raise a descriptive error for
unregistered deps; copy `preamble`; document (or warn on) dropped command-less
jobs. **Test:** `change_backend` on a queue with a preamble → preamble present in
output text of the new backend.

### 3.2.4 [LOW, verified] Auto-generated names can collide with explicit names
`base_queue.py:222-226`. Auto-name is `f'{name}-job-{num_real_jobs}'` with no
collision check: `submit(name='q-job-1')` then two anonymous submits → spurious
`DuplicateJobError` (and pre-3.2.1, a corrupted queue). **Fix:** increment until
unused. **Test:** the exact scenario above succeeds.

### 3.2.5 [LOW] `print_commands` drops **kwargs, contradicting its docstring
`base_queue.py:368-435`. Docstring promises forwarding to `finalize_text`; the
call at `:430-435` passes only four fixed kwargs. **Fix:** pop handled keys
(`colors`, `with_rich`) and forward the rest. Note `BashJob.print_commands`
(serial.py:472) already forwards correctly.

### 3.2.6 [LOW, verified] `style='auto'` resolves inconsistently
`base_queue.py:401, 423-424` yields `'plain'` (because
`colors = kwargs.get('colors', None)` is falsy) while `_rendering.coerce_style`
(`_rendering.py:25-27`) defaults to `'colors'`. Same argument, opposite result
between `Queue.print_commands` and `BashJob.print_commands`.
**Fix:** consolidate both the `colors` and `with_rich` deprecations plus the
`'auto'` rule inside `_rendering.coerce_style`, delete the inline copy in
`base_queue`, and have `BashJob.print_commands` call the free function directly
instead of `base_queue.Queue._coerce_style(self, ...)` with a Job as `self`
(serial.py:468-470, currently `# ty: ignore`d).

## 3.3 CLI (`cmd_queue/main.py`)

### 3.3.1 [HIGH, verified] Single-arg quoting hack breaks documented usage
`main.py:187-194` — covered by Phase 2 (task 2.2.7). If Phase 2 landed, just
confirm the regression test exists; otherwise fix here.

### 3.3.2 Debug prints pollute every `show`/`run`
`main.py:175` (`print('data = ...')`), `:203-208` (`print('\n\n\n')`,
`print(f'submitkw=...')`). Gate on `config.verbose > 1` or delete.
Also `cmd_queue/util/util_yaml.py:127-129` — two live debug prints inside the
ruamel `!include` constructor pollute stdout for any CLI config using `!include`
(the commented-out sibling at `:37` shows the intent). Delete both.

### 3.3.3 [LOW] `qname=None` writes `None.cmd_queue.json`
`main.py:121-125`. `cmd_queue new` with no positional silently creates a queue
named `None`. **Fix:** in `cli_queue_fpath`, `SystemExit('a queue name is
required')` when falsy. **Test:** drive `main()` with `new` and no name → error.

### 3.3.4 [LOW] CLI `submit` accepts a missing command
`main.py:538-548`. `command=None` is appended to the queue file; the error only
surfaces at `run` time as `TypeError(<class 'NoneType'>)`. Validate at submit.

### 3.3.5 Robustness cleanups (do together)
- `main.py:434-446` — capability sniffing via `__code__.co_varnames` includes
  locals; use `inspect.signature(queue.monitor).parameters`. Remove the
  `try/except Exception: pass` around a plain attribute read.
- `main.py:183` — CLI calls deprecated `add_header_command`, warning on every
  run; call `add_preamble_command`.
- `main.py:341-347` — `cleanup` prompts "kill these?" for an empty list;
  short-circuit. `submit`/`show`/`run` on a nonexistent queue surface a raw
  `FileNotFoundError`; catch and suggest `cmd_queue new <name>`.

## 3.4 Deferred design issues (document, don't fix here)

- `SerialQueue.run()` returns `None` and never fails on job failure (script ends
  `set +e`, exits 0) — callers must call `read_state()`. Consider returning final
  state and/or a `check=True` raise-on-failed option. API change → Phase 8.
- CLI queue JSON file has no locking; concurrent `submit`s lose rows
  (acknowledged in module `__todo__`). An `flock` around read-modify-write is a
  cheap interim fix.

## Verification

Each numbered fix lands with its regression test. After the phase:
`python3 -m pytest tests/ -q` green, `./run_doctests.sh` green, `ruff`/`ty` clean,
and `python3 -m cmd_queue --help` plus the README Quickstart CLI flow work
end-to-end in a scratch directory.
