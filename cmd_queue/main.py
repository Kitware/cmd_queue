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
import rich

__todo__ = """

- [ ] Currently any operation on a CLI queue will read and rewrite an entire
      json file. This is noticably slugginsh when working in bash. Instead we
      should abstract this with the concept of a CLIQueueDatabase. Its initial
      implementation would effectively do the same thing, but then we could
      test and compare alternative implementations of this API. For instance,
      we could write files to a folder and then collect all files at the end so
      multiple jobs could be written simultaniously.

"""


def _testcase():
    r"""

    ..code bash:
        cmd_queue new test_queue
        # cmd_queue submit test_queue --command="
        #      python -c 'import sys; print(sys.argv)' \
        #              --key=val \
        #              --flag \
        #              --yaml_arg='
        #                  yaml: mappings
        #                  are: useful
        #              ' \
        #              --final=arg \
        #              positional
        #      "

        cmd_queue submit test_queue -- \
             python -c 'import sys; print(sys.argv)' \
                     --key=val \
                     --flag \
                     --yaml_arg='
                         yaml: mappings
                         are: useful
                     ' \
                     --final=arg \
                     positional

        cmd_queue show test_queue
        cmd_queue run test_queue --backend=serial
        cmd_queue run test_queue --backend=tmux

    """


class CommonConfig(scfg.DataConfig):

    qname = scfg.Value(None, position=1, help='name of the CLI queue')

    dpath = scfg.Value('auto', help=ub.paragraph(
        '''
        The path the CLI will use to store intermediate files. Defaults to $XDG_CACHE/.cache/cmd_queue/cli
        '''
    ))

    verbose = scfg.Value(1, help='verbosity level')

    def __post_init__(config):
        if config['dpath'] == 'auto':
            config['dpath'] = str(ub.Path.appdir('cmd_queue/cli'))

    @classmethod
    def main(cls, cmdline=1, **kwargs):
        config = cls.cli(cmdline=cmdline, data=kwargs, strict=True)
        if config.verbose:
            rich.print('config = ' + ub.urepr(config, nl=1))
        cli_queue_name = config['qname']
        config.cli_queue_dpath = ub.Path(config['dpath'])
        config.cli_queue_fpath = config.cli_queue_dpath / (str(cli_queue_name) + '.cmd_queue.json')
        config.run()


class CommonShowRun(CommonConfig):
    workers = scfg.Value(1, help='number of concurrent queues for the tmux backend.')

    backend = scfg.Value('tmux', help='the execution backend to use', choices=['tmux', 'slurm', 'serial', 'airflow'])

    def _build_queue(config):
        import cmd_queue
        import json
        queue = cmd_queue.Queue.create(size=max(1, config['workers']),
                                       backend=config['backend'],
                                       name=config['qname'])
        # Run a new CLI queue
        data = json.loads(config.cli_queue_fpath.read_text())
        print('data = {}'.format(ub.urepr(data, nl=1)))
        row = None
        try:
            for row in data:
                if row['type'] == 'header':
                    bash_command = row['header']
                    if isinstance(bash_command, list):
                        bash_command = ' '.join([str(p) for p in bash_command])
                    queue.add_header_command(bash_command)
                elif row['type'] == 'command':
                    bash_command = row['command']
                    if isinstance(bash_command, list):
                        if len(bash_command) == 1:
                            # hack
                            import shlex
                            if shlex.quote(bash_command[0]) == bash_command[0]:
                                bash_command = bash_command[0]
                            else:
                                bash_command = shlex.quote(bash_command[0])
                        else:
                            import shlex
                            bash_command = ' '.join([shlex.quote(str(p)) for p in bash_command])
                    submitkw = ub.udict(row) & {'name', 'depends'}
                    print('\n\n\n')
                    print(f'submitkw={submitkw}')
                    print('bash_command = {}'.format(ub.urepr(bash_command, nl=1)))
                    print('\n\n\n')
                    queue.submit(bash_command, log=False, **submitkw)
        except Exception:
            print('row = {}'.format(ub.urepr(row, nl=1)))
            raise
        return queue


