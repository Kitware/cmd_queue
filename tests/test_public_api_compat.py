"""Compatibility tests for public import paths and backend creation."""

import pytest


def test_public_import_paths_are_stable():
    import cmd_queue
    from cmd_queue import Job, Queue
    from cmd_queue.airflow_queue import AirflowJob, AirflowQueue
    from cmd_queue.base_queue import DuplicateJobError, UnknownBackendError
    from cmd_queue.serial_queue import BashJob, SerialQueue
    from cmd_queue.slurm_queue import SlurmJob, SlurmQueue
    from cmd_queue.tmux_queue import TMUXMultiQueue

    assert cmd_queue.Job is Job
    assert cmd_queue.Queue is Queue
    assert issubclass(BashJob, Job)
    assert issubclass(SlurmJob, Job)
    assert issubclass(AirflowJob, Job)
    assert issubclass(SerialQueue, Queue)
    assert issubclass(TMUXMultiQueue, Queue)
    assert issubclass(SlurmQueue, Queue)
    assert issubclass(AirflowQueue, Queue)
    assert issubclass(DuplicateJobError, KeyError)
    assert issubclass(UnknownBackendError, KeyError)


def test_backend_registry_preserves_names_and_order():
    from cmd_queue import Queue

    assert list(Queue._backend_classes()) == [
        'serial',
        'tmux',
        'slurm',
        'airflow',
    ]


def test_create_preserves_size_argument_compatibility(tmp_path):
    from cmd_queue import Queue
    from cmd_queue.airflow_queue import AirflowQueue
    from cmd_queue.base_queue import UnknownBackendError
    from cmd_queue.serial_queue import SerialQueue
    from cmd_queue.slurm_queue import SlurmQueue
    from cmd_queue.tmux_queue import TMUXMultiQueue

    serial = Queue.create(
        backend='serial', size=999, name='compat_serial', dpath=tmp_path / 'serial'
    )
    tmux = Queue.create(
        backend='tmux', size=1, name='compat_tmux', dpath=tmp_path / 'tmux'
    )
    slurm = Queue.create(backend='slurm', size=999, name='compat_slurm')
    airflow = Queue.create(
        backend='airflow',
        size=999,
        name='compat_airflow',
        dpath=tmp_path / 'airflow',
    )

    assert isinstance(serial, SerialQueue)
    assert isinstance(tmux, TMUXMultiQueue)
    assert isinstance(slurm, SlurmQueue)
    assert isinstance(airflow, AirflowQueue)

    with pytest.raises(UnknownBackendError):
        Queue.create(backend='does-not-exist')


def test_submit_dependency_compatibility(tmp_path):
    from cmd_queue import Queue
    from cmd_queue.base_queue import DuplicateJobError

    queue = Queue.create(
        backend='serial', name='compat_deps', rootid='compat', dpath=tmp_path
    )
    first = queue.submit('echo first', name='first')
    second = queue.submit('echo second', name='second', depends='first')
    queue.sync()
    third = queue.submit('echo third', name='third')

    assert second.depends == [first]
    assert third.depends == [second]

    graph = queue._dependency_graph()
    assert list(graph.edges()) == [('first', 'second'), ('second', 'third')]

    with pytest.raises(DuplicateJobError):
        queue.submit('echo duplicate', name='first')
