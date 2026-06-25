"""Render-only backend contract tests.

The tests avoid executing tmux, Slurm, or Airflow.  They lock the public backend
surface while internals are gradually moved into smaller helpers.
"""

import pytest


@pytest.mark.parametrize('backend', ['serial', 'tmux', 'slurm', 'airflow'])
def test_backend_classes_support_minimal_contract(backend, tmp_path):
    from cmd_queue import Queue

    kwargs = {'backend': backend, 'name': f'contract_{backend}'}
    if backend in {'serial', 'tmux', 'airflow'}:
        kwargs['dpath'] = tmp_path / backend
    if backend == 'serial':
        kwargs['rootid'] = 'root'
    if backend == 'tmux':
        kwargs['rootid'] = 'root'
        kwargs['size'] = 1

    queue = Queue.create(**kwargs)
    assert hasattr(queue, 'submit')
    assert hasattr(queue, 'finalize_text')
    assert hasattr(queue, 'print_commands')
    assert hasattr(queue, 'read_state')
    assert isinstance(queue.is_available(), bool)

    first = queue.submit('echo first', name='first')
    second = queue.submit('echo second', name='second', depends=first)
    text = queue.finalize_text()
    combined_text = text
    if backend == 'tmux':
        # ``TMUXMultiQueue.finalize_text`` returns the driver script.  The
        # per-worker scripts contain the actual job commands. ``workers`` is a
        # tmux-only attribute, so narrow the base ``Queue`` to the concrete type.
        from typing import cast
        from cmd_queue.backends.tmux import TMUXMultiQueue
        tmux_queue = cast(TMUXMultiQueue, queue)
        combined_text += '\n'.join(
            worker.finalize_text() for worker in tmux_queue.workers
        )

    assert isinstance(text, str)
    assert 'echo first' in combined_text
    assert 'echo second' in combined_text
    assert second.depends == [first]


@pytest.mark.parametrize('backend', ['serial', 'tmux', 'slurm', 'airflow'])
def test_dependency_graph_edges_are_backend_independent(backend, tmp_path):
    from cmd_queue import Queue

    kwargs = {'backend': backend, 'name': f'graph_{backend}'}
    if backend in {'serial', 'tmux', 'airflow'}:
        kwargs['dpath'] = tmp_path / backend
    if backend == 'serial':
        kwargs['rootid'] = 'root'
    if backend == 'tmux':
        kwargs['rootid'] = 'root'
        kwargs['size'] = 1

    queue = Queue.create(**kwargs)
    queue.submit('echo first', name='first')
    queue.submit('echo second', name='second', depends='first')
    queue.sync()
    queue.submit('echo third', name='third')

    graph = queue._dependency_graph()
    assert list(graph.edges()) == [('first', 'second'), ('second', 'third')]
