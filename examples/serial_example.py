"""
The simplest backend: ``backend='serial'``.

The serial backend writes the DAG to a single bash script and runs the
jobs one at a time in topological order, in the current process. No
tmux, no scheduler, nothing to install -- it works anywhere. That makes
it the natural "level 1" of the serial -> tmux -> slurm progression: the
same queue API you use here scales out unchanged to the other backends.

Because everything runs sequentially, the total runtime is the *sum* of
every job's duration (~50s for the demo DAG below), whereas the tmux and
slurm backends run independent branches in parallel. Watching the serial
run is a good way to feel why the parallel backends exist.

The job DAG has four logical levels (identical to the tmux/slurm
examples so the three can be compared directly). Each logical job is
split into a serial chain of smaller one-second jobs.

    Level 1 (prep):      prep-A  prep-B  prep-C  prep-D
    Level 2 (process):   proc-A  proc-B  proc-C  proc-D   (each after one prep)
    Level 3 (merge):     merge-X (after proc-A + proc-B)
                         merge-Y (after proc-C + proc-D)
    Level 4 (finalize):  final   (after both merges)

By default one of the proc jobs is forced to fail so the failure
summary (and dependency-skip cascade) is visible. Pass ``--failures=0``
for a clean run, or higher numbers for more failures.

CommandLine:
    # Run the demo DAG serially
    python ~/code/cmd_queue/examples/serial_example.py

    # Force a clean run (no injected failures)
    python ~/code/cmd_queue/examples/serial_example.py --failures=0
"""

import scriptconfig as scfg
import ubelt as ub


class SerialExampleConfig(scfg.DataConfig):
    """
    Command line options for the serial backend example.
    """

    name = scfg.Value(
        'serial-example',
        help='Queue name.',
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

    args = SerialExampleConfig.cli()

    queue = cmd_queue.Queue.create(
        backend='serial',
        name=args.name,
    )

    proc_names = ['proc-A', 'proc-B', 'proc-C', 'proc-D']
    fail_set = set(proc_names[: max(0, min(args.failures, len(proc_names)))])

    submit_kw = {'log': args.logs}

    def submit_sleep_chain(base_name, total_sleep, depends=None, fail=False):
        """
        Submit a logical sleep job as a chain of smaller queue jobs.

        This keeps the logical runtime roughly equal to ``total_sleep``,
        but gives the queue more individual jobs to track.

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

    # Level 1: four independent prep jobs. With a parallel backend these
    # would run concurrently; serially they run back-to-back.
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

    if not queue.is_available():
        raise SystemExit('serial backend not available on this machine')

    print(
        f'\nRunning serially: failures={args.failures}, logs={args.logs}\n'
    )

    result = queue.run(block=True)

    print(f'\nrun() returned: {result}')


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/examples/serial_example.py
    """
    main()
