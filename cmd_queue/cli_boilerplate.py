"""
This file defines a helper base config that can be used to help make cmd_queue
CLIs so cmd_queue options are standardized and present at the top level.

There are two flavors:

* :class:`CmdQueueConfigMixin` -- the current, :mod:`kwconf`-based class. Use
  this for new code.

* :class:`CMDQueueConfig` -- the original :mod:`scriptconfig`-based class. It is
  **deprecated** but kept for backwards compatibility with downstream code. It
  emits a :class:`DeprecationWarning` when used.

The example below uses the deprecated scriptconfig class; see
:class:`CmdQueueConfigMixin` for the equivalent kwconf usage.

CommandLine:
    xdoctest -m cmd_queue.cli_boilerplate __doc__:0

Example:
    >>> from cmd_queue.cli_boilerplate import CMDQueueConfig
    >>> import scriptconfig as scfg
    >>> import rich
    >>> #
    >>> class MyQueueCLI(CMDQueueConfig):
    >>>     'A custom CLI that includes the cmd-queue boilerplate'
    >>>     my_input_file = scfg.Value(None, help='some custom param')
    >>>     my_num_steps = scfg.Value(3, help='some custom param')
    >>>     is_small = scfg.Value(False, help='some custom param')
    >>>     my_output_file = scfg.Value(None, help='some custom param')
    >>> #
    >>> def my_cli_main(cmdline=1, **kwargs):
    >>>     config = MyQueueCLI.cli(cmdline=cmdline, data=kwargs)
    >>>     rich.print('config = {}'.format(ub.urepr(config, nl=1)))
    >>>     queue = config.create_queue()
    >>>     #
    >>>     ###
    >>>     # Custom code to submit jobs to the queue
    >>>     #
    >>>     job0 = queue.submit(f'echo "processing input file: {config.my_input_file}"', name='ROOT-INPUT-JOB')
    >>>     #
    >>>     independent_outputs = []
    >>>     for idx in range(config.my_num_steps):
    >>>         job_t1 = queue.submit(f'echo "tree {idx}.S"', depends=[job0], name=f'jobname{idx}.1')
    >>>         if not config.is_small:
    >>>             job_t2 = queue.submit(f'echo "tree {idx}.SL"', depends=[job_t1], name=f'jobname{idx}.2')
    >>>             job_t3 = queue.submit(f'echo "tree {idx}.SR"', depends=[job_t2], name=f'jobname{idx}.3')
    >>>             job_t4 = queue.submit(f'echo "tree {idx}.SRR"', depends=[job_t3], name=f'jobname{idx}.4')
    >>>             job_t5 = queue.submit(f'echo "tree {idx}.SRL"', depends=[job_t3], name=f'jobname{idx}.5')
    >>>             job_t6 = queue.submit(f'echo "tree {idx}.T"', depends=[job_t4, job_t5], name=f'jobname{idx}.6')
    >>>             job_t7 = queue.submit(f'echo "tree {idx}.SLT"', depends=[job_t2], name=f'jobname{idx}.7')
    >>>             independent_outputs.extend([job_t6, job_t2])
    >>>         else:
    >>>             independent_outputs.extend([job_t1])
    >>>     #
    >>>     queue.submit(f'echo "processing output file: {config.my_output_file}"', depends=independent_outputs, name='FINAL-OUTPUT-JOB')
    >>>     ###
    >>>     #
    >>>     config.run_queue(queue)
    >>> #
    >>> # Show what happens when you use the serial backend
    >>> print('-------------------')
    >>> print('--- DEMO SERIAL ---')
    >>> print('-------------------')
    >>> my_cli_main(
    >>>     cmdline=0,
    >>>     run=0,
    >>>     print_queue=1,
    >>>     print_commands=1,
    >>>     backend='serial'
    >>> )
    >>> # Show what happens when you use the tmux backend
    >>> print('-----------------')
    >>> print('--- DEMO TMUX ---')
    >>> print('-----------------')
    >>> my_cli_main(
    >>>     cmdline=0,
    >>>     run=0,
    >>>     print_queue=0,
    >>>     is_small=True,
    >>>     my_num_steps=0,
    >>>     print_commands=1,
    >>>     backend='tmux'
    >>> )
    >>> # Show what happens when you use the slurm backend
    >>> print('------------------')
    >>> print('--- DEMO SLURM ---')
    >>> print('------------------')
    >>> my_cli_main(
    >>>     cmdline=0,
    >>>     run=0, backend='slurm',
    >>>     print_commands=1,
    >>>     print_queue=False,
    >>>     slurm_options='''
    >>>         partition: 'general-gpu'
    >>>         account: 'default'
    >>>         ntasks: 1
    >>>         gres: 'gpu:1'
    >>>         cpus_per_task: 4
    >>>     '''
    >>> )
    >>> # xdoctest: +REQUIRES(--run)
    >>> # Actually run with the defaults
    >>> print('----------------')
    >>> print('--- DEMO RUN ---')
    >>> print('----------------')
    >>> my_cli_main(cmdline=0, run=1, print_queue=0, print_commands=0)
"""

