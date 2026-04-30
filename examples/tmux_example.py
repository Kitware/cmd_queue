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

CommandLine:
    # Default: inline monitor (current shell)
    python ~/code/cmd_queue/examples/tmux_example.py

    # Spawn the monitor in its own tmux session and attach
    python ~/code/cmd_queue/examples/tmux_example.py --mode=tmux

    # Run silently and reattach manually with `cmd_queue monitor <name>`
    python ~/code/cmd_queue/examples/tmux_example.py --mode=none
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
    args = parser.parse_args()

    queue = cmd_queue.Queue.create(
        backend='tmux',
        size=args.workers,
        name=args.name,
    )

    # Level 1: four independent prep jobs — run fully in parallel.
    prep_a = queue.submit(
        'echo "[prep-A] start"; sleep 5; echo "[prep-A] done"', name='prep-A')
    prep_b = queue.submit(
        'echo "[prep-B] start"; sleep 7; echo "[prep-B] done"', name='prep-B')
    prep_c = queue.submit(
        'echo "[prep-C] start"; sleep 6; echo "[prep-C] done"', name='prep-C')
    prep_d = queue.submit(
        'echo "[prep-D] start"; sleep 8; echo "[prep-D] done"', name='prep-D')

    # Level 2: each process job depends on exactly one prep job.
    proc_a = queue.submit(
        'echo "[proc-A] start"; sleep 3; echo "[proc-A] done"',
        name='proc-A', depends=[prep_a])
    proc_b = queue.submit(
        'echo "[proc-B] start"; sleep 4; echo "[proc-B] done"',
        name='proc-B', depends=[prep_b])
    proc_c = queue.submit(
        'echo "[proc-C] start"; sleep 5; echo "[proc-C] done"',
        name='proc-C', depends=[prep_c])
    proc_d = queue.submit(
        'echo "[proc-D] start"; sleep 3; echo "[proc-D] done"',
        name='proc-D', depends=[prep_d])

    # Level 3: two merge jobs, each waiting on a pair of proc jobs.
    merge_x = queue.submit(
        'echo "[merge-X] start"; sleep 4; echo "[merge-X] done"',
        name='merge-X', depends=[proc_a, proc_b])
    merge_y = queue.submit(
        'echo "[merge-Y] start"; sleep 3; echo "[merge-Y] done"',
        name='merge-Y', depends=[proc_c, proc_d])

    # Level 4: single finalize job — the whole pipeline converges here.
    queue.submit(
        'echo "[final] start"; sleep 2; echo "[final] done"',
        name='final', depends=[merge_x, merge_y])

    queue.print_graph()

    if not queue.is_available():
        raise SystemExit('tmux backend not available on this machine')

    print(f'\nLaunching with monitor={args.mode!r}, workers={args.workers}\n')

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
