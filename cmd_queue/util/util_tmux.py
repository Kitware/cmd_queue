"""
Generic tmux helpers
"""
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
    def list_sessions():
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
    def _kill_session_command(target_session):
        return f'tmux kill-session -t {target_session}'

    @staticmethod
    def _capture_pane_command(target_session):
        # Relly should take a target pane argument
        return f'tmux capture-pane -p -t "{target_session}:0.0"'

    @staticmethod
    def capture_pane(target_session, verbose=3):
        return ub.cmd(tmux._capture_pane_command(target_session), verbose=verbose)

    @staticmethod
    def kill_session(target_session, verbose=3):
        return ub.cmd(tmux._kill_session_command(target_session), verbose=verbose)

    @staticmethod
    def kill_pane(pane_id, verbose=3):
        return ub.cmd(f'tmux kill-pane -t {pane_id}', verbose=verbose)

    @staticmethod
    def list_panes(target_session):
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
        out = ub.cmd(['tmux', 'list-panes', '-t', str(target_session), '-F', format_code], verbose=0)
        for line in out.stdout.strip().split('\n'):
            row = json.loads(line)
            rows.append(row)
        return rows