from __future__ import annotations

import typing
import warnings
from typing import Any, Dict, Optional

import kwconf as kw
import scriptconfig as scfg
import ubelt as ub

if typing.TYPE_CHECKING:
    import cmd_queue


class CMDQueueConfig(scfg.DataConfig):
    """
    DEPRECATED: use :class:`CmdQueueConfigMixin`, which is kwconf-based.

    A helper to carry around the common boilerplate for cmd-queue CLI's.  The
    general usage is that you will inherit from this class and define config
    options your CLI cares about, however they must not overload any of the
    options specified here.

    Usage will be to call :func:`CMDQueueConfig.create_queue` to initialize a
    queue based on these options, and then execute it with
    :func:`CMDQueueConfig.run_queue`. In this way you do not need to worry
    about this specific boilerplate when writing your application. See
    ``cmd_queue.cli_boilerplate __doc__:0`` for example usage.

    It is a good idea to overwrite the default value of queue_name when
    inheriting: e.g.

    .. code:: python

        queue_name = scfg.Value('your_default_name', help='overwrite the default queue name', group='cmd-queue')

    Other defaults that can be overwritten are:

    .. code:: python

        run = scfg.Value(False, isflag=True, help='if False, only prints the commands, otherwise executes them', group='cmd-queue')

        backend = scfg.Value('tmux', help=('The cmd_queue backend. Can be tmux, slurm, or serial'), group='cmd-queue')

        print_commands = scfg.Value('auto', isflag=True, help='enable / disable rprint before exec', group='cmd-queue')

        print_queue = scfg.Value('auto', isflag=True, help='print the cmd queue DAG', group='cmd-queue')

        with_textual = scfg.Value('auto', isflag=True, help='setting for cmd-queue monitoring', group='cmd-queue')

        other_session_handler = scfg.Value('ask', help='for tmux backend only. How to handle conflicting sessions. Can be ask, kill, or ignore, or auto', group='cmd-queue')

        virtualenv_cmd = scfg.Value(None, type=str, help=ub.paragraph(
            '''
            Command to start the appropriate virtual environment if your bashrc
            does not start it by default.'''), group='cmd-queue')

        tmux_workers = scfg.Value(8, help='number of tmux workers in the queue for the tmux backend', group='cmd-queue')

        slurm_options = scfg.Value(None, help='if the backend is slurm, provide a YAML dictionary for things like partition / etc...', group='cmd-queue')

    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Warn on subclassing rather than at import: importing this module is
        # also how a caller reaches ``CmdQueueConfigMixin``, and warning there
        # would fire for people who never touch the scriptconfig class.
        super().__init_subclass__(**kwargs)
        warnings.warn(
            f'{cls.__name__} inherits from cmd_queue CMDQueueConfig, which is '
            'deprecated and will be removed in a future release. Inherit from '
            'cmd_queue.cli_boilerplate.CmdQueueConfigMixin instead; it is the '
            'kwconf equivalent. Note that kwconf takes cli(argv=...) rather '
            'than cli(cmdline=...), and a bool rather than an int.',
            DeprecationWarning,
            stacklevel=2,
        )

    run = scfg.Value(
        False,
        isflag=True,
        help='if False, only prints the commands, otherwise executes them',
        group='cmd-queue',
    )

    backend = scfg.Value(
        'tmux',
        help=('The cmd_queue backend. Can be tmux, slurm, or serial'),
        group='cmd-queue',
    )

    monitor = scfg.Value(
        'inline',
        # NOTE: type=str is important. Without it scriptconfig smartcasts the
        # string 'none' to Python None, which then fails choices validation.
        type=str,
        help=ub.paragraph(
            """
            Where the live status UI runs while jobs execute.
            hybrid = inline monitor + attachable tmux session (best for
            interactive use); inline = inline only (default); tmux =
            detached tmux session only (survives the calling shell); none
            = headless (reattach hint still printed).
            """
        ),
        group='cmd-queue',
        choices=['hybrid', 'inline', 'tmux', 'none'],
    )

    queue_name = scfg.Value(
        None, help='overwrite the default queue name', group='cmd-queue'
    )

    print_commands = scfg.Value(
        'auto',
        isflag=True,
        help='enable / disable rprint before exec',
        group='cmd-queue',
    )

    print_queue = scfg.Value(
        'auto', isflag=True, help='print the cmd queue DAG', group='cmd-queue'
    )

    with_textual = scfg.Value(
        'auto',
        isflag=True,
        help='setting for cmd-queue monitoring',
        group='cmd-queue',
    )

    other_session_handler = scfg.Value(
        'ask',
        help='for tmux backend only. How to handle conflicting sessions. Can be ask, kill, or ignore, or auto',
        group='cmd-queue',
    )

    virtualenv_cmd = scfg.Value(
        None,
        type=str,
        help=ub.paragraph(
            """
        Command to start the appropriate virtual environment if your bashrc
        does not start it by default."""
        ),
        group='cmd-queue',
    )

    # TODO: add global preamble argument

    tmux_workers = scfg.Value(
        8,
        help='number of tmux workers in the queue for the tmux backend',
        group='cmd-queue',
    )

    slurm_options = scfg.Value(
        None,
        help=ub.paragraph(
            """
        if the backend is slurm, provide a YAML dictionary for things like
        partition / etc...
        """
        ),
        group='cmd-queue',
    )

    def __post_init__(self) -> None:
        from cmd_queue.util.util_yaml import Yaml

        ub.schedule_deprecation(
            modname='cmd_queue',
            name='CMDQueueConfig',
            type='class',
            migration=ub.paragraph(
                """
                CMDQueueConfig is built on scriptconfig. Switch to the
                kwconf-based :class:`CmdQueueConfigMixin`, which has the same
                fields and ``create_queue`` / ``run_queue`` API. Note kwconf
                no longer auto-splits comma strings into lists (use
                ``parser='csv'`` or ``nargs='+'`` on such fields).
                """
            ),
            deprecate='0.3.2',
        )
        # scriptconfig descriptors return the underlying value at runtime;
        # ty sees the descriptor type and flags the assignment.
        self.slurm_options = Yaml.coerce(self.slurm_options) or {}  # ty: ignore[invalid-assignment]

    def create_queue(config, **kwargs: Any) -> 'cmd_queue.Queue':
        """
        Create an empty queue based on options specified in this config

        Args:
            **kwargs: extra args passed to cmd_queue.Queue.create

        Returns:
            cmd_queue.Queue
        """
        import cmd_queue

        queuekw: Dict[str, Any] = {}
        if config.backend == 'slurm':
            # scriptconfig descriptor resolves to a dict at runtime.
            queuekw.update(config.slurm_options)  # ty: ignore[no-matching-overload]
        elif config.backend == 'tmux':
            queuekw.update(
                {
                    'size': config.tmux_workers,
                }
            )
        queuekw.update(kwargs)
        if 'name' not in queuekw:
            queuekw['name'] = config.queue_name
        # scriptconfig descriptor: ``config.backend`` resolves to str at runtime.
        queue = cmd_queue.Queue.create(backend=config.backend, **queuekw)  # ty: ignore[invalid-argument-type]
        if config.virtualenv_cmd:
            # Experimental feature to automatically activate virtual
            # environments
            virtualenv_cmd = config.virtualenv_cmd
            if virtualenv_cmd == 'auto':
                import os
                import shlex

                venv_path = os.environ.get('VIRTUAL_ENV', '')
                if venv_path:
                    virtualenv_cmd = 'source ' + shlex.quote(
                        str(ub.Path(venv_path) / 'bin/activate')
                    )
                else:
                    virtualenv_cmd = None
            if virtualenv_cmd:
                # scriptconfig descriptor narrows to str at runtime.
                queue.add_header_command(virtualenv_cmd)  # ty: ignore[invalid-argument-type]
        return queue

    def run_queue(
        config,
        queue: 'cmd_queue.Queue',
        print_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Execute a queue with options based on this config.

        Args:
            queue (cmd_queue.Queue): queue to run / report
            print_kwargs (None | Dict):
        """

        queue: cmd_queue.Queue
        print_thresh = 30
        if config['print_commands'] == 'auto':
            if len(queue) < print_thresh:
                config['print_commands'] = 1
            else:
                print(
                    f'More than {print_thresh} jobs, skip queue.print_commands. '
                    'If you want to see them explicitly specify print_commands=1'
                )
                config['print_commands'] = 0

        if config['print_queue'] == 'auto':
            if len(queue) < print_thresh:
                config['print_queue'] = 1
            else:
                print(
                    f'More than {print_thresh} jobs, skip queue.print_graph. '
                    'If you want to see them explicitly specify print_queue=1'
                )
                config['print_queue'] = 0

        if config.print_commands:
            if print_kwargs is None:
                print_kwargs = {}
            queue.print_commands(**print_kwargs)

        if config.print_queue:
            queue.print_graph(vertical_chains=True)

        if config.run:
            queue.run(
                with_textual=config.with_textual,
                other_session_handler=config.other_session_handler,
                monitor=config.monitor,
                **kwargs,
            )


