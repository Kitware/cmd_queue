# Phase 5: slurm backend correctness

**Goal:** Fix verified defects in `cmd_queue/backends/slurm.py` and
`cmd_queue/slurmify.py`. Highest-impact clusters: (a) squeue scraping that
crashes real monitors, (b) out-of-the-box malformed sbatch lines,
(c) submission/DAG integrity holes.

**Prerequisites:** Phases 1-2 (sbatch value quoting is Phase 2 task 2.2.5).
**Testing note:** most fixes are testable at the text level
(`finalize_text()` / rendered script assertions) without a cluster — extend
`tests/test_slurm_variants.py`. Live behavior is covered by the skip-gated
`tests/test_backend_execution.py` lane; `dev/slurm` contains a toolkit for
spinning up a test slurm. Recent commits already fixed: boolean-flag trailing
quote, scontrol bare-token parsing, KeyError on purged jobs, headless
`monitor='none'` — do not redo those.

> Line numbers reference commit `0635f9c`.

## 5.1 Monitor robustness (crashes observed in real runs)

### 5.1.1 [HIGH] Multi-word squeue REASON kills the monitor
`slurm.py:1140-1142`. `update_status_table` parses
`squeue --format="%i %P %j %u %t %M %D %R"` with `pd.read_csv(stream, sep=' ')`.
`%R` (NODELIST/REASON) routinely contains spaces for pending jobs — e.g.
`(Nodes required for job are DOWN, DRAINED or reserved)` → `ParserError:
Expected 8 fields ... saw 16`. squeue output is not filtered to this queue, so
ANY job on the cluster in such a state kills the live monitor mid-run. Even when
pandas doesn't raise, columns silently misalign, breaking the NAME filter and
the `(DependencyNeverSatisfied)` auto-scancel.
**Fix (preferred):** use `squeue --json` when available (slurm >= 20.02;
`is_available` already version-gates `sinfo --json`, reuse that plumbing), with
a text fallback that splits each line manually via `line.split(' ', 7)` so the
REASON tail stays intact. Drop `pd.read_csv` for this entirely.

### 5.1.2 [HIGH] Transient squeue failure crashes the monitor / fakes completion
`slurm.py:1140-1142` and `:960-966`. `ub.cmd('squeue ...')` return code is never
checked: a slurmctld hiccup gives empty stdout → `pd.read_csv` raises
`EmptyDataError` in the inline monitor; in `monitor='tmux'` mode `_is_finished`
treats the same empty output as "finished" and returns while jobs still run.
**Fix:** check `info['ret']`; on failure skip the tick (keep previous state);
in `_is_finished`, treat failed squeue as "not finished".

### 5.1.3 [MEDIUM] `refresh_rate` parameter unconditionally discarded
`slurm.py:1274` overwrites the `refresh_rate: float = 0.4` argument from `:982`
with a local `= 0.4`. Callers cannot slow the poll, which currently runs one
`squeue` plus one `scontrol show job` **per unfinished job** per 0.4s tick —
hammering slurmctld on large queues. **Fix:** delete line 1274. Then (perf,
same area): replace per-job `scontrol show job` (`:1085-1099`) with one batched
`sacct -j id1,id2,... --format=JobID,State,ExitCode --parsable2` (or
`squeue --jobs=... --json`) per tick.

### 5.1.4 [MEDIUM] Ctrl-C in non-interactive monitor raises; partial state lost
`slurm.py:1292-1298`. The `KeyboardInterrupt` handler calls
`rich.prompt.Confirm.ask` unconditionally (EOFError when stdin is not a tty,
e.g. nohup/CI) and returns `agg_state` without `_update_agg_state()` (empty
dict → callers checking `result['failed']` break; `onfail='kill'` skipped).
**Fix:** `_update_agg_state()` before returning; prompt only when
`sys.stdin.isatty()`, defaulting to "don't kill". Fix the prompt typo
("do you to kill the procs?").

### 5.1.5 [LOW] Unknown job state optimistically reported COMPLETED
`slurm.py:1099`. `_sacct_job_state(job_id) or 'COMPLETED'` marks jobs with no
accounting info as passed (e.g. bogus ids from a failed sbatch, see 5.3.1).
**Fix:** introduce a distinct terminal `'lost'` status counted separately
(still terminal for the finish check).

