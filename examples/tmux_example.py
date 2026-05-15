"""
Demonstrates the ``monitor`` kwarg on the tmux backend.

Four monitor modes are illustrated:

    * ``monitor='hybrid'`` (default) — the live status table renders in
      the current shell *and* a detached ``cmd_queue monitor`` tmux
      session is spawned alongside. Press ``[a]`` from the inline UI to
      attach (or switch-client) to the tmux session, ``[q]`` to stop
      watching.

    * ``monitor='inline'`` — only the in-shell live UI; no tmux session
      is spawned.

    * ``monitor='tmux'`` — only the detached tmux session, no inline
      UI. Useful when you want the visible status table (and post-run
      cleanup) to survive the calling shell closing.

    * ``monitor='none'`` — no live UI; ``run()`` headless-blocks until
      jobs finish. Useful in non-interactive scripts. The reattach hint
      is still printed so a human can attach via ``cmd_queue monitor``.

The job DAG has four logical levels and shows meaningful parallel execution.
Each logical job is split into a serial chain of smaller one-second jobs.
This creates more queue jobs while keeping the total runtime roughly the same.

    Level 1 (prep):      prep-A  prep-B  prep-C  prep-D   (parallel, 5-8s)
    Level 2 (process):   proc-A  proc-B  proc-C  proc-D   (each after one prep, 3-5s)
    Level 3 (merge):     merge-X (after proc-A + proc-B)
                         merge-Y (after proc-C + proc-D)  (parallel, 3-4s)
    Level 4 (finalize):  final   (after both merges, 2s)

By default one of the proc jobs is forced to fail so the failure
summary (and dependency-skip cascade) is visible. Pass ``--failures=0``
for a clean run, or higher numbers for more failures.

CommandLine:
    # Default (hybrid): inline monitor in this shell + attachable tmux
    # session. Press [a] in the inline UI to jump into the tmux monitor,
    # [q] to stop watching (queue keeps running).
    python ~/code/cmd_queue/examples/tmux_example.py

    # Inline-only, no side tmux session
    python ~/code/cmd_queue/examples/tmux_example.py --mode=inline

    # Spawn the monitor only in a tmux session (no inline view)
    python ~/code/cmd_queue/examples/tmux_example.py --mode=tmux

    # Run silently and reattach manually with `cmd_queue monitor <name>`
    python ~/code/cmd_queue/examples/tmux_example.py --mode=none

    # Force a clean run (no injected failures)
    python ~/code/cmd_queue/examples/tmux_example.py --failures=0
"""

import scriptconfig as scfg
import ubelt as ub


class TmuxExampleConfig(scfg.DataConfig):
    """
    Automatically created module for IPython interactive environment
    """

    mode = scfg.Value(
        'hybrid',
        help='Where the monitor UI runs.',
        choices=['hybrid', 'inline', 'tmux', 'none'],
    )
    name = scfg.Value(
        'tmux-example',
        help=ub.paragraph(
            """
            Queue name; also doubles as the lookup key for `cmd_queue
            monitor <name>`.
            """
        ),
    )
    workers = scfg.Value(4, type=int, help='Number of parallel tmux workers.')
    failures = scfg.Value(
        6,
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

    args = TmuxExampleConfig.cli()

    queue = cmd_queue.Queue.create(
        backend='tmux',
        size=args.workers,
        name=args.name,
    )

    proc_names = ['proc-A', 'proc-B', 'proc-C', 'proc-D']
    fail_set = set(proc_names[: max(0, min(args.failures, len(proc_names)))])

    submit_kw = {'log': args.logs}

    def submit_sleep_chain(base_name, total_sleep, depends=None, fail=False):
        """
        Submit a logical sleep job as a chain of smaller queue jobs.

        This keeps the logical runtime roughly equal to ``total_sleep``,
        but gives the tmux monitor more individual jobs to display.

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

    # Level 1: four independent prep jobs — run fully in parallel.
    # Each logical prep job is split into a serial chain of smaller jobs.
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

    # Level 4: single finalize job — the whole pipeline converges here.
    submit_sleep_chain('final', 2, depends=[merge_x, merge_y])

    queue.print_graph()

    if not queue.is_available():
        raise SystemExit('tmux backend not available on this machine')

    print(
        f'\nLaunching with monitor={args.mode!r}, workers={args.workers}, '
        f'failures={args.failures}, logs={args.logs}\n'
    )

    result = queue.run(
        block=True,
        monitor=args.mode,
        onfail='kill',
        other_session_handler='auto',
    )

    print(f'\nrun() returned: {result}')
    if args.mode == 'tmux':
        print(
            'The monitor tmux session stayed alive after the workers '
            'finished so the final status table is visible. Reattach '
            'from any shell with:\n'
            f'    tmux attach -t cmdq-monitor-{args.name}-...\n'
            'or look it up by queue name with:\n'
            f'    cmd_queue monitor {args.name}'
        )


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/examples/tmux_example.py
    """
    main()
