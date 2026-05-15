"""Generated text compatibility smoke tests.

These tests lock stable invariants instead of every byte of generated text.
They make internal refactors safer without over-constraining intentional
formatting improvements in later PRs.
"""


def test_serial_generated_text_invariants(tmp_path):
    from cmd_queue import Queue

    queue = Queue.create(
        backend='serial', name='compat_serial', rootid='root', dpath=tmp_path
    )
    queue.add_preamble_command('export COMPAT_FLAG=1')
    first = queue.submit('echo first', name='first')
    queue.submit('echo second', name='second', depends=first)

    text = queue.finalize_text(with_status=False, with_gaurds=False)
    assert text.index('export COMPAT_FLAG=1') < text.index('echo first')
    assert text.index('echo first') < text.index('echo second')
    assert '# Written by cmd_queue' in text


def test_tmux_generated_text_invariants(tmp_path):
    from cmd_queue import Queue

    queue = Queue.create(
        backend='tmux', name='compat_tmux', rootid='root', dpath=tmp_path, size=1
    )
    first = queue.submit('echo first', name='first')
    queue.submit('echo second', name='second', depends=first)

    text = queue.finalize_text(with_status=False, with_gaurds=False, with_locks=False)
    worker_text = '\n'.join(
        worker.finalize_text(with_status=False, with_gaurds=False)
        for worker in queue.workers
    )
    assert 'tmux new-session' in text
    assert 'source ' in text
    assert 'echo first' in worker_text
    assert 'echo second' in worker_text


def test_slurm_generated_text_invariants():
    from cmd_queue import Queue

    queue = Queue.create(backend='slurm', name='compat_slurm')
    first = queue.submit('echo first', name='first')
    queue.submit('echo second', name='second', depends=first)

    text = queue.finalize_text()
    assert 'sbatch' in text
    assert '--job-name="first"' in text
    assert '--job-name="second"' in text
    assert '--dependency=afterok:${JOB_000}' in text


def test_airflow_generated_text_invariants(tmp_path):
    from cmd_queue import Queue

    queue = Queue.create(
        backend='airflow', name='compat_airflow', dpath=tmp_path / 'airflow'
    )
    first = queue.submit('echo first', name='first')
    queue.submit('echo second', name='second', depends=first)

    text = queue.finalize_text()
    assert 'from airflow import DAG' in text
    assert "jobs['first']" in text
    assert "jobs['second']" in text
    assert "jobs['second'].set_upstream(jobs['first'])" in text