## 5.2 sbatch flag construction

### 5.2.1 [HIGH] `mem_per_cpu`/`container` misclassified as boolean flags
`slurm.py:219` (`mem_per_cpu` in `SLURM_SBATCH_FLAGS` while also in KVARGS at
`:182`) and `:206` (`container` in FLAGS only, though it takes a value).
`mem_per_cpu='4G'` renders `--mem-per-cpu="4G" --mem-per-cpu` (sbatch: option
requires an argument); `container='/img.sqfs'` renders bare `--container`,
silently discarding the path. **Fix:** remove `mem_per_cpu` from FLAGS; move
`container` to KVARGS. Then audit the whole FLAGS/KVARGS split against
`sbatch --help` (the lists were regex-generated; check for other misfilings).
**Test:** text-level render assertions for both kwargs.

### 5.2.2 [MEDIUM] Queue-level boolean flags silently dropped
`slurm.py:751`. `submit` merges `_kwargs = self._sbatch_kvargs | kwargs`;
`self._sbatch_flags` (captured at `:583-584`) is never used, so
`SlurmQueue('t', requeue=True)` is a silent no-op.
**Fix:** `_kwargs = self._sbatch_kvargs | self._sbatch_flags | kwargs`.
**Test:** queue-level `requeue=True` appears as `--requeue` in every job line.

### 5.2.3 [LOW] Typo'd kwargs silently swallowed
`slurm.py:285, 566`. Unrecognized kwargs land in `unused_kwargs` without a
whisper (`partion='gpu'` drops the resource request). **Fix:** warn (or raise)
when `unused_kwargs` is non-empty.

## 5.3 Submission / DAG integrity

### 5.3.1 [HIGH] Failed sbatch produces invalid jobids JSON → JSONDecodeError
`slurm.py:816-822` (unquoted `%s` in the jobids JSON printf) and `:1049-1066`
(only `UnableToMonitor` caught around `json.loads`). The generated script has no
`set -e`; a failed sbatch leaves `JOB_nnn` empty →
`printf '{"JOB_000": %s}' ""` writes `{"JOB_000": }` (invalid JSON); the script
still exits 0 (last printf succeeds) so `check=True` passes, then the monitor
raises `JSONDecodeError` instead of reporting the submission failure. With
`--clusters`, `sbatch --parsable` prints `jobid;cluster` — invalid both as JSON
and inside `--dependency=afterok:${JOB_nnn}`.
**Fix:** quote values in the printf (`'"%s"'`); post-parse, treat empty or
non-numeric ids as submission failures with a clear error; strip `;cluster`
suffixes both in the JSON and before interpolating into `--dependency`.
**Test:** simulate a jobids file with an empty value; monitor reports a
submission failure instead of raising JSONDecodeError.

