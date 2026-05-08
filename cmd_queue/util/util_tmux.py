from __future__ import annotations

"""
Generic tmux helpers
"""
from typing import Any, Dict, List, Optional

import ubelt as ub


class tmux:
    """
    TODO:
        - [ ] should use libtmux instead, or provide a compatible minimal API.

    Example:
        >>> # xdoctest: +SKIP
        >>> from cmd_queue.util.util_tmux import tmux
        >>> sessions = tmux.list_sessions()

    """

    @staticmethod
    def list_sessions() -> List[Dict[str, str]]:
        info = ub.cmd('tmux list-sessions')
        sessions = []
        for line in info['out'].split('\n'):
            line = line.strip()
            if line:
                session_id, rest = line.split(':', 1)
                sessions.append({'id': session_id, 'rest': rest})
        return sessions

    @staticmethod
    def _kill_session_command(target_session: str) -> str:
        return f'tmux kill-session -t {target_session}'

    @staticmethod
    def _capture_pane_command(target_session: str) -> str:
        # Really should take a target pane argument
        return f'tmux capture-pane -p -t "{target_session}:0.0"'

    @staticmethod
    def capture_pane(target_session: str, verbose: int = 3) -> Any:
        return ub.cmd(
            tmux._capture_pane_command(target_session), verbose=verbose
        )

    @staticmethod
    def kill_session(target_session: str, verbose: int = 3) -> Any:
        return ub.cmd(
            tmux._kill_session_command(target_session), verbose=verbose
        )

    @staticmethod
    def kill_pane(pane_id: str, verbose: int = 3) -> Any:
        return ub.cmd(f'tmux kill-pane -t {pane_id}', verbose=verbose)

    @staticmethod
    def is_inside() -> bool:
        """True if the current process is running inside a tmux session."""
        import os

        return bool(os.environ.get('TMUX'))

    @staticmethod
    def has_session(target_session: str) -> bool:
        info = ub.cmd(['tmux', 'has-session', '-t', target_session])
        return info['ret'] == 0

    @staticmethod
    def spawn_monitor_session(
        session_name: str,
        manifest_path: Any,
        attach: bool = True,
        verbose: int = 0,
        extra_args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Start ``cmd_queue monitor --manifest=<path>`` in a detached tmux
        session and (optionally) attach the user to it.

        Returns a dict describing what was created and how to reattach.
        """
        import os
        import shlex
        import sys

        if not ub.find_exe('tmux'):
            raise RuntimeError('tmux is not available')

        # Always invoke the same Python interpreter that started run() — a
        # globally-installed older ``cmd_queue`` binary on PATH would not
        # know about the monitor subcommand.
        cmd_parts = [
            sys.executable,
            '-m',
            'cmd_queue',
            'monitor',
            '--manifest=' + str(manifest_path),
        ]
        if extra_args:
            cmd_parts.extend(extra_args)
        # After the monitor exits, drop into an interactive shell so the
        # pane stays alive and the user can scroll up to read the final
        # status table without a synthetic prompt blocking dismissal.
        inner = ' '.join(shlex.quote(p) for p in cmd_parts)
        bash_payload = f'{inner}; exec bash'
        new_session_cmd = [
            'tmux',
            'new-session',
            '-d',
            '-s',
            session_name,
            'bash',
            '-lc',
            bash_payload,
        ]
        ub.cmd(new_session_cmd, verbose=verbose, check=True)

        info: Dict[str, Any] = {
            'session_name': session_name,
            'attach_command': f'tmux attach -t {session_name}',
        }
        if attach:
            inside = bool(os.environ.get('TMUX'))
            if inside:
                # Switching the current client is the in-tmux equivalent of
                # attach; spawning a nested attach is rejected by tmux.
                ub.cmd(
                    ['tmux', 'switch-client', '-t', session_name],
                    verbose=verbose,
                    check=True,
                )
                info['attached_via'] = 'switch-client'
            else:
                # ``attach-session`` is interactive, so let the foreground
                # process inherit the tty.
                ub.cmd(
                    ['tmux', 'attach-session', '-t', session_name],
                    verbose=verbose,
                    check=False,
                )
                info['attached_via'] = 'attach-session'
        return info

    @staticmethod
    def block_with_attach_prompt(
        session_name: str,
        is_finished_fn: Any,
        refresh_rate: float = 1.0,
        label: str = 'queue',
    ) -> None:
        """
        Block until ``is_finished_fn()`` returns truthy, while letting the
        user press ``a`` to attach (or switch) to the given tmux session
        and ``q`` / ``d`` to stop watching from the parent shell.

        On a non-TTY stdin (e.g. piped invocation, CI), falls back to a
        silent polling loop.

        Args:
            session_name: target tmux session for the attach action.
            is_finished_fn: zero-arg callable returning True when the
                queue is done.
            refresh_rate: how often (seconds) to re-check completion and
                poll for keypresses.
            label: short noun used in the user-facing prompt.
        """
        import os
        import sys
        import time

        if not sys.stdin.isatty():
            while not is_finished_fn():
                time.sleep(refresh_rate)
            return

        import select
        import termios
        import tty

        inside_tmux = bool(os.environ.get('TMUX'))
        attach_cmd = (
            f'tmux switch-client -t {session_name}'
            if inside_tmux
            else f'tmux attach -t {session_name}'
        )
        print(f'Watching {label}.')
        import rich

        rich.print(
            rf'[bold]Press \[a][/bold] to attach to monitor session ({session_name})'
        )
        rich.print(
            r'[bold]Press \[q][/bold] to stop watching (queue keeps running).'
        )
        print(f'Manual reattach anytime from another shell:\n{attach_cmd}')

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                if is_finished_fn():
                    return
                ready, _, _ = select.select([sys.stdin], [], [], refresh_rate)
                if not ready:
                    continue
                ch = sys.stdin.read(1)
                if ch in ('a', 'A'):
                    # Restore terminal before tmux takes over the tty.
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    try:
                        if inside_tmux:
                            ub.cmd(
                                ['tmux', 'switch-client', '-t', session_name],
                                check=False,
                            )
                        else:
                            ub.cmd(
                                ['tmux', 'attach-session', '-t', session_name],
                                check=False,
                            )
                    finally:
                        # Re-enter cbreak when the user detaches back.
                        tty.setcbreak(fd)
                elif ch in ('q', 'Q', 'd', 'D'):
                    return
                elif ch == '\x03':  # Ctrl-C
                    raise KeyboardInterrupt
        except KeyboardInterrupt:
            return
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    @staticmethod
    def attach_or_switch(session_name: str) -> None:
        """Bring ``session_name`` to the foreground for the user.

        Inside an existing tmux client, this issues ``switch-client`` so
        we don't try to nest tmux. Otherwise we ``attach-session`` and
        let the foreground process inherit the tty (the user can detach
        with the usual binding to come back).
        """
        import os

        if os.environ.get('TMUX'):
            ub.cmd(
                ['tmux', 'switch-client', '-t', session_name],
                check=False,
            )
        else:
            ub.cmd(
                ['tmux', 'attach-session', '-t', session_name],
                check=False,
            )

    @staticmethod
    def list_panes(target_session: str) -> List[Dict[str, str]]:
        """
        Ignore:
            from cmd_queue.util.util_tmux import tmux
            sessions = tmux.list_sessions()
            rows = []
            for session in tmux.list_sessions():
                target_session = session['id']
                rows.extend(tmux.list_panes(target_session))
            print(f'rows = {ub.urepr(rows, nl=1)}')
        """
        import json

        # References:
        # https://github.com/tmux-python/libtmux/blob/f705713c7aff1b14e8f8f3ca53d1b0b6ba6e98d0/src/libtmux/formats.py#L80
        PANE_FORMATS = [
            'pane_id',
            'pane_index',
            'pane_pid',
            'pane_active',
            'pane_dead',
            'pane_in_mode',
            'pane_synchronized',
            'pane_tty',
            'pane_start_command',
            'pane_start_path',
            'pane_current_path',
            'pane_current_command',
            'cursor_x',
            'cursor_y',
            'scroll_region_upper',
            'scroll_region_lower',
            'saved_cursor_x',
            'saved_cursor_y',
            'alternate_on',
            'alternate_saved_x',
            'alternate_saved_y',
            'cursor_flag',
            'insert_flag',
            'keypad_cursor_flag',
            'keypad_flag',
            'wrap_flag',
            'mouse_standard_flag',
            'mouse_button_flag',
            'mouse_any_flag',
            'mouse_utf8_flag',
            'history_size',
            'history_limit',
            'history_bytes',
            'pane_width',
            'pane_height',
            # "pane_title",  # removed in 3.1+
        ]
        format_code = json.dumps({k: '#{' + k + '}' for k in PANE_FORMATS})
        rows = []
        out: Any = ub.cmd(
            [
                'tmux',
                'list-panes',
                '-t',
                str(target_session),
                '-F',
                format_code,
            ],
            verbose=0,
        )
        for line in out.stdout.strip().split('\n'):
            row = json.loads(line)
            rows.append(row)
        return rows
