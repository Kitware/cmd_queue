#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
This is the main script for the cmd_queue CLI. The :class:`CmdQueueConfig`
defines the available options and its docstring provides a quick tutorial.
For help run:

.. code:: bash

    cmd_queue --help

"""
import scriptconfig as scfg
import ubelt as ub


class CmdQueueConfig(scfg.DataConfig):
    """
    The cmd_queue CLI for building, executing, and managing queues from bash.

    This is a modal CLI where "action" will specify the main behavior.
    Most behaviors are related to creating and submitting custom queues.

    The ``cleanup`` action is for helping to manage the tmux backend, maingly
    killing session names that start with ``"cmdq_"``.

    Quickstart
    ##########

        # Create a new queue
        cmd_queue new "my_queue"

        # Create multiple items in a bash array, and loop over that array
        items=(
            "item1" "item2" "item3" "item4" "item5" "item6"
            "item7" "item8" "item9" "item10" "item11" "item12"
        )
        for item in "${items[@]}"; do

            # For each item, we create a job to be run in the queue
            cmd_queue submit "my_queue" --  echo \"process $item\"

        done

        # It is a good idea to look at what you queued up before you execute it
        cmd_queue show "my_queue"

        # This actually executes your queue. The serial backend is the most
        # compatable, but the least powerful.
        cmd_queue run "my_queue" --backend=serial


    Step 1:  Initialize a new queue
    ###############################

    .. code:: bash

        cmd_queue new "my_cli_queue"

        # Note if you are working in a virtualenv you need to specify a header
        # to activate it if you are going to use the tmux or slurm backend
        # (serial will work without this)

        # e.g. for conda
        cmd_queue new "my_cli_queue" --header="conda activate myenv"

        # e.g. for pyenv
        cmd_queue new "my_cli_queue" --header="pyenv shell 3.11.0 && source $PYENV_ROOT/versions/3.11.0/envs/pyenv3.11.0/bin/activate"

    Step 2:  Initialize a new queue
    ###############################

    .. code:: bash

        cmd_queue submit "my_cli_queue" --  echo hello world
        cmd_queue submit "my_cli_queue" --  echo "hello world"
        cmd_queue submit "my_cli_queue" -- cowsay hellow world
        # Quotes are necessary if we are using bash constructs like &&
        cmd_queue submit "my_cli_queue" -- 'cowsay MOO && sleep 1'
        cmd_queue submit "my_cli_queue" -- 'cowsay MOOOO && sleep 2'
        cmd_queue submit "my_cli_queue" -- 'cowsay MOOOOOO && sleep 3'
        cmd_queue submit "my_cli_queue" -- 'cowsay MOOOOOOOO && sleep 4'

    Step 3:  Inspect your commands before you run
    #############################################

    .. code:: bash

        cmd_queue show "my_cli_queue"

    Step 4:  Run your commands
    ##########################

    .. code:: bash

        # Run using the serial backend
        cmd_queue run "my_cli_queue" --backend=serial

        # Run using the tmux backend
        cmd_queue run "my_cli_queue" --backend=tmux --workers=2

    Extra: other features
    #####################

    .. code:: bash

        # List all the known queues you've created
        cmd_queue list

        # Cleanup tmux sessions (useful when jobs are failing)
        cmd_queue cleanup

    """
    action = scfg.Value(None, position=1, help='action', choices=[
        'cleanup', 'show', 'new', 'submit', 'run', 'list'], required=True)

    name = scfg.Value(None, position=2, help='name of the CLI queue')

    command = scfg.Value(None, position=3, nargs='*', help=ub.paragraph(
        '''
        Specifies the bash command to queue.
        Care must be taken when specifying this argument.  If specifying as a
        key/value pair argument, it is important to quote and escape the bash
        command properly.  A more convinient way to specify this command is as
        a positional argument. End all of the options to this CLI with `--` and
        then specify your full command.
        '''))

    workers = scfg.Value(1, help='number of concurrent queues for the tmux backend.')

    backend = scfg.Value('tmux', help='the execution backend to use', choices=['tmux', 'slurm', 'serial', 'airflow'])

    # TODO: use a modal config to separate action behaviors
    header = scfg.Value(None, help='a header command to execute in every session (e.g. activating a virtualenv). Only used when action is new')

    yes = scfg.Value(False, help='if True say yes to prompts')

    dpath = scfg.Value('auto', help=ub.paragraph(
        '''
        The path the CLI will use to store intermediate files. Defaults to $XDG_CACHE/.cache/cmd_queue/cli
        '''
    ))

    def __post_init__(config):
        if config['dpath'] == 'auto':
            config['dpath'] = str(ub.Path.appdir('cmd_queue/cli'))


def main(cmdline=1, **kwargs):
    """
    Example:
        >>> # xdoctest: +SKIP
        >>> cmdline = 0
        >>> kwargs = dict()
        >>> main(cmdline=cmdline, **kwargs)
    """
    import json
    config = CmdQueueConfig.cli(cmdline=cmdline, data=kwargs, strict=True)  # autocomplete=True
    print('config = ' + ub.urepr(dict(config), nl=1))

    cli_queue_name = config['name']
    cli_queue_dpath = ub.Path(config['dpath'])
    cli_queue_fpath = cli_queue_dpath / (str(cli_queue_name) + '.cmd_queue.json')

    if config['action'] == 'list':
        print(ub.urepr(list(cli_queue_dpath.glob('*.cmd_queue.json'))))

    elif config['action'] == 'new':
        # Start a new CLI queue
        data = []
        cli_queue_fpath.parent.ensuredir()

        if config.header is not None:
            data.append({'type': 'header', 'header': config.header})

        cli_queue_fpath.write_text(json.dumps(data))

    elif config['action'] == 'submit':
        # Run a new CLI queue
        data = json.loads(cli_queue_fpath.read_text())
        data.append({'type': 'command', 'command': config['command']})
        cli_queue_fpath.write_text(json.dumps(data))

    elif config['action'] == 'show':
        queue = build_queue(cli_queue_fpath, config)
        queue.print_commands()
        queue.print_graph()

    elif config['action'] == 'run':
        queue = build_queue(cli_queue_fpath, config)
        queue.run()

    elif config['action'] == 'cleanup':
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
        if config.yes or prompt.Confirm.ask('Do you want to kill these?'):
            for session_id in sessions_ids:
                tmux.kill_session(session_id)

    else:
        raise KeyError(config['action'])


def build_queue(cli_queue_fpath, config):
    import cmd_queue
    import json
    queue = cmd_queue.Queue.create(size=max(1, config['workers']),
                                   backend=config['backend'],
                                   name=config['name'])
    # Run a new CLI queue
    data = json.loads(cli_queue_fpath.read_text())
    for row in data:
        if row['type'] == 'header':
            bash_command = row['header']
            if isinstance(bash_command, list):
                bash_command = ' '.join(bash_command)
            queue.add_header_command(bash_command)
        elif row['type'] == 'command':
            bash_command = row['command']
            if isinstance(bash_command, list):
                bash_command = ' '.join(bash_command)
            queue.submit(bash_command, log=False)
    return queue

if __name__ == '__main__':
    """

    CommandLine:
        python ~/code/cmd_queue/cmd_queue/__main__.py
        python -m cmd_queue cleanup
    """
    main()
