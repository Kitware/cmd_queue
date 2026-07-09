# Phase 7: Test suite strengthening

**Goal:** Close the gaps that let the Phase 2-6 bugs survive: assertion-free
tests, uncollected files, untested modules, and shared-state hazards.

**Prerequisites:** Phases 2-6 each added targeted regression tests; this phase
is the systematic sweep. Current baseline: 82 tests collect; 76 pass / 7 skip
locally in ~11s. The newer suites (`test_bash_variants`, `test_slurm_variants`,
`test_backend_execution`, `test_block_timeout`, `test_tmux_attach`) are strong —
behavioral, regression-documented, properly skip-gated. Match their style.

## 7.1 Fix tests that cannot fail

- `tests/tests_mixed_hardware_tmux.py` — **never collected** (pytest's default
  pattern is `test_*.py`, this is `tests_*.py`), and even if renamed it has
  zero assertions (only `print_commands()`/`print_graph()`). Rename to
  `test_mixed_hardware_tmux.py` and assert something real: e.g. the rendered
  worker scripts split `CUDA_VISIBLE_DEVICES` assignments across the two
  `gres` entries. Or delete it if redundant with `test_backend_execution`.
- `tests/test_errors.py::test_failures_on_each_backend` — submits jobs named
  "job2 never runs" etc., then only calls `run()` and discards `read_state()`.
  Assert on `read_state()`: expected failed/skipped/passed counts per backend —
  this is the test that should have caught the tee/pipefail bug (Phase 3.1.1).
- `tests/test_package_metadata.py` — unconditionally `@pytest.mark.skip` with a
  `pass` body; inflates counts, tests nothing. Delete it (move its docstring
  rationale to a comment elsewhere if worth keeping).

## 7.2 Add unit tests for untested modules

No direct tests exist anywhere for (line counts as of `0635f9c`):

| Module | Priority | What to cover |
|---|---|---|
| `util/util_yaml.py` (443) | high | `Yaml.coerce/loads/dumps` round-trips, `!include` (no debug prints — regression for Phase 3.3.2), pyyaml-vs-ruamel backends |
| `slurmify.py` (149) | high | Phase 5.5 items — rendered-text level |
| `monitor_manifest.py` (131) | high | resolve by name/path, stray-file shadowing (Phase 6.6), stale-manifest handling |
| `util/util_bash.py` (48) | high | `bash_json_dump` output parses as JSON incl. quoting edge cases (Phase 2.2.4) |
| `util/richer.py` / `util/texter.py` | medium | one test that every name in `__all__` is importable — this alone would have caught both current bugs (see 7.5) |
| `cli_boilerplate.py` (602) | medium | deprecated but shipped: one smoke per config class through `create_queue`/`run_queue` with `--run=0` |
| `util/util_algo.py`, `util/util_tags.py`, `util/util_networkx.py` | low | doctest coverage may suffice — ensure doctests actually run in CI (they run via the xdoctest lane over the installed module; verify these modules are included) |
| `monitor_app.py` | medium | textual `run_test` coverage added in Phase 6.2 |

## 7.3 Backend-contract suite

`tests/test_backend_contract.py` exists — extend it so every registered backend
is checked for:

- `run(**kw)` accepts the boilerplate kwargs (`with_textual`,
  `other_session_handler`, `monitor`, `block`, `onfail`, `onexit`) — catches
  Phase 6.3's airflow TypeError class permanently.
- `submit` rejects duplicate names (catches Phase 5.3.2's SlurmQueue bypass).
- `run()`/`monitor()` return shapes agree with annotations (tmux's currently
  lie — Phase 9 fixes the annotations; the contract test keeps them honest).
- `read_state()` returns the agreed keys (`passed/failed/skipped/total`...)
  for a trivially passing and a trivially failing queue (serial always;
  tmux/slurm skip-gated).

## 7.4 Test isolation

- Add `tests/conftest.py`. `tests/test_cli.py:8` reuses a shared
  `ub.Path.appdir('cmd_queue/tests/tests_cli')` and fixed queue names
  `testqueue1/2` — collides under `pytest -n` or two concurrent checkouts.
  Move CLI tests to `tmp_path` (point the CLI's queue dir there via its env
  var/config knob; add one if none exists — check `cli_queue_fpath`).
  `test_backend_execution.py` may keep appdir (documented reason: slurm needs a
  shared filesystem) — leave it.
- Known timing-sensitive spots (acceptable, just don't regress):
  `test_backend_execution.py:193-201` (`dt >= 2.5` around a `sleep 3`
  slurm job); `test_bash_variants.py:705` (1s sleep before SIGTERM, mitigated
  by a marker-poll loop).

## 7.5 Two concrete util bugs to fix alongside their new tests

- `util/richer.py:125-194` — `__all__` advertises `get_console`, `inspect`,
  `print`, `reconfigure`, but `lazy_import` was generated with
  `submod_attrs={}`, so those four raise AttributeError/ImportError (verified);
  `from cmd_queue.util.richer import *` crashes. Regenerate with mkinit adding
  the attrs, or drop them from `__all__`.
- `util/texter.py` — mirrors a ~2021 textual API (`background`, `layout_map`,
  `page`, `view`, ... submodules) that does not exist in the required
  `textual>=4.0.0`; `EAGER_IMPORT=1` makes importing it crash; nothing in the
  package imports it. **Delete the module** (and its docs page) — preferred —
  or regenerate against textual 4.x.
- Also from the same audit: `util/__init__.py:45-57` lazy-exports only
  `util_algo`/`util_networkx`; attribute access to `cmd_queue.util.util_yaml`
  etc. raises AttributeError. Regenerate the mkinit block to list all
  submodules. `util_yaml.py:83`: restore the commented-out `@ub.memoize` on
  `_custom_new_ruaml_yaml_obj` (every dumps/loads currently rebuilds classes
  and re-registers representers). `util_yaml.py:267`: pyyaml backend uses
  full `yaml.Loader` on user-supplied config strings — switch to `SafeLoader`
  unless arbitrary-object loading is a documented feature.
- `util_tmux.py:35-36`: `resolve_block_timeout(explicit='none')` raises
  `ValueError` while the env-var path accepts `'none'` — accept it in both.

## Verification

- `python3 -m pytest tests/ -q` — every test file collects (no `tests_*.py`
  strays), no unconditional skips remain, count meaningfully higher than the
  82 baseline.
- `python3 -m pytest tests/ -n 4` (pytest-xdist, add to test requirements if
  absent) passes — proves the isolation work.
- Coverage: `python3 run_tests.py`; target: every module in the 7.2 table has
  >0% direct coverage; note overall % in the phase-completion commit message.
