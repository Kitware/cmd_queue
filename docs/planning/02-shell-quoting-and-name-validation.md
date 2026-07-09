# Phase 2: Shell quoting and name validation (cross-cutting hardening)

**Goal:** Eliminate the single largest defect class in the codebase — unescaped
interpolation of user-controlled strings into generated bash — by introducing
shared helpers and tight name validation, then applying them everywhere.

**Prerequisites:** Phase 1 (green baseline). **Estimated scope:** medium-large.
This phase should land BEFORE the per-backend bug phases because many of their
bugs are instances of this class; fixing the class first avoids double work.

> Line numbers reference commit `0635f9c`. Locate by symbol if drifted.

## Why this is the top defect class

The audit found unquoted/unescaped interpolation in every generator:

- **serial**: `export {k}="{v}"` (environ → command injection), unquoted
  `mkdir -p {path}` / `printf "pass" > {path}` / `[ -f {dep.pass_fpath} ]` /
  `tee {log_fpath}` / `cd {self.cwd}`
- **slurm**: `--job-name="{name}"`, `--output="{path}"`, `--{key}="{value}"`,
  `scancel --name="{name}"` (values with `"` or `$(...)` corrupt argv or execute
  at submit time — only `--wrap` uses `shlex.quote` today)
- **tmux**: unquoted session names and `[ ! -f {flag_path} ]` semaphore tests;
  f-string tmux commands in `util_tmux`
- **util_bash**: `bash_json_dump` interpolates values into a JSON template with no
  escaping and concatenates the output path unquoted
- **main.py CLI**: the single-arg `shlex.quote` "hack" that breaks compound commands

A name like `my job`, a value like `say "hi" $(whoami)`, or a dpath under
`"My Drive"` silently corrupts status tracking or executes code.

## 2.1 Add shared helpers

Create `cmd_queue/util/util_quote.py` (or extend `util_bash.py`) with:

```python
import re
import shlex

_NAME_PAT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.\-]*$')

def validate_job_name(name: str) -> str:
    """Raise ValueError naming the offending character if `name` is not safe
    for filenames, tmux session names, and unquoted bash words.
    tmux additionally forbids '.' and ':' in session names — since job/queue
    names feed session names, forbid '.' and ':' too (tighten _NAME_PAT
    accordingly or strip dots at the tmux layer; pick one and document it)."""

def shquote(value) -> str:
    """shlex.quote(str(value)) — one obvious spelling used by all generators."""
```

Decide the exact allowed character class once, document it in the `Queue.submit`
docstring, and mention it in the CHANGELOG (it is a behavior change: names that
previously "worked" by luck may now be rejected — that is the point).

## 2.2 Apply at the choke points

1. **Name validation** — `base_queue.py:229-230` currently only rejects `':'`.
   Replace with `validate_job_name`. Also apply to:
   - `Queue.__init__` / backend `__init__`s for the queue `name` (a space in the
     queue name currently breaks `TMUXMultiQueue` session creation — the driver
     runs `tmux new-session -d -s {pathid} "bash"` unquoted — and breaks
     `SlurmQueue.run()`'s unquoted `ub.cmd(f'bash {self.fpath}')`).
   - `SlurmQueue.submit` (slurm.py:694-756), which bypasses the base check today.
2. **serial.py generators** — quote every interpolated path:
   `serial.py:197-209, 223, 232, 327, 333, 736` (`cd {self.cwd}` is unquoted while
   the job-level `pushd "{self.cwd}"` at :274 is quoted). Since paths are literal,
   plain `"..."` wrapping is sufficient, but `shquote` is uniform and safer.
3. **serial.py environ export** — `serial.py:727-729`:
   ```python
   script.extend(f'export {k}={shquote(v)}' for k, v in self.environ.items())
   ```
   and validate `k` as a bash identifier (`^[A-Za-z_][A-Za-z0-9_]*$`).
4. **util_bash.bash_json_dump** (`util_bash.py:41-47`) — quote the redirect target
   and JSON-escape interpolated string values (`json.dumps(value)` produces a
   correctly escaped JSON string; embed that). Fix the docstring example, whose
   documented `%s` usage produces invalid unquoted JSON.
5. **slurm.py sbatch lines** — `slurm.py:358, 395, 400` and the scancel calls at
   `:1164, 1309`: build every flag as `'--flag=' + shquote(value)` instead of
   `--flag="{value}"`. `--wrap` already does this; make the rest match.
6. **tmux semaphore + driver** — `tmux.py:335` (`'[ ! -f {} ]'.format(p)` →
   quote), `tmux.py:638-642` (driver script session names), and convert the
   f-string commands in `util_tmux.py:99-105, 131-133` (`_kill_session_command`,
   `_capture_pane_command`, `kill_pane`) to argv lists like the rest of that class.
7. **main.py CLI single-arg hack** — `main.py:187-194`. The current code applies
   `shlex.quote` to a single-element command that "needs quoting", turning the
   documented `cmd_queue submit q -- 'cowsay MOO && sleep 1'` into a single quoted
   word → exit 127. A one-element list is already a complete bash command line the
   user quoted once in their shell: use it as-is (`bash_command = bash_command[0]`
   in both branches). Only the multi-token case needs per-token `shlex.quote`+join.

## 2.3 Regression tests

Add `tests/test_shell_quoting.py`:

- Job/queue names with a space, `"`, `$`, `.`, `:` → `ValueError` from `submit`
  (and from queue constructors).
- `SerialQueue(environ={'V': 'say "hi" $(true)'})` → rendered script contains a
  correctly quoted export; run the queue and assert the env var round-trips
  verbatim (execute with `bash -c`, echo `$V` to a file, compare).
- dpath containing a space (use `tmp_path / 'has space'`) → serial queue runs,
  `.pass` files land in the right place, `read_state()` reports passed.
- `bash_json_dump` with a value containing `"` and `\` → output parses with
  `json.loads`.
- CLI: `cmd_queue new t && cmd_queue submit t -- 'true && true' && cmd_queue run t
  --backend=serial` (drive via `main()` in-process like `tests/test_cli.py` does)
  → exit 0, state shows passed. This is the Quickstart's own documented usage and
  is broken today.
- Slurm (no cluster needed — text-level): `SlurmJob('echo hi', 'n',
  comment='say "hi" $(whoami)').finalize_text()` contains no bare `$(` outside
  single quotes; parse the sbatch line with `shlex.split` and assert the comment
  survives as one argv element.

## Verification

- New test file passes; full suite passes; `ruff` and `ty` clean.
- `grep -n '="{' cmd_queue/backends/*.py` returns no sbatch/export-style
  interpolations (spot-check any remaining hits are safe).
- Doctests still pass: `./run_doctests.sh` (quoting changes alter generated text;
  update any doctest expected output deliberately, not by blind copy).
