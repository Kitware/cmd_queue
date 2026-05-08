#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
This is the main script for the cmd_queue CLI. The :class:`CmdQueueConfig`
defines the available options and its docstring provides a quick tutorial.
For help run:

.. code:: bash

    cmd_queue --help

"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable

import rich
import scriptconfig as scfg
import ubelt as ub

__todo__ = """

- [ ] Currently any operation on a CLI queue will read and rewrite an entire
      json file. This is noticeably sluggish when working in bash. Instead we
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


if TYPE_CHECKING:
    import cmd_queue


class CommonConfig(scfg.DataConfig):
    qname = scfg.Value(None, position=1, help='name of the CLI queue')

    dpath = scfg.Value(
        'auto',
        help=ub.paragraph(
            """
        The path the CLI will use to store intermediate files. Defaults to $XDG_CACHE/.cache/cmd_queue/cli
        """
        ),
    )

    verbose = scfg.Value(1, help='verbosity level')

    def __post_init__(config) -> None:
        if config['dpath'] == 'auto':
            config['dpath'] = str(ub.Path.appdir('cmd_queue/cli'))

    @classmethod
    def main(cls, argv: int = 1, **kwargs: Any) -> None:
        # scriptconfig ``argv`` accepts True/None/list[str]; the integer
        # idiom (``1`` => use sys.argv) is undocumented but in use here.
        config = cls.cli(argv=argv, data=kwargs, strict=True)  # ty: ignore[invalid-argument-type]
        if config.verbose:
            # ub.urepr's return type is unioned with a tuple form for
            # the json branch; the str cast is always-safe here.
            rich.print('config = ' + str(ub.urepr(config, nl=1)))
        cli_queue_name = config['qname']
        # scriptconfig allows attaching arbitrary attributes to a Config
        # instance at runtime.
        config.cli_queue_dpath = ub.Path(config['dpath'])  # ty: ignore[unresolved-attribute]
        config.cli_queue_fpath = config.cli_queue_dpath / (  # ty: ignore[unresolved-attribute]
            str(cli_queue_name) + '.cmd_queue.json'
        )
        config.run()


class CommonShowRun(CommonConfig):
    workers = scfg.Value(
        1, help='number of concurrent queues for the tmux backend.'
    )

    backend = scfg.Value(
        'tmux',
        help='the execution backend to use',
        choices=['tmux', 'slurm', 'serial', 'airflow'],
    )

    gpus = scfg.Value(
        None,
        help='a comma separated list of the gpu numbers to spread across. tmux backend only.',
    )

    def _build_queue(config) -> 'cmd_queue.Queue':
        import json

        import cmd_queue

        queue = cmd_queue.Queue.create(
            size=max(1, config['workers']),
            backend=config['backend'],
            name=config['qname'],
            gpus=config['gpus'],
        )
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

                            bash_command = ' '.join(
                                [shlex.quote(str(p)) for p in bash_command]
                            )
                    # ``ub.udict.__and__`` accepts an iterable of keys.
                    submitkw = ub.udict(row) & {'name', 'depends'}  # ty: ignore[unsupported-operator]
                    print('\n\n\n')
                    print(f'submitkw={submitkw}')
                    print(
                        'bash_command = {}'.format(ub.urepr(bash_command, nl=1))
                    )
                    print('\n\n\n')
                    queue.submit(bash_command, log=False, **submitkw)
        except Exception:
            print('row = {}'.format(ub.urepr(row, nl=1)))
            raise
        return queue


class CmdQueueCLI(scfg.ModalCLI):
    r"""
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
        cmd_queue submit "my_cli_queue" -- cowsay hello world
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

        yes = scfg.Value(
            False,
            isflag=True,
            help='if True say yes to prompts',
            short_alias=['y'],
        )

        __command__ = 'cleanup'

        def run(config) -> None:
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

        def run(config) -> None:
            """ """
            queue = config._build_queue()
            queue.run()

    class monitor(CommonConfig):
        """
        Monitor an already-running queue.

        Locates the queue by name (via the active-queue index that ``run``
        populates), by manifest path, or by the queue's working directory.
        Useful for reattaching to a queue whose ``run()`` invocation has
        ended (e.g. shell closed) while workers are still active, and as
        the entry point used by the tmux monitor backend to host the
        status UI in its own session.
        """

        __command__ = 'monitor'

        manifest = scfg.Value(
            None,
            help=ub.paragraph(
                """
            Optional explicit path to the monitor manifest JSON. If
            given, this overrides positional name resolution.
            """
            ),
        )

        onfail = scfg.Value(
            '',
            choices=['', 'kill'],
            help=ub.paragraph(
                """
            What to do if the queue ends with at least one failure.
            ``kill`` cancels still-running workers; ``''`` leaves them.
            """
            ),
        )

        onexit = scfg.Value(
            '',
            choices=['', 'capture'],
            help=ub.paragraph(
                """
            What to do once the queue is fully done. ``capture`` runs the
            backend's capture step (e.g. dump tmux pane contents).
            """
            ),
        )

        refresh_rate = scfg.Value(0.4, help='monitor refresh rate, seconds')

        with_textual = scfg.Value(
            'auto', help='use textual UI if available (tmux backend only)'
        )

        def run(config) -> None:
            from cmd_queue import monitor_manifest as mm

            if config.manifest:
                # scriptconfig descriptor narrows to str at runtime.
                manifest_path = ub.Path(config.manifest).expand().absolute()  # ty: ignore[invalid-argument-type]
                if not manifest_path.exists():
                    raise FileNotFoundError(manifest_path)
            else:
                target = config['qname']
                if not target:
                    raise SystemExit(
                        'cmd_queue monitor requires either a queue name '
                        '(positional) or --manifest=<path>'
                    )
                manifest_path = mm.resolve_manifest(target)
            if config.verbose:
                rich.print(
                    f'Loading monitor manifest from [bold]{manifest_path}[/bold]'
                )
            queue = mm.load_queue_for_monitoring(manifest_path)
            kwargs = {}
            try:
                kwargs['refresh_rate'] = config.refresh_rate
            except Exception:
                pass
            if 'with_textual' in queue.monitor.__code__.co_varnames:
                kwargs['with_textual'] = config.with_textual
            # monitor() owns post-run cleanup; only forward the kwargs the
            # backend's monitor signature actually accepts.
            varnames = queue.monitor.__code__.co_varnames
            if 'onfail' in varnames:
                kwargs['onfail'] = config.onfail
            if 'onexit' in varnames:
                kwargs['onexit'] = config.onexit
            queue.monitor(**kwargs)

    class show(CommonShowRun):
        """
        display a queue
        """

        __command__ = 'show'

        def run(config) -> None:
            queue = config._build_queue()
            queue.print_commands()
            queue.print_graph()

    class submit(CommonConfig):
        """
        submit a job to a queue
        """

        __command__ = 'submit'

        jobname = scfg.Value(
            None, help='for submit, this is the name of the new job'
        )
        depends = scfg.Value(None, help='comma separated jobnames to depend on')

        command = scfg.Value(
            None,
            type=str,
            position=2,
            nargs='*',
            help=ub.paragraph(
                """
            Specifies the bash command to queue.
            Care must be taken when specifying this argument.  If specifying as a
            key/value pair argument, it is important to quote and escape the bash
            command properly.  A more convenient way to specify this command is as
            a positional argument. End all of the options to this CLI with `--` and
            then specify your full command.
            """
            ),
        )

        def run(config) -> None:
            r"""
            Example:
                from cmd_queue.main import *  # NOQA
                CmdQueueCLI.new.main(argv=0, qname='test-queue')
                CmdQueueCLI.submit.main(argv=0, qname='test-queue', command=['echo', 'hello', 'world'])
                CmdQueueCLI.show.main(argv=0, qname='test-queue')
                CmdQueueCLI.run.main(argv=0, qname='test-queue')

                CmdQueueCLI.new.main(argv='test-queue')
                CmdQueueCLI.submit.main(argv='test-queue echo hello world')
                CmdQueueCLI.submit.main(argv='test-queue -- echo hello world')
                CmdQueueCLI.show.main(argv='test-queue')
                CmdQueueCLI.run.main(argv='test-queue')

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
        header = scfg.Value(
            None,
            help='a header command to execute in every session (e.g. activating a virtualenv). Only used when action is new',
        )

        def run(config) -> None:
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

        def run(config) -> None:
            print(
                ub.urepr(list(config.cli_queue_dpath.glob('*.cmd_queue.json')))
            )


main: Callable[..., Any] = CmdQueueCLI.main


if __name__ == '__main__':
    """

    CommandLine:
        python ~/code/cmd_queue/cmd_queue/__main__.py
        python -m cmd_queue cleanup
    """
    CmdQueueCLI.main()
