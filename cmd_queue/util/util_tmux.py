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
                sessions.append({
                    'id': session_id,
                    'rest': rest
                })
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
        return ub.cmd(tmux._capture_pane_command(target_session), verbose=verbose)

    @staticmethod
    def kill_session(target_session: str, verbose: int = 3) -> Any:
        return ub.cmd(tmux._kill_session_command(target_session), verbose=verbose)

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
            sys.executable, '-m', 'cmd_queue', 'monitor',
            '--manifest=' + str(manifest_path),
        ]
        if extra_args:
            cmd_parts.extend(extra_args)
        # Wrap in a small shell script so the pane stays open after the
        # monitor exits, letting the user see the final table.
        inner = ' '.join(shlex.quote(p) for p in cmd_parts)
        bash_payload = (
            f'{inner}; '
            'echo; echo "[cmd_queue monitor exited] press enter to close"; '
            'read -r _'
        )
        new_session_cmd = [
            'tmux', 'new-session', '-d', '-s', session_name,
            'bash', '-lc', bash_payload,
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
                ub.cmd(['tmux', 'switch-client', '-t', session_name],
                       verbose=verbose, check=True)
                info['attached_via'] = 'switch-client'
            else:
                # ``attach-session`` is interactive, so let the foreground
                # process inherit the tty.
                ub.cmd(['tmux', 'attach-session', '-t', session_name],
                       verbose=verbose, check=False)
                info['attached_via'] = 'attach-session'
        return info

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
            "pane_id",
            "pane_index",
            "pane_pid",

            "pane_active",
            "pane_dead",
            "pane_in_mode",
            "pane_synchronized",
            "pane_tty",
            "pane_start_command",
            "pane_start_path",
            "pane_current_path",
            "pane_current_command",
            "cursor_x",
            "cursor_y",
            "scroll_region_upper",
            "scroll_region_lower",
            "saved_cursor_x",
            "saved_cursor_y",
            "alternate_on",
            "alternate_saved_x",
            "alternate_saved_y",
            "cursor_flag",
            "insert_flag",
            "keypad_cursor_flag",
            "keypad_flag",
            "wrap_flag",
            "mouse_standard_flag",
            "mouse_button_flag",
            "mouse_any_flag",
            "mouse_utf8_flag",
            "history_size",
            "history_limit",
            "history_bytes",
            "pane_width",
            "pane_height",
            # "pane_title",  # removed in 3.1+
        ]
        format_code = json.dumps({k: '#{' + k + '}' for k in PANE_FORMATS})
        rows = []
        out: Any = ub.cmd(['tmux', 'list-panes', '-t', str(target_session), '-F', format_code], verbose=0)
        for line in out.stdout.strip().split('\n'):
            row = json.loads(line)
            rows.append(row)
        return rows