class CmdQueueCLI(scfg.ModalCLI):
    """
    The cmd_queue CLI for building, executing, and managing queues from bash.

    This is a modal CLI where "action" will specify the main behavior.
    Most behaviors are related to creating and submitting custom queues.

    The ``cleanup`` action is for helping to manage the tmux backend, maingly
    killing session names that start with ``"cmdq_"``.

    Quickstart
    ##########

    .. code:: bash

        # Create a new queue
        cmd_queue new "my_queue"

        # Submit a job to it
        cmd_queue submit "my_queue" --  echo "\"my first job\""

        # Show the generated script
        cmd_queue show "my_queue"

        # Create multiple items in a bash array, and loop over that array
        items=(
            "item1" "item2" "item3" "item4" "item5" "item6"
            "item7" "item8" "item9" "item10" "item11" "item12"
        )
        for item in "${items[@]}"; do

            # For each item, we create a job to be run in the queue
            cmd_queue submit "my_queue" --  echo "\"process output for --item=$item\""
        done

        # Show the generated script
        cmd_queue show "my_queue"

        # Execute your queue.
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

    class cleanup(CommonConfig):
        """
        cleanup tmux sessions
        """

        yes = scfg.Value(False, isflag=True, help='if True say yes to prompts', short_alias=['y'])

        __command__ = 'cleanup'
        def run(config):
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

    class run(CommonShowRun):
        """
        run a queue
        """
        __command__ = 'run'
        def run(config):
            """
            """
            queue = config._build_queue()
            queue.run()

    class show(CommonShowRun):
        """
        display a queue
        """
        __command__ = 'show'

        def run(config):
            queue = config._build_queue()
            queue.print_commands()
            queue.print_graph()

    class submit(CommonConfig):
        """
        submit a job to a queue
        """
        __command__ = 'submit'

        jobname = scfg.Value(None, help='for submit, this is the name of the new job')
        depends = scfg.Value(None, help='comma separated jobnames to depend on')

        command = scfg.Value(None, type=str, position=2, nargs='*', help=ub.paragraph(
            '''
            Specifies the bash command to queue.
            Care must be taken when specifying this argument.  If specifying as a
            key/value pair argument, it is important to quote and escape the bash
            command properly.  A more convinient way to specify this command is as
            a positional argument. End all of the options to this CLI with `--` and
            then specify your full command.
            '''))

        def run(config):
            """
            Example:
                from cmd_queue.main import *  # NOQA
                CmdQueueCLI.new.main(cmdline=0, qname='test-queue')
                CmdQueueCLI.submit.main(cmdline=0, qname='test-queue', command=['echo', 'hello', 'world'])
                CmdQueueCLI.show.main(cmdline=0, qname='test-queue')
                CmdQueueCLI.run.main(cmdline=0, qname='test-queue')

                CmdQueueCLI.new.main(cmdline='test-queue')
                CmdQueueCLI.submit.main(cmdline='test-queue echo hello world')
                CmdQueueCLI.submit.main(cmdline='test-queue -- echo hello world')
                CmdQueueCLI.show.main(cmdline='test-queue')
                CmdQueueCLI.run.main(cmdline='test-queue')

                ub.cmd('cmd_queue new test-queue', system=True, verbose=3)
                ub.cmd('cmd_queue submit test-queue hello world', system=True, verbose=3)
                ub.cmd('cmd_queue submit test-queue -- echo hello world', system=True, verbose=3)
                ub.cmd(ub.codeblock(
                    '''
                    cmd_queue submit test-queue -- \
                            python -c "if 1:
                                import ubelt as ub
                                print(ub.modname_to_modpath('ubelt'))
                            "
                    '''), system=True, verbose=3)
                ub.cmd('cmd_queue show test-queue', system=True, verbose=3)
                ub.cmd('cmd_queue run test-queue --backend=serial', system=True, verbose=3)


                cmd_queue new test-queue
                cmd_queue submit test-queue hello world
                cmd_queue submit test-queue -- echo hello world
                cmd_queue submit test-queue -- \
                        python -c "if 1:
                            import ubelt as ub
                            print(ub.modname_to_modpath('ubelt'))
                        "
                cmd_queue submit test-queue -- python -c "import sys; print(sys.argv)" --foo bar --baz biz
                cmd_queue show test-queue
                cmd_queue run test-queue --backend=serial
                cmd_queue run test-queue --backend=tmux

            Example:
                ub.cmd('cmd_queue test-queue')
            """
            import json
            # Run a new CLI queue
            data = json.loads(config.cli_queue_fpath.read_text())
            row = {'type': 'command', 'command': config['command']}
            if config.jobname:
                row['name'] = config.jobname
            if config.depends:
                row['depends'] = config.depends
            data.append(row)
            config.cli_queue_fpath.write_text(json.dumps(data))

    class new(CommonConfig):
        """
        create a new queue
        """
        __command__ = 'new'
        header = scfg.Value(None, help='a header command to execute in every session (e.g. activating a virtualenv). Only used when action is new')

        def run(config):
            import json
            # Start a new CLI queue
            data = []
            config = config
            config.cli_queue_fpath.parent.ensuredir()

            if config.header is not None:
                data.append({'type': 'header', 'header': config.header})

            config.cli_queue_fpath.write_text(json.dumps(data))

    class list(CommonConfig):
        """
        display available queues
        """
        __command__ = 'list'
        def run(config):
            print(ub.urepr(list(config.cli_queue_dpath.glob('*.cmd_queue.json'))))


main = CmdQueueCLI.main


if __name__ == '__main__':
    """

    CommandLine:
        python ~/code/cmd_queue/cmd_queue/__main__.py
        python -m cmd_queue cleanup
    """
    CmdQueueCLI.main()
