"""Tests for the Airflow backend without pytest fixtures."""

import ubelt as ub
import pytest

from cmd_queue.airflow_queue import AirflowQueue


airflow = pytest.importorskip('airflow')


def _test_dpath(name: str) -> ub.Path:
    """Create a reproducible test directory under the repo appdir."""
    dpath = ub.Path.appdir(f'cmd_queue/tests/{name}').delete().ensuredir()
    return dpath


def _make_queue(name='cmdq_airflow_demo'):
    dpath = _test_dpath(name)
    airflow_home = dpath / 'airflow_home'
    return AirflowQueue(
        name=name, dpath=dpath / 'queue_root', airflow_home=airflow_home
    )


def test_finalize_text_contains_dependencies():
    queue = _make_queue(name='finalize_demo')
    first = queue.submit('echo first', name='first_task')
    queue.submit('echo second', name='second_task', depends=first)

    text = queue.finalize_text()
    assert 'dag = DAG(' in text
    assert "'finalize_demo'" in text
    assert "jobs['first_task']" in text
    assert "jobs['second_task']" in text
    assert "jobs['second_task'].set_upstream(jobs['first_task'])" in text


def test_airflow_queue_run_executes_in_order():
    queue = _make_queue(name='run_demo')
    outfile = queue.dpath / 'output.txt'
    queue.submit(f'echo first >> {outfile}', name='first')
    queue.submit(f'echo second >> {outfile}', name='second', depends='first')

    queue.run()

    contents = outfile.read_text().strip().splitlines()
    assert contents == ['first', 'second']
