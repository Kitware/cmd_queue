#!/usr/bin/env python3
import scriptconfig as scfg
import ubelt as ub


class CmdQueueConfig(scfg.DataConfig):
    """
    The command queue CLI is experimental and needs development.
    Currently ``cmd_queue cleanup`` is the only available command
    which can be used to cleanup tmux session names that start with "cmdq_".

    Example:
        cmd_queue new "my_cli_queue"
        cmd_queue submit "my_cli_queue" "echo hello"
        cmd_queue submit "my_cli_queue" "echo world"
        cmd_queue show "my_cli_queue"
        cmd_queue run "my_cli_queue"
    """
    command = scfg.Value(None, position=1, help='command', choices=['cleanup', 'show', 'new', 'submit', 'run'])
    name = scfg.Value(None, position=2, help='name of the CLI queue')
    bash_text = scfg.Value(None, position=3, nargs='*')
    workers = scfg.Value(0)
    backend = scfg.Value('tmux')


def main(cmdline=1, **kwargs):
    """
    Example:
        >>> # xdoctest: +SKIP
        >>> cmdline = 0
        >>> kwargs = dict(
        >>> )
        >>> main(cmdline=cmdline, **kwargs)
    """
    import json
    config = CmdQueueConfig.legacy(cmdline=cmdline, data=kwargs)
    print('config = ' + ub.urepr(dict(config), nl=1))

    cli_queue_name = config['name']
    cli_queue_fpath = ub.Path(str(cli_queue_name) + '.json')

    def build_queue():
        import cmd_queue
        queue = cmd_queue.Queue.create(size=config['workers'],
                                       backend=config['backend'],
                                       name=config['name'])
        # Run a new CLI queue
        data = json.loads(cli_queue_fpath.read_text())
        for row in data:
            bash = row['bash_text']
            if isinstance(bash, list):
                bash = ' '.join(bash)
            queue.submit(bash)
        return queue

    if config['command'] == 'new':
        # Start a new CLI queue
        data = []
        cli_queue_fpath.write_text(json.dumps(data))

    elif config['command'] == 'submit':
        # Run a new CLI queue
        data = json.loads(cli_queue_fpath.read_text())
        data.append({'bash_text': config['bash_text']})
        cli_queue_fpath.write_text(json.dumps(data))

    elif config['command'] == 'show':
        queue = build_queue()
        queue.rprint()
        queue.print_graph()

    elif config['command'] == 'run':
        queue = build_queue()
        queue.run()

    elif config['command'] == 'cleanup':
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

    else:
        raise KeyError(config['command'])

if __name__ == '__main__':
    """

    CommandLine:
        python ~/code/cmd_queue/cmd_queue/__main__.py
        python -m cmd_queue cleanup
    """
    main()
