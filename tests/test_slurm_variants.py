# test_slurm_preamble_insertion.py
import shlex

from cmd_queue.slurm_queue import SlurmJob, SlurmQueue


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


def test_slurm_setup_folds_into_preamble_gate():
    # ``setup`` is a gating precondition: it is folded into the preamble so the
    # ``&&`` chain short-circuits the command if setup fails. With no teardown
    # the command is not wrapped.
    queue = SlurmQueue(preamble=None)
    job = queue.submit('echo CMD', setup='acquire_lease')
    sbatch_args = job._build_sbatch_args(global_preamble=queue.header_commands)
    payload = _extract_wrap_payload(sbatch_args)
    assert payload == 'acquire_lease && echo CMD'

    # setup composes after an existing preamble (global then job then setup)
    queue = SlurmQueue(preamble=['echo GLOBAL'])
    job = queue.submit('echo CMD', preamble='echo JOB', setup='acquire_lease')
    sbatch_args = job._build_sbatch_args(global_preamble=queue.header_commands)
    payload = _extract_wrap_payload(sbatch_args)
    assert payload == 'echo GLOBAL && echo JOB && acquire_lease && echo CMD'


def test_slurm_teardown_wraps_command_with_trap():
    # ``teardown`` co-locates a signal-safe cleanup trap with the command. slurm
    # runs one process per job, so the trap lives directly in ``--wrap``.
    queue = SlurmQueue(preamble=None)
    job = queue.submit('echo CMD', teardown='release_lease')
    sbatch_args = job._build_sbatch_args(global_preamble=queue.header_commands)
    payload = _extract_wrap_payload(sbatch_args)

    # The command is wrapped in a brace group that installs the trap.
    assert '__cmdq_teardown() { release_lease ; }' in payload
    assert 'trap __cmdq_teardown EXIT' in payload
    assert "trap 'exit 143' TERM" in payload
    assert "trap 'exit 130' INT" in payload
    # The actual command runs inside the trapped group.
    assert 'echo CMD' in payload


def test_slurm_setup_gates_teardown():
    # ``setup && { trap...; command; }``: when setup fails the whole group
    # (which installs the trap) never runs, so nothing is torn down.
    queue = SlurmQueue(preamble=None)
    job = queue.submit('echo CMD', setup='acquire_lease', teardown='release_lease')
    sbatch_args = job._build_sbatch_args(global_preamble=queue.header_commands)
    payload = _extract_wrap_payload(sbatch_args)

    # setup precedes the trapped group via ``&&`` so it gates teardown.
    assert payload.startswith('acquire_lease && {')
    assert 'trap __cmdq_teardown EXIT' in payload


def test_slurm_teardown_executes_as_documented():
    # Execute the rendered wrap payload to confirm the runtime contract:
    # the command's exit code stays authoritative and teardown always runs.
    import subprocess
    queue = SlurmQueue(preamble=None)

    # command fails -> exit code preserved, teardown still runs
    job = queue.submit('echo CMD; exit 5', name='a',
                       setup='echo SETUP', teardown='echo TD')
    payload = _extract_wrap_payload(
        job._build_sbatch_args(global_preamble=queue.header_commands))
    r = subprocess.run(['bash', '-c', payload], capture_output=True, text=True)
    assert r.returncode == 5, 'command exit code stays authoritative'
    assert 'TD' in r.stdout, 'teardown runs even when command fails'

    # teardown fails -> does not flip a passing command
    job = queue.submit('echo CMD', name='b',
                       setup='echo SETUP', teardown='echo TD; false')
    payload = _extract_wrap_payload(
        job._build_sbatch_args(global_preamble=queue.header_commands))
    r = subprocess.run(['bash', '-c', payload], capture_output=True, text=True)
    assert r.returncode == 0, 'teardown failure must not flip the result'
    assert 'TD' in r.stdout

    # setup fails -> command skipped, teardown not run
    job = queue.submit('echo CMD', name='c',
                       setup='false', teardown='echo TD')
    payload = _extract_wrap_payload(
        job._build_sbatch_args(global_preamble=queue.header_commands))
    r = subprocess.run(['bash', '-c', payload], capture_output=True, text=True)
    assert r.returncode != 0, 'setup failure fails the job'
    assert 'CMD' not in r.stdout, 'command should not run if setup fails'
    assert 'TD' not in r.stdout, 'teardown should not run if setup fails'
