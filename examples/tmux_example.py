"""
Demonstrates the ``monitor`` kwarg on the tmux backend.

Three modes are illustrated:

    * ``monitor='inline'`` (default) — the live status table renders in
      the current shell, just like before. Closing the shell loses the
      view and (depending on your terminal) may kill the parent process.

    * ``monitor='tmux'`` — the status table renders in a *separate*
      detached tmux session. The original shell still blocks until jobs
      finish, but the visible UI (and the post-run cleanup) lives in a
      session that survives the shell closing. Run with ``--mode=tmux``.

    * ``monitor='none'`` — no live UI; ``run()`` headless-blocks until
      jobs finish. Useful in non-interactive scripts. The reattach hint
      is still printed so a human can attach via ``cmd_queue monitor``.

The job DAG has four levels and shows meaningful parallel execution:

    Level 1 (prep):      prep-A  prep-B  prep-C  prep-D   (parallel, 5-8s)
    Level 2 (process):   proc-A  proc-B  proc-C  proc-D   (each after one prep, 3-5s)
    Level 3 (merge):     merge-X (after proc-A + proc-B)
                         merge-Y (after proc-C + proc-D)  (parallel, 3-4s)
    Level 4 (finalize):  final   (after both merges, 2s)

By default one of the proc jobs is forced to fail so the failure
summary (and dependency-skip cascade) is visible. Pass ``--failures=0``
for a clean run, or higher numbers for more failures.

CommandLine:
    # Default: inline monitor (current shell), one forced failure
    python ~/code/cmd_queue/examples/tmux_example.py

    # Spawn the monitor in its own tmux session and attach
    python ~/code/cmd_queue/examples/tmux_example.py --mode=tmux

    # Run silently and reattach manually with `cmd_queue monitor <name>`
    python ~/code/cmd_queue/examples/tmux_example.py --mode=none

    # Force a clean run (no injected failures)
    python ~/code/cmd_queue/examples/tmux_example.py --failures=0
"""
import argparse


def main():
    import cmd_queue

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--mode',
        choices=['inline', 'tmux', 'none'],
        default='tmux',
        help='Where the monitor UI runs.',
    )
    parser.add_argument(
        '--name',
        default='tmux-example',
        help='Queue name; also doubles as the lookup key for '
             '`cmd_queue monitor <name>`.',
    )
    parser.add_argument(
        '--workers', type=int, default=4,
        help='Number of parallel tmux workers.',
    )
    parser.add_argument(
        '--failures', type=int, default=1,
        help='Number of proc-* jobs to force into failure (0-4). The '
             'failures cascade: dependent merge/final jobs are skipped.',
    )
    parser.add_argument(
        '--no-logs', dest='logs', action='store_false',
        help='Disable per-job log capture (default: enabled).',
    )
    parser.set_defaults(logs=True)
    args = parser.parse_args()

    queue = cmd_queue.Queue.create(
        backend='tmux',
        size=args.workers,
        name=args.name,
    )

    proc_names = ['proc-A', 'proc-B', 'proc-C', 'proc-D']
    fail_set = set(proc_names[:max(0, min(args.failures, len(proc_names)))])

    def proc_cmd(name: str, sleep: int) -> str:
        body = f'echo "[{name}] start"; sleep {sleep}'
        if name in fail_set:
            return (
                f'{body}; echo "[{name}] FORCED FAILURE" >&2; '
                f'exit 1'
            )
        return f'{body}; echo "[{name}] done"'

    submit_kw = {'log': args.logs}

    # Level 1: four independent prep jobs — run fully in parallel.
    prep_a = queue.submit(
        'echo "[prep-A] start"; sleep 5; echo "[prep-A] done"',
        name='prep-A', **submit_kw)
    prep_b = queue.submit(
        'echo "[prep-B] start"; sleep 7; echo "[prep-B] done"',
        name='prep-B', **submit_kw)
    prep_c = queue.submit(
        'echo "[prep-C] start"; sleep 6; echo "[prep-C] done"',
        name='prep-C', **submit_kw)
    prep_d = queue.submit(
        'echo "[prep-D] start"; sleep 8; echo "[prep-D] done"',
        name='prep-D', **submit_kw)

    # Level 2: each process job depends on exactly one prep job; some
    # may be forced to fail by --failures.
    proc_a = queue.submit(
        proc_cmd('proc-A', 3), name='proc-A', depends=[prep_a], **submit_kw)
    proc_b = queue.submit(
        proc_cmd('proc-B', 4), name='proc-B', depends=[prep_b], **submit_kw)
    proc_c = queue.submit(
        proc_cmd('proc-C', 5), name='proc-C', depends=[prep_c], **submit_kw)
    proc_d = queue.submit(
        proc_cmd('proc-D', 3), name='proc-D', depends=[prep_d], **submit_kw)

    # Level 3: two merge jobs, each waiting on a pair of proc jobs.
    merge_x = queue.submit(
        'echo "[merge-X] start"; sleep 4; echo "[merge-X] done"',
        name='merge-X', depends=[proc_a, proc_b], **submit_kw)
    merge_y = queue.submit(
        'echo "[merge-Y] start"; sleep 3; echo "[merge-Y] done"',
        name='merge-Y', depends=[proc_c, proc_d], **submit_kw)

    # Level 4: single finalize job — the whole pipeline converges here.
    queue.submit(
        'echo "[final] start"; sleep 2; echo "[final] done"',
        name='final', depends=[merge_x, merge_y], **submit_kw)

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
        other_session_handler='kill',
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
        python ~/code/cmd_queue/examples/tmux_example.py --mode=tmux
    """
    main()
