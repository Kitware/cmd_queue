#!/usr/bin/env python3
import scriptconfig as scfg
import ubelt as ub


class CmdQueueConfig(scfg.DataConfig):
    """
    The command queue CLI is experimental and needs development.
    Currently ``cmd_queue cleanup`` is the only available command
    which can be used to cleanup tmux session names that start with "cmdq_".
    """
    command = scfg.Value(None, position=1, help='command', choices=['cleanup'])
    ...


def main(cmdline=1, **kwargs):
    """
    Example:
        >>> # xdoctest: +SKIP
        >>> cmdline = 0
        >>> kwargs = dict(
        >>> )
        >>> main(cmdline=cmdline, **kwargs)
    """
    config = CmdQueueConfig.legacy(cmdline=cmdline, data=kwargs)
    print('config = ' + ub.urepr(dict(config), nl=1))

    if config['command'] == 'cleanup':

        from cmd_queue.util.util_tmux import tmux
        sessions = tmux.list_sessions()
        print('sessions = {}'.format(ub.urepr(sessions, nl=1)))

        # Cleanup tmux sessions
        sessions_ids = []
        for session in sessions:
            if session['id'].startswith('cmdq_'):
                sessions_ids.append(session['id'])
        print('sessions_ids = {}'.format(ub.urepr(sessions_ids, nl=1)))
        from rich import prompt
        if prompt.Confirm.ask('Do you want to kill these?'):
            for session_id in sessions_ids:
                tmux.kill_session(session_id)

if __name__ == '__main__':
    """

    CommandLine:
        python ~/code/cmd_queue/cmd_queue/__main__.py
        python -m cmd_queue cleanup
    """
    main()
