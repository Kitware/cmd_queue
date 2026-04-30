# test_slurm_preamble_insertion.py
import shlex
from cmd_queue.slurm_queue import SlurmQueue, SlurmJob


def _extract_wrap_payload(sbatch_args):
    """
    Given the list returned by SlurmJob._build_sbatch_args(...),
    extract the string passed to --wrap and unquote it.
    """
    # sbatch_args contains an entry like: '--wrap \'<payload>\''
    wrap_items = [item for item in sbatch_args if item.startswith('--wrap ')]
    assert len(wrap_items) == 1, (
        f'Expected exactly one --wrap item, got: {wrap_items}'
    )
    wrap_item = wrap_items[0]

    # split once: "--wrap <quoted payload>"
    _, quoted_payload = wrap_item.split(' ', 1)

    # The payload is shlex.quote(...)'d in the implementation
    payload = shlex.split(quoted_payload)[0]
    return payload


def test_slurm_wrap_contains_global_then_job_preamble_then_command():
    # Global preamble: specified on the queue
    global_preamble = ['echo GLOBAL1', 'echo GLOBAL2']

    # Job preamble: specified per submit
    job_preamble = 'echo JOB1'

    command = 'echo RUN'

    queue = SlurmQueue(preamble=global_preamble)

    job = queue.submit(command, preamble=job_preamble)
    assert isinstance(job, SlurmJob)

    # Directly build sbatch args the same way SlurmQueue does
    sbatch_args = job._build_sbatch_args(global_preamble=queue.header_commands)
    print(f'sbatch_args={sbatch_args}')

    payload = _extract_wrap_payload(sbatch_args)

    # The payload should be a single shell line with && joining
    expected = ' && '.join(global_preamble + [job_preamble, command])

    # Exact match is reasonable here because payload construction is deterministic
    assert payload == expected, f'\nExpected:\n{expected}\nGot:\n{payload}'


def test_slurm_wrap_omits_missing_preambles():
    # No global preamble, no job preamble
    queue = SlurmQueue(preamble=None)
    job = queue.submit('echo ONLYCMD', preamble=None)

    sbatch_args = job._build_sbatch_args(global_preamble=queue.header_commands)
    payload = _extract_wrap_payload(sbatch_args)
    assert payload == 'echo ONLYCMD'

    # Global preamble only
    queue = SlurmQueue(preamble=['echo GLOBAL'])
    job = queue.submit('echo CMD', preamble=None)
    sbatch_args = job._build_sbatch_args(global_preamble=queue.header_commands)
    payload = _extract_wrap_payload(sbatch_args)
    assert payload == 'echo GLOBAL && echo CMD'

    # Job preamble only
    queue = SlurmQueue(preamble=None)
    job = queue.submit('echo CMD', preamble='echo JOB')
    sbatch_args = job._build_sbatch_args(global_preamble=queue.header_commands)
    payload = _extract_wrap_payload(sbatch_args)
    assert payload == 'echo JOB && echo CMD'
