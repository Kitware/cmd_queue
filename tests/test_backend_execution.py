"""
End-to-end execution tests that actually **run** a queue on each backend and
verify that jobs -- and their ``setup`` / ``teardown`` lifecycle -- executed.

Unlike the render-only tests (which only build the bash/sbatch text), these
submit and run a real queue:

* ``serial`` always runs (no external dependencies).
* ``tmux`` and ``slurm`` are skipped unless the backend reports itself
  available via ``is_available()``. So on a machine with a working slurm
  install these exercise real ``sbatch`` submission; elsewhere they skip
  cleanly.

Each job (and its setup/teardown) writes a marker file, so execution is
verified by the side effects on disk -- a backend-agnostic check.

Working directories use :func:`ubelt.Path.appdir` (under the user's home)
rather than pytest's ``tmp_path``: for slurm the job body runs on a compute
node, and the marker files must land somewhere the submitting process can
read them back. ``$HOME`` is shared across nodes on a typical cluster,
whereas ``/tmp`` is often node-local.
"""
from __future__ import annotations

import pytest
import ubelt as ub

import cmd_queue

# Computed once: which backends can actually run on this machine.
_AVAILABLE = set(cmd_queue.Queue.available_backends())


def _work_dpath(slug: str) -> ub.Path:
    """A clean, shared-filesystem working directory for one test."""
    dpath = ub.Path.appdir('cmd_queue/tests/backend_execution') / slug
    dpath.delete().ensuredir()
    return dpath


def _backend_param(name: str):
    return pytest.param(
        name,
        marks=pytest.mark.skipif(
            name not in _AVAILABLE,
            reason=f'{name} backend is not available on this machine',
        ),
    )


BACKENDS = [
    _backend_param('serial'),
    _backend_param('tmux'),
    _backend_param('slurm'),
]


def _make_queue(backend: str, name: str, dpath: ub.Path):
    """Construct a queue with the per-backend kwargs each one expects."""
    kwargs: dict = {'backend': backend, 'name': name}
    if backend in {'serial', 'tmux'}:
        kwargs['dpath'] = dpath
        kwargs['rootid'] = 'test'
    if backend == 'tmux':
        kwargs['size'] = 1
    return cmd_queue.Queue.create(**kwargs)


def _run_blocking(queue, backend: str) -> None:
    """Run the queue and block until every job reaches a terminal state.

    The blocking mechanism differs per backend:
    * serial runs the script in the foreground (inherently blocking);
    * tmux blocks via a headless state-file poll (``monitor='none'``);
    * slurm blocks by polling ``scontrol`` in the inline monitor.
    """
    try:
        if backend == 'tmux':
            queue.run(
                block=True,
                monitor='none',
                with_textual=False,
                onfail='',
                other_session_handler='ignore',
            )
        elif backend == 'slurm':
            queue.run(block=True, monitor='inline', onfail='')
        else:
            queue.run(block=True, verbose=0)
    finally:
        # Best-effort cleanup so a failure never leaves tmux sessions or
        # queued slurm jobs lingering for the next test.
        kill = getattr(queue, 'kill', None)
        if callable(kill):
            try:
                kill()
            except Exception:
                pass


@pytest.mark.parametrize('backend', BACKENDS)
def test_backend_executes_simple_dag(backend):
    """A two-job dependent DAG runs to completion and produces its output."""
    dpath = _work_dpath(f'simple-{backend}')
    queue = _make_queue(backend, 'cmdq-exec-simple', dpath / 'qdir')

    out1 = dpath / 'job1.out'
    out2 = dpath / 'job2.out'
    job1 = queue.submit(f'echo hi > "{out1}"', name='job1')
    queue.submit(f'echo done > "{out2}"', name='job2', depends=[job1])

    _run_blocking(queue, backend)

    assert out1.exists(), 'first job did not run'
    assert out2.exists(), 'dependent job did not run'
    assert out1.read_text().strip() == 'hi'
    assert out2.read_text().strip() == 'done'


@pytest.mark.parametrize('backend', BACKENDS)
def test_backend_executes_setup_teardown(backend):
    """setup runs before the command and teardown runs after it (success)."""
    dpath = _work_dpath(f'setup-teardown-{backend}')
    queue = _make_queue(backend, 'cmdq-exec-st', dpath / 'qdir')

    setup_marker = dpath / 'setup.marker'
    cmd_marker = dpath / 'cmd.marker'
    teardown_marker = dpath / 'teardown.marker'

    queue.submit(
        f'echo cmd > "{cmd_marker}"',
        name='bracketed',
        setup=f'echo s > "{setup_marker}"',
        teardown=f'echo t > "{teardown_marker}"',
    )

    _run_blocking(queue, backend)

    assert setup_marker.exists(), 'setup should run before the command'
    assert cmd_marker.exists(), 'command should run after a successful setup'
    assert teardown_marker.exists(), 'teardown should run after the command'


@pytest.mark.parametrize('backend', BACKENDS)
def test_backend_setup_failure_fails_job_and_skips_command(backend):
    """A failing setup marks the job failed and gates the command (skipped)
    and teardown (not run).

    setup is the resource acquisition: if it fails the resource was never
    acquired, so the job fails and neither the command nor the release
    (teardown) should run.
    """
    dpath = _work_dpath(f'setup-fail-{backend}')
    queue = _make_queue(backend, 'cmdq-exec-stfail', dpath / 'qdir')

    cmd_marker = dpath / 'cmd.marker'
    teardown_marker = dpath / 'teardown.marker'

    job = queue.submit(
        f'echo cmd > "{cmd_marker}"',
        name='bracketed',
        setup='false',  # gating precondition fails
        teardown=f'echo t > "{teardown_marker}"',
    )

    _run_blocking(queue, backend)

    assert not cmd_marker.exists(), 'command must be skipped when setup fails'
    assert not teardown_marker.exists(), (
        'teardown must not run when setup never succeeded'
    )
    # The failing setup must mark the job failed (not passed). serial/tmux
    # record this in on-disk pass/fail markers; slurm tracks job state through
    # the scheduler (no marker), and its "setup failure exits non-zero" is
    # covered by test_slurm_variants.py.
    if backend != 'slurm':
        assert job.fail_fpath.exists(), 'a failing setup must fail the job'
        assert not job.pass_fpath.exists(), 'a failed job must not pass'
