"""
Submitting the demo DAG to a real slurm scheduler (``backend='slurm'``).

This is the "level 3" backend: cmd_queue converts the job DAG into
``sbatch`` submissions (with ``--dependency`` edges) and lets slurm
schedule them across the cluster. The same queue API used by the serial
and tmux examples is reused here unchanged -- only the backend and a few
scheduler-specific options differ.

Partition / account
-------------------
On a shared cluster you typically must route jobs to a specific
partition and bill them to an account, e.g.::

    python ~/code/cmd_queue/examples/slurm_example.py \
        --partition=general --account=my_project

When ``--partition``/``--account`` are omitted (the default) the options
are simply left off the ``sbatch`` command, so slurm uses the cluster's
default partition and no accounting. That is what lets this example run
as-is on a vanilla single-node slurm install (which usually exposes a
default ``debug`` partition).

Monitoring
----------
Like the tmux example, ``--mode`` selects where the live status UI runs:

    * ``hybrid`` (default) -- inline table in this shell *and* an
      attachable detached tmux monitor session.
    * ``inline``          -- in-shell live UI only.
    * ``tmux``            -- detached tmux monitor session only.
    * ``none``            -- headless; ``run()`` blocks until jobs finish.

The job DAG has four logical levels (identical to the serial/tmux
examples so the three can be compared directly). Each logical job is
split into a serial chain of smaller one-second jobs.

    Level 1 (prep):      prep-A  prep-B  prep-C  prep-D   (parallel)
    Level 2 (process):   proc-A  proc-B  proc-C  proc-D   (each after one prep)
    Level 3 (merge):     merge-X (after proc-A + proc-B)
                         merge-Y (after proc-C + proc-D)  (parallel)
    Level 4 (finalize):  final   (after both merges)

By default one of the proc jobs is forced to fail so the failure
summary (and dependency-skip cascade) is visible. Pass ``--failures=0``
for a clean run, or higher numbers for more failures.

CommandLine:
    # Run on the cluster's default partition (works on a local install)
    python ~/code/cmd_queue/examples/slurm_example.py

    # Target a specific partition / account on a shared cluster
    python ~/code/cmd_queue/examples/slurm_example.py \
        --partition=general --account=my_project

    # Just print the sbatch script without submitting anything
    python ~/code/cmd_queue/examples/slurm_example.py --dry=1

    # Force a clean run (no injected failures)
    python ~/code/cmd_queue/examples/slurm_example.py --failures=0
"""

import scriptconfig as scfg
import ubelt as ub


class SlurmExampleConfig(scfg.DataConfig):
    """
    Command line options for the slurm backend example.
    """

    mode = scfg.Value(
        'hybrid',
        type=str,
        help='Where the monitor UI runs.',
        choices=['hybrid', 'inline', 'tmux', 'none'],
    )
    name = scfg.Value(
        'slurm-example',
        help=ub.paragraph(
            """
            Queue name; also doubles as the lookup key for `cmd_queue
            monitor <name>`.
            """
        ),
    )
    partition = scfg.Value(
        None,
        help=ub.paragraph(
            """
            Slurm partition to submit to. If unset, the sbatch
            --partition option is omitted and the cluster's default
            partition is used.
            """
        ),
    )
    account = scfg.Value(
        None,
        help=ub.paragraph(
            """
            Slurm account to bill jobs to. If unset, the sbatch
            --account option is omitted.
            """
        ),
    )
    cpus = scfg.Value(
        1,
        type=int,
        help='Value for sbatch --cpus-per-task.',
    )
    dry = scfg.Value(
        False,
        isflag=True,
        help='Print the sbatch script and exit without submitting.',
    )
    failures = scfg.Value(
        1,
        type=int,
        help=ub.paragraph(
            """
            Number of proc-* logical jobs to force into failure (0-4).
            The failures cascade: dependent merge/final jobs are skipped.
            """
        ),
    )
    logs = scfg.Value(
        True,
        isflag=True,
        help=ub.paragraph(
            """
            Set to False to disable per-job log capture (default: enabled).
            """
        ),
    )


