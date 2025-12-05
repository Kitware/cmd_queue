"""Tests for the Airflow backend."""

import pytest

from cmd_queue.airflow_queue import AirflowQueue


airflow = pytest.importorskip('airflow')


def _make_queue(tmp_path, name='cmdq_airflow_demo'):
    airflow_home = tmp_path / 'airflow_home'
    return AirflowQueue(name=name, dpath=tmp_path / 'queue_root', airflow_home=airflow_home)


def test_finalize_text_contains_dependencies(tmp_path):
    queue = _make_queue(tmp_path, name='finalize_demo')
    first = queue.submit('echo first', name='first_task')
    queue.submit('echo second', name='second_task', depends=first)

    text = queue.finalize_text()
    assert "dag = DAG(" in text
    assert "'finalize_demo'" in text
    assert "jobs['first_task']" in text
    assert "jobs['second_task']" in text
    assert "jobs['second_task'].set_upstream(jobs['first_task'])" in text


def test_airflow_queue_run_executes_in_order(tmp_path):
    queue = _make_queue(tmp_path, name='run_demo')
    outfile = tmp_path / 'output.txt'
    queue.submit(f"echo first >> {outfile}", name='first')
    queue.submit(f"echo second >> {outfile}", name='second', depends='first')

    queue.run()

    contents = outfile.read_text().strip().splitlines()
    assert contents == ['first', 'second']