### 5.3.2 [HIGH] Duplicate job names accepted → dependencies wired to wrong job
`slurm.py:694-756` (no duplicate check; base class has one at
base_queue.py:262) and `:804-806` (`jobname_to_varname[name]` overwritten).
Two jobs named `dup` → string deps resolve to the second; even SlurmJob-object
deps on the first resolve to the second job's id. Wrong DAG, no error.
**Fix:** replicate the base-class duplicate check in `SlurmQueue.submit` (or
better: refactor so `SlurmQueue.submit` calls shared base logic — coordinate
with Phase 3.2.1's ordering fix). **Test:** duplicate submit raises
`DuplicateJobError`.

### 5.3.3 [MEDIUM] `exclude_tags` + dependent job → invalid/hijackable dependency
`slurm.py:426` (fallback `$(squeue --noheader --format %i --name '<name>')`)
with `:795-806` (excluded jobs get no varname). A dep on an excluded job renders
the squeue-by-name fallback; the job was never submitted, so it expands empty →
`sbatch: error: Job dependency problem`; the dependent and everything downstream
never submit. Worse: if ANY cluster user has a job with that name, the
dependency silently attaches to a stranger's job; multi-line output from
several same-name jobs also breaks the flag.
**Fix:** at `finalize_text` time, drop dependencies on excluded jobs with a
warning (matching serial/tmux semantics of "excluded means treat as satisfied")
or fail fast; if keeping the runtime fallback for cross-queue deps, add
`--user=$USER`, take the last line only, and guard empty expansion in bash.
**Test:** text-level — excluded dep produces no `--dependency` (or a guarded
form), and a warning is emitted.

## 5.4 Availability probe

### [MEDIUM] `is_available` can raise UnboundLocalError; dead branch
`slurm.py:663-679`. Within the `>= 21` path the `else: scontrol show nodes
--json` branch is unreachable, and JSON with neither `'nodes'` nor `'sinfo'`
keys leaves `nodes` unbound → availability *probe* crashes `run()` instead of
returning False. sinfo's JSON shape demonstrably changed across v21/22/23.
**Fix:** `nodes = out.get('nodes') or [i['node'] for i in out.get('sinfo', [])]`;
wrap the whole probe in try/except returning False; delete the dead branch;
also guard the `sinfo --version` parse (`:652-654`).
**Test:** feed the parser both known JSON shapes and a bogus shape.

## 5.5 slurmify CLI (`cmd_queue/slurmify.py`) — broken out of the box

1. **[HIGH] `partition` default is `1`** (`slurmify.py:62`) → every no-arg run
   submits `--partition="1"` → `sbatch: error: invalid partition`. Fix: default
   `None`.
2. **[HIGH] `--depends` always raises KeyError** (`slurmify.py:97,129-130` with
   `slurm.py:746-749`): names are resolved via the fresh queue's `named_jobs`,
   which is empty; even the docstring's own `--depends=None` csv-parses to
   `['None']` and crashes. Fix: accept numeric job ids passed through as
   `--dependency=afterok:<id>`, and/or translate names via a guarded
   squeue-by-name (`--user=$USER`); error clearly otherwise. Fix the docstring
   example.
3. **[MEDIUM] `--gpus=1` requests zero GPUs**: `parser='csv'` yields a list;
   `_coerce_gres` (`slurm.py:386-387`) maps any list to `'gpu:0'`. Fix: parse
   as int / map 1-element lists to `gpu:<n>`; also fix the help strings that say
   "tmux backend only" in a slurm-only tool.
4. **[MEDIUM] single-token command double-quoted** (`slurmify.py:114-121`):
   same class as main.py's hack (Phase 2.2.7) — a 1-element command is already a
   complete command line; pass through unmodified.
5. **[LOW] `command=None`** (no positional) flows into `queue.submit(None)` and
   fails opaquely later — validate up front.
6. Add `tests/test_slurmify.py` covering all of the above at the
   rendered-text level (no cluster needed: build the queue, inspect
   `finalize_text()`).

## 5.6 Smaller items (fold into the above commits where convenient)

- `kill()` cancels by `--name` only (`slurm.py:1306-1311`) — user-supplied
  names collide across queues/users; prefer `scancel <jobid>` from the jobids
  JSON, falling back to `--name` + `--user=$USER`.
- Job stdout written with `.sh` extension (`slurm.py:728`) — use `.log`/`.out`.
- `parse_scontrol_output` (`slurm.py:1401-1438`): example is not a doctest
  (no `>>>`) so never runs; the first-special-key regex mis-splits lines like
  `Partition=priority AllocNode:Sid=...`. Convert to a real doctest; match the
  last special key per line.
- Queue `name` validation + `run()`'s unquoted `ub.cmd(f'bash {self.fpath}')`
  — covered by Phase 2; verify here for slurm specifically.

## Verification

- `tests/test_slurm_variants.py` + new text-level tests green without a cluster.
- If feasible, spin up the `dev/slurm` test cluster and run
  `tests/test_backend_execution.py` + `examples/slurm_example.py` end-to-end;
  verify the monitor survives a pending job with a multi-word reason (submit
  more jobs than the toy cluster has nodes to force `(Resources)`/priority
  reasons).
- Full suite + doctests + ruff + ty green.
