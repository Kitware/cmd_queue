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
        default='inline',
        help='Where the monitor UI runs.',
    )
    parser.add_argument(
        '--name',
        default='tmux-example',
        help='Queue name; also doubles as the lookup key for '
             '`cmd_queue monitor <name>`.',
    )
    parser.add_argument(
        '--workers', type=int, default=2,
        help='Number of parallel tmux workers.',
    )
    args = parser.parse_args()

    queue = cmd_queue.Queue.create(
        backend='tmux',
        size=args.workers,
        name=args.name,
    )

    # Build a small DAG so the status table has something interesting to show.
    job_a = queue.submit('echo "a starting"; sleep 2; echo "a done"', name='a')
    job_b = queue.submit('echo "b starting"; sleep 3; echo "b done"', name='b')
    queue.submit(
        'echo "c (depends on a, b)"; sleep 1; echo "c done"',
        name='c',
        depends=[job_a, job_b],
    )

    queue.print_graph()

    if not queue.is_available():
        raise SystemExit('tmux backend not available on this machine')

    print(f'\nLaunching with monitor={args.mode!r}\n')

    # The interesting line. Identical for any monitor mode — only the
    # location of the UI changes.
    result = queue.run(
        block=True,
        monitor=args.mode,
        onfail='kill',          # tear down idle worker sessions on success
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