class CmdQueueConfigMixin(kw.Config):
    """
    The kwconf-based successor to :class:`CMDQueueConfig`.

    Carries the common boilerplate for cmd-queue CLIs. Inherit from this class
    and add the config options your CLI cares about (they must not clash with
    the options defined here). Use :func:`create_queue` to build a queue from
    these options and :func:`run_queue` to execute / report it.

    This has the same fields and methods as the deprecated
    :class:`CMDQueueConfig`, but is built on :mod:`kwconf` instead of
    :mod:`scriptconfig`. The most visible behavior change inherited from kwconf
    is that comma-separated CLI strings are *not* auto-split into lists; declare
    such fields with ``parser='csv'`` or ``nargs='+'`` if you need that.

    It is a good idea to override the default ``queue_name`` when inheriting:

    .. code:: python

        import kwconf as kw
        queue_name = kw.Value('your_default_name', help='...', group='cmd-queue')

    Example:
        >>> from cmd_queue.cli_boilerplate import CmdQueueConfigMixin
        >>> import kwconf as kw
        >>> import ubelt as ub
        >>> class MyQueueCLI(CmdQueueConfigMixin):
        >>>     my_num_steps = kw.Value(2, help='a custom param')
        >>> def my_cli_main(argv=False, **kwargs):
        >>>     config = MyQueueCLI.cli(argv=argv, data=kwargs)
        >>>     queue = config.create_queue()
        >>>     job0 = queue.submit('echo "root job"', name='ROOT')
        >>>     for idx in range(config.my_num_steps):
        >>>         queue.submit(f'echo "step {idx}"', depends=[job0], name=f'step{idx}')
        >>>     config.run_queue(queue)
        >>> my_cli_main(argv=False, run=0, print_queue=1, print_commands=1, backend='serial')
    """

    # NOTE: do NOT add a ``: bool`` annotation here. kwconf coerces a
    # bool-annotated flag, so ``--run=0`` becomes ``bool('0')`` -> True.
    # Leaving it unannotated keeps the historical semantics: ``--run=0`` is
    # falsy, ``--run=1`` truthy, and bare ``--run`` True.
    run = kw.Flag(
        False,
        help='if False, only prints the commands, otherwise executes them',
        group='cmd-queue',
    )

    backend: str = kw.Value(
        'tmux',
        help=('The cmd_queue backend. Can be tmux, slurm, or serial'),
        group='cmd-queue',
    )

    monitor: str = kw.Value(
        'inline',
        help=ub.paragraph(
            """
            Where the live status UI runs while jobs execute.
            hybrid = inline monitor + attachable tmux session (best for
            interactive use); inline = inline only (default); tmux =
            detached tmux session only (survives the calling shell); none
            = headless (reattach hint still printed).
            """
        ),
        group='cmd-queue',
        choices=['hybrid', 'inline', 'tmux', 'none'],
    )

    queue_name: Optional[str] = kw.Value(
        None, help='overwrite the default queue name', group='cmd-queue'
    )

    print_commands: Any = kw.Value(
        'auto',
        isflag=True,
        help='enable / disable rprint before exec',
        group='cmd-queue',
    )

    print_queue: Any = kw.Value(
        'auto', isflag=True, help='print the cmd queue DAG', group='cmd-queue'
    )

    with_textual: Any = kw.Value(
        'auto',
        isflag=True,
        help='setting for cmd-queue monitoring',
        group='cmd-queue',
    )

    other_session_handler: str = kw.Value(
        'ask',
        help='for tmux backend only. How to handle conflicting sessions. Can be ask, kill, or ignore, or auto',
        group='cmd-queue',
    )

    virtualenv_cmd: Optional[str] = kw.Value(
        None,
        parser=str,
        help=ub.paragraph(
            """
        Command to start the appropriate virtual environment if your bashrc
        does not start it by default."""
        ),
        group='cmd-queue',
    )

    tmux_workers: int = kw.Value(
        8,
        help='number of tmux workers in the queue for the tmux backend',
        group='cmd-queue',
    )

    slurm_options: Any = kw.Value(
        None,
        help=ub.paragraph(
            """
        if the backend is slurm, provide a YAML dictionary for things like
        partition / etc...
        """
        ),
        group='cmd-queue',
    )

    def __post_init__(self) -> None:
        from cmd_queue.util.util_yaml import Yaml

        self.slurm_options = Yaml.coerce(self.slurm_options) or {}

    def create_queue(config, **kwargs: Any) -> 'cmd_queue.Queue':
        """
        Create an empty queue based on options specified in this config

        Args:
            **kwargs: extra args passed to cmd_queue.Queue.create

        Returns:
            cmd_queue.Queue
        """
        import cmd_queue

        queuekw: Dict[str, Any] = {}
        if config.backend == 'slurm':
            queuekw.update(config.slurm_options)
        elif config.backend == 'tmux':
            queuekw.update(
                {
                    'size': config.tmux_workers,
                }
            )
        queuekw.update(kwargs)
        if 'name' not in queuekw:
            queuekw['name'] = config.queue_name
        queue = cmd_queue.Queue.create(backend=config.backend, **queuekw)
        if config.virtualenv_cmd:
            # Experimental feature to automatically activate virtual
            # environments
            virtualenv_cmd: Optional[str] = config.virtualenv_cmd
            if virtualenv_cmd == 'auto':
                import os
                import shlex

                venv_path = os.environ.get('VIRTUAL_ENV', '')
                if venv_path:
                    virtualenv_cmd = 'source ' + shlex.quote(
                        str(ub.Path(venv_path) / 'bin/activate')
                    )
                else:
                    virtualenv_cmd = None
            if virtualenv_cmd:
                queue.add_preamble_command(virtualenv_cmd)
        return queue

    def run_queue(
        config,
        queue: 'cmd_queue.Queue',
        print_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Execute a queue with options based on this config.

        Args:
            queue (cmd_queue.Queue): queue to run / report
            print_kwargs (None | Dict):
        """
        print_thresh = 30
        if config['print_commands'] == 'auto':
            if len(queue) < print_thresh:
                config['print_commands'] = 1
            else:
                print(
                    f'More than {print_thresh} jobs, skip queue.print_commands. '
                    'If you want to see them explicitly specify print_commands=1'
                )
                config['print_commands'] = 0

        if config['print_queue'] == 'auto':
            if len(queue) < print_thresh:
                config['print_queue'] = 1
            else:
                print(
                    f'More than {print_thresh} jobs, skip queue.print_graph. '
                    'If you want to see them explicitly specify print_queue=1'
                )
                config['print_queue'] = 0

        if config.print_commands:
            if print_kwargs is None:
                print_kwargs = {}
            queue.print_commands(**print_kwargs)

        if config.print_queue:
            queue.print_graph(vertical_chains=True)

        if config.run:
            queue.run(
                with_textual=config.with_textual,
                other_session_handler=config.other_session_handler,
                monitor=config.monitor,
                **kwargs,
            )