def main():
    import cmd_queue

    args = SlurmExampleConfig.cli()

    # Only pass partition/account through to sbatch when the user
    # actually specified them; otherwise let slurm use its defaults.
    create_kw = {
        'backend': 'slurm',
        'name': args.name,
        'cpus': args.cpus,
    }
    if args.partition is not None:
        create_kw['partition'] = args.partition
    if args.account is not None:
        create_kw['account'] = args.account

    queue = cmd_queue.Queue.create(**create_kw)

    proc_names = ['proc-A', 'proc-B', 'proc-C', 'proc-D']
    fail_set = set(proc_names[: max(0, min(args.failures, len(proc_names)))])

    submit_kw = {'log': args.logs}

    def submit_sleep_chain(base_name, total_sleep, depends=None, fail=False):
        """
        Submit a logical sleep job as a chain of smaller queue jobs.

        This keeps the logical runtime roughly equal to ``total_sleep``,
        but gives the monitor more individual jobs to display.

        Example:
            ``submit_sleep_chain('prep-A', 5)`` creates:

                prep-A-01 -> prep-A-02 -> prep-A-03 -> prep-A-04 -> prep-A-05

            Each part sleeps for one second, so the total duration is still
            about five seconds, plus a small amount of scheduling overhead.
        """
        if total_sleep <= 0:
            raise ValueError('total_sleep must be positive')

        prev_depends = list(depends or [])
        last_job = None

        for idx in range(total_sleep):
            part = idx + 1
            name = f'{base_name}-{part:02d}'
            is_final_part = part == total_sleep

            cmd = f'echo "[{name}] start"; sleep 1; '

            if is_final_part and fail:
                cmd += f'echo "[{base_name}] FORCED FAILURE" >&2; exit 1'
            elif is_final_part:
                cmd += f'echo "[{base_name}] done"'
            else:
                cmd += f'echo "[{name}] done"'

            last_job = queue.submit(
                cmd,
                name=name,
                depends=prev_depends,
                **submit_kw,
            )
            prev_depends = [last_job]

        return last_job

    # Level 1: four independent prep jobs -- slurm can run these in
    # parallel across nodes/cores as resources allow.
    prep_a = submit_sleep_chain('prep-A', 5)
    prep_b = submit_sleep_chain('prep-B', 7)
    prep_c = submit_sleep_chain('prep-C', 6)
    prep_d = submit_sleep_chain('prep-D', 8)

    # Level 2: each process job depends on exactly one prep job; some
    # may be forced to fail by --failures.
    proc_a = submit_sleep_chain(
        'proc-A', 3, depends=[prep_a], fail='proc-A' in fail_set
    )
    proc_b = submit_sleep_chain(
        'proc-B', 4, depends=[prep_b], fail='proc-B' in fail_set
    )
    proc_c = submit_sleep_chain(
        'proc-C', 5, depends=[prep_c], fail='proc-C' in fail_set
    )
    proc_d = submit_sleep_chain(
        'proc-D', 3, depends=[prep_d], fail='proc-D' in fail_set
    )

    # Level 3: two merge jobs, each waiting on a pair of proc jobs.
    merge_x = submit_sleep_chain('merge-X', 4, depends=[proc_a, proc_b])
    merge_y = submit_sleep_chain('merge-Y', 3, depends=[proc_c, proc_d])

    # Level 4: single finalize job -- the whole pipeline converges here.
    submit_sleep_chain('final', 2, depends=[merge_x, merge_y])

    queue.print_graph()

    # Show the actual sbatch submission script that would run.
    queue.print_commands()

    if args.dry:
        print('\n--dry set: printed sbatch script, not submitting.')
        return

    if not queue.is_available():
        raise SystemExit(
            'slurm backend not available on this machine '
            '(is slurmd running and squeue working?)'
        )

    print(
        f'\nSubmitting with monitor={args.mode!r}, '
        f'partition={args.partition!r}, account={args.account!r}, '
        f'failures={args.failures}, logs={args.logs}\n'
    )

    result = queue.run(
        block=True,
        monitor=args.mode,
        onfail='kill',
    )

    print(f'\nrun() returned: {result}')


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/examples/slurm_example.py
    """
    main()
