r"""
Simplify chaining of multiple shell commands


Serves as a frontend for several DAG backends, including our own custom tmux
queue. We also support slurm and will soon support airflow.

Example:
    >>> # The available backends classmethod lets you know which backends
    >>> # your system has access to. The "serial" backend should always be
    >>> # available. Everthing else requires some degree of setup (tmux
    >>> # is the easiest, just install it, no configuration needed).
    >>> import cmd_queue
    >>> print(cmd_queue.Queue.available_backends())  # xdoctest: +IGNORE_WANT
    ['serial', 'tmux', 'slurm']

Example:
    >>> # The API to submit jobs is the same regardless of the backend.
    >>> # Job dependencies can be specified by name, or by the returned
    >>> # job objects.
    >>> import cmd_queue
    >>> queue = cmd_queue.Queue.create(backend='serial')
    >>> job1a = queue.submit('echo "Hello World" && sleep 0.1', name='job1a')
    >>> job1b = queue.submit('echo "Hello Revocable" && sleep 0.1', name='job1b')
    >>> job2a = queue.submit('echo "Hello Crushed" && sleep 0.1', depends=[job1a], name='job2a')
    >>> job2b = queue.submit('echo "Hello Shadow" && sleep 0.1', depends=[job1b], name='job2b')
    >>> job3 = queue.submit('echo "Hello Excavate" && sleep 0.1', depends=[job2a, job2b], name='job3')
    >>> jobX = queue.submit('echo "Hello Barrette" && sleep 0.1', depends=[], name='jobX')
    >>> jobY = queue.submit('echo "Hello Overwrite" && sleep 0.1', depends=[jobX], name='jobY')
    >>> jobZ = queue.submit('echo "Hello Giblet" && sleep 0.1', depends=[jobY], name='jobZ')
    ...
    >>> # Use print_graph to get a "network text" representation of the DAG
    >>> # This gives you a sense of what jobs can run in parallel
    >>> queue.print_graph(reduced=False)
    Graph:
    ╟── job1a
    ╎   └─╼ job2a
    ╎       └─╼ job3 ╾ job2b
    ╟── job1b
    ╎   └─╼ job2b
    ╎       └─╼  ...
    ╙── jobX
        └─╼ jobY
            └─╼ jobZ
    >>> # The purpose of command queue is not to run the code, but to
    >>> # generate the code that would run the code.
    >>> # The rprint command (rich print) gives you the gist of the code
    >>> # command queue would run. Flags can be given to modify conciseness.
    >>> queue.rprint(with_rich=0, colors=0)
    # --- ...
    #!/bin/bash
    # Written by cmd_queue ...
    <BLANKLINE>
    # ----
    # Jobs
    # ----
    <BLANKLINE>
    #
    ### Command 1 / 8 - job1a
    echo "Hello World" && sleep 0.1
    #
    ### Command 2 / 8 - job1b
    echo "Hello Revocable" && sleep 0.1
    #
    ### Command 3 / 8 - job2a
    echo "Hello Crushed" && sleep 0.1
    #
    ### Command 4 / 8 - job2b
    echo "Hello Shadow" && sleep 0.1
    #
    ### Command 5 / 8 - job3
    echo "Hello Excavate" && sleep 0.1
    #
    ### Command 6 / 8 - jobX
    echo "Hello Barrette" && sleep 0.1
    #
    ### Command 7 / 8 - jobY
    echo "Hello Overwrite" && sleep 0.1
    #
    ### Command 8 / 8 - jobZ
    echo "Hello Giblet" && sleep 0.1
    >>> # Different backends have different ways of executing the
    >>> # the underlying DAG, but it always boils down to: generate the code
    >>> # that would execute your jobs.
    >>> #
    >>> # For the TMUX queue it boils down to writing a bash script for
    >>> # sessions that can run in parallel, and a bash script that submits
    >>> # them as different sessions (note: locks exist but are ommitted here)
    >>> tmux_queue = queue.change_backend('tmux', size=2)
    >>> tmux_queue.rprint(with_rich=0, colors=0, with_locks=0)
    # --- ...sh
    #!/bin/bash
    # Written by cmd_queue ...
    # ----
    # Jobs
    # ----
    #
    ### Command 1 / 3 - jobX
    echo "Hello Barrette" && sleep 0.1
    #
    ### Command 2 / 3 - jobY
    echo "Hello Overwrite" && sleep 0.1
    #
    ### Command 3 / 3 - jobZ
    echo "Hello Giblet" && sleep 0.1
    # --- ...sh
    #!/bin/bash
    # Written by cmd_queue ...
    # ----
    # Jobs
    # ----
    #
    ### Command 1 / 4 - job1a
    echo "Hello World" && sleep 0.1
    #
    ### Command 2 / 4 - job2a
    echo "Hello Crushed" && sleep 0.1
    #
    ### Command 3 / 4 - job1b
    echo "Hello Revocable" && sleep 0.1
    #
    ### Command 4 / 4 - job2b
    echo "Hello Shadow" && sleep 0.1
    # --- ...sh
    #!/bin/bash
    # Written by cmd_queue ...
    # ----
    # Jobs
    # ----
    #
    ### Command 1 / 1 - job3
    echo "Hello Excavate" && sleep 0.1
    # --- ...sh
    #!/bin/bash
    # Driver script to start the tmux-queue
    echo "submitting 8 jobs"
    ### Run Queue: cmdq_unnamed_000_... with 3 jobs
    tmux new-session -d -s cmdq_unnamed_000_... "bash"
    tmux send -t cmdq_unnamed_... \
        "source ...sh" \
        Enter
    ### Run Queue: cmdq_unnamed_001_... with 4 jobs
    tmux new-session -d -s cmdq_unnamed_001_... "bash"
    tmux send -t cmdq_unnamed_001_... \
        "source ...sh" \
        Enter
    ### Run Queue: cmdq_unnamed_002_... with 1 jobs
    tmux new-session -d -s cmdq_unnamed_002_... "bash"
    tmux send -t cmdq_unnamed_... \
        "source ...sh" \
        Enter
    echo "jobs submitted"
    >>> # The slurm queue is very simple, it just constructs one bash file that is the
    >>> # sbatch commands to submit your jobs. All of the other details are taken care of
    >>> # by slurm itself.
    >>> # xdoctest: +IGNORE_WANT
    >>> slurm_queue = queue.change_backend('slurm')
    >>> slurm_queue.rprint(with_rich=0, colors=0)
    # --- ...sh
    mkdir -p ".../logs"
    JOB_000=$(sbatch --job-name="job1a" --output="/.../logs/job1a.sh" --wrap 'echo "Hello World" && sleep 0.1' --parsable)
    JOB_001=$(sbatch --job-name="job1b" --output="/.../logs/job1b.sh" --wrap 'echo "Hello Revocable" && sleep 0.1' --parsable)
    JOB_002=$(sbatch --job-name="jobX" --output="/.../logs/jobX.sh" --wrap 'echo "Hello Barrette" && sleep 0.1' --parsable)
    JOB_003=$(sbatch --job-name="job2a" --output="/.../logs/job2a.sh" --wrap 'echo "Hello Crushed" && sleep 0.1' "--dependency=afterok:${JOB_000}" --parsable)
    JOB_004=$(sbatch --job-name="job2b" --output="/.../logs/job2b.sh" --wrap 'echo "Hello Shadow" && sleep 0.1' "--dependency=afterok:${JOB_001}" --parsable)
    JOB_005=$(sbatch --job-name="jobY" --output="/.../logs/jobY.sh" --wrap 'echo "Hello Overwrite" && sleep 0.1' "--dependency=afterok:${JOB_002}" --parsable)
    JOB_006=$(sbatch --job-name="job3" --output="/.../logs/job3.sh" --wrap 'echo "Hello Excavate" && sleep 0.1' "--dependency=afterok:${JOB_003}:${JOB_004}" --parsable)
    JOB_007=$(sbatch --job-name="jobZ" --output="/.../logs/jobZ.sh" --wrap 'echo "Hello Giblet" && sleep 0.1' "--dependency=afterok:${JOB_005}" --parsable)
    >>> # The airflow backend is slightly different because it defines
    >>> # DAGs with Python files, so we write a Python file instead of
    >>> # a bash file. NOTE: the process of actually executing the airflow
    >>> # DAG has not been finalized yet. (Help wanted)
    >>> airflow_queue = queue.change_backend('airflow')
    >>> airflow_queue.rprint(with_rich=0, colors=0)
    # --- ...py
    from airflow import DAG
    from datetime import timezone
    from datetime import datetime as datetime_cls
    from airflow.operators.bash import BashOperator
    now = datetime_cls.utcnow().replace(tzinfo=timezone.utc)
    dag = DAG(
        'SQ',
        start_date=now,
        catchup=False,
        tags=['example'],
    )
    jobs = dict()
    jobs['job1a'] = BashOperator(task_id='job1a', bash_command='echo "Hello World" && sleep 0.1', dag=dag)
    jobs['job1b'] = BashOperator(task_id='job1b', bash_command='echo "Hello Revocable" && sleep 0.1', dag=dag)
    jobs['job2a'] = BashOperator(task_id='job2a', bash_command='echo "Hello Crushed" && sleep 0.1', dag=dag)
    jobs['job2b'] = BashOperator(task_id='job2b', bash_command='echo "Hello Shadow" && sleep 0.1', dag=dag)
    jobs['job3'] = BashOperator(task_id='job3', bash_command='echo "Hello Excavate" && sleep 0.1', dag=dag)
    jobs['jobX'] = BashOperator(task_id='jobX', bash_command='echo "Hello Barrette" && sleep 0.1', dag=dag)
    jobs['jobY'] = BashOperator(task_id='jobY', bash_command='echo "Hello Overwrite" && sleep 0.1', dag=dag)
    jobs['jobZ'] = BashOperator(task_id='jobZ', bash_command='echo "Hello Giblet" && sleep 0.1', dag=dag)
    jobs['job2a'].set_upstream(jobs['job1a'])
    jobs['job2b'].set_upstream(jobs['job1b'])
    jobs['job3'].set_upstream(jobs['job2a'])
    jobs['job3'].set_upstream(jobs['job2b'])
    jobs['jobY'].set_upstream(jobs['jobX'])
    jobs['jobZ'].set_upstream(jobs['jobY'])


Example:
    >>> # Given a Queue object, the "run" method will attempt to execute it
    >>> # for you and give you a sense of progress.
    >>> # xdoctest: +IGNORE_WANT
    >>> import cmd_queue
    >>> queue = cmd_queue.Queue.create(backend='serial')
    >>> job1a = queue.submit('echo "Hello World" && sleep 0.1', name='job1a')
    >>> job1b = queue.submit('echo "Hello Revocable" && sleep 0.1', name='job1b')
    >>> job2a = queue.submit('echo "Hello Crushed" && sleep 0.1', depends=[job1a], name='job2a')
    >>> job2b = queue.submit('echo "Hello Shadow" && sleep 0.1', depends=[job1b], name='job2b')
    >>> job3 = queue.submit('echo "Hello Excavate" && sleep 0.1', depends=[job2a, job2b], name='job3')
    >>> jobX = queue.submit('echo "Hello Barrette" && sleep 0.1', depends=[], name='jobX')
    >>> jobY = queue.submit('echo "Hello Overwrite" && sleep 0.1', depends=[jobX], name='jobY')
    >>> jobZ = queue.submit('echo "Hello Giblet" && sleep 0.1', depends=[jobY], name='jobZ')
    >>> # Using the serial queue simply executes all of the commands in order in
    >>> # the current session. This behavior can be useful as a fallback or
    >>> # for debugging.
    >>> # Note: xdoctest doesnt seem to capture the set -x parts. Not sure why.
    >>> queue.run(block=True, system=True)  # xdoctest: +IGNORE_WANT
    ┌─── START CMD ───
    [ubelt.cmd] ...@...:...$ bash ...sh
    + echo 'Hello World'
    Hello World
    + sleep 0.1
    + echo 'Hello Revocable'
    Hello Revocable
    + sleep 0.1
    + echo 'Hello Crushed'
    Hello Crushed
    + sleep 0.1
    + echo 'Hello Shadow'
    Hello Shadow
    + sleep 0.1
    + echo 'Hello Excavate'
    Hello Excavate
    + sleep 0.1
    + echo 'Hello Barrette'
    Hello Barrette
    + sleep 0.1
    + echo 'Hello Overwrite'
    Hello Overwrite
    + sleep 0.1
    + echo 'Hello Giblet'
    Hello Giblet
    + sleep 0.1
    Command Queue Final Status:
    {"status": "done", "passed": 8, "failed": 0, "skipped": 0, "total": 8, "name": "", "rootid": "..."}
    └─── END CMD ───
    >>> # The TMUX queue does not show output directly by default (although
    >>> # it does have access to methods that let it grab logs from tmux)
    >>> # But normally you can attach to the tmux sessions to look at them
    >>> # The default monitor will depend on if you have textual installed or not.
    >>> # Another default behavior is that it will ask if you want to kill
    >>> # previous command queue tmux sessions, but this can be disabled.
    >>> import ubelt as ub
    >>> if 'tmux' in cmd_queue.Queue.available_backends():
    >>>     tmux_queue = queue.change_backend('tmux', size=2)
    >>>     tmux_queue.run(with_textual='auto', check_other_sessions=False)
    [ubelt.cmd] joncrall@calculex:~/code/cmd_queue$ bash /home/joncrall/.cache/cmd_queue/tmux/unnamed_2022-07-27_cbfeedda/run_queues_unnamed.sh
    submitting 8 jobs
    jobs submitted
    ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━┓
    ┃ tmux session name ┃ status ┃ passed ┃ failed ┃ skipped ┃ total ┃
    ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━┩
    │ cmdq_unnamed_000  │ done   │ 3      │ 0      │ 0       │ 3     │
    │ cmdq_unnamed_001  │ done   │ 4      │ 0      │ 0       │ 4     │
    │ cmdq_unnamed_002  │ done   │ 1      │ 0      │ 0       │ 1     │
    │ agg               │ done   │ 8      │ 0      │ 0       │ 8     │
    └───────────────────┴────────┴────────┴────────┴─────────┴───────┘
    >>> # The monitoring for the slurm queue is basic, and the extent to
    >>> # which features can be added will depend on your slurm config.
    >>> # Any other slurm monitoring tools can be used. There are plans
    >>> # to implement a textual monitor based on the slurm logfiles.
    >>> if 'slurm' in cmd_queue.Queue.available_backends():
    >>>     slurm_queue = queue.change_backend('slurm')
    >>>     slurm_queue.run()
    ┌─── START CMD ───
    [ubelt.cmd] ...sh
    └─── END CMD ───
                             slurm-monitor
    ┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
    ┃ num_running ┃ num_in_queue ┃ total_monitored ┃ num_at_start ┃
    ┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
    │ 0           │ 31           │ 118             │ 118          │
    └─────────────┴──────────────┴─────────────────┴──────────────┘
    >>> # xdoctest: +SKIP
    >>> # Running airflow queues is not implemented yet
    >>> if 'airflow' in cmd_queue.Queue.available_backends():
    >>>     airflow_queue = queue.change_backend('airflow')
    >>>     airflow_queue.run()
"""

__mkinit__ = """
mkinit -m cmd_queue
"""
__version__ = '0.1.5'


__submodules__ = {
    'base_queue': ['Queue'],
}
from cmd_queue import base_queue

from cmd_queue.base_queue import (Queue,)

__all__ = ['Queue', 'base_queue']
