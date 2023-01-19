"""
Generic tmux helpers
"""
import ubelt as ub


class tmux:

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

    def _kill_session_command(target_session):
        return f'tmux kill-session -t {target_session}'

    def _capture_pane_command(target_session):
        # Relly should take a target pane argument
        return f'tmux capture-pane -p -t "{target_session}:0.0"'

    def capture_pane(target_session, verbose=3):
        return ub.cmd(tmux._capture_pane_command(target_session), verbose=verbose)

    def kill_session(target_session, verbose=3):
        return ub.cmd(tmux._kill_session_command(target_session), verbose=verbose)
