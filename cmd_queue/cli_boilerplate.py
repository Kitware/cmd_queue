"""
This file defines a helper scriptconfig base config that can be used to help
make cmd_queue CLIs so cmd_queue options are standardized and present at the
top level.

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
import scriptconfig as scfg
import ubelt as ub


__docstubs__ = """
import cmd_queue
"""


class CMDQueueConfig(scfg.DataConfig):
    """
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
    run = scfg.Value(False, isflag=True, help='if False, only prints the commands, otherwise executes them', group='cmd-queue')

    backend = scfg.Value('tmux', help=('The cmd_queue backend. Can be tmux, slurm, or serial'), group='cmd-queue')

    queue_name = scfg.Value(None, help='overwrite the default queue name', group='cmd-queue')

    print_commands = scfg.Value('auto', isflag=True, help='enable / disable rprint before exec', group='cmd-queue')

    print_queue = scfg.Value('auto', isflag=True, help='print the cmd queue DAG', group='cmd-queue')

    with_textual = scfg.Value('auto', isflag=True, help='setting for cmd-queue monitoring', group='cmd-queue')

    other_session_handler = scfg.Value('ask', help='for tmux backend only. How to handle conflicting sessions. Can be ask, kill, or ignore, or auto', group='cmd-queue')

    virtualenv_cmd = scfg.Value(None, type=str, help=ub.paragraph(
        '''
        Command to start the appropriate virtual environment if your bashrc
        does not start it by default.'''), group='cmd-queue')

    tmux_workers = scfg.Value(8, help='number of tmux workers in the queue for the tmux backend', group='cmd-queue')

    slurm_options = scfg.Value(None, help=ub.paragraph(
        '''
        if the backend is slurm, provide a YAML dictionary for things like
        partition / etc...
        '''), group='cmd-queue')

    def __post_init__(self):
        from cmd_queue.util.util_yaml import Yaml
        self.slurm_options = Yaml.coerce(self.slurm_options) or {}

    def create_queue(config, **kwargs):
        """
        Create an empty queue based on options specified in this config

        Args:
            **kwargs: extra args passed to cmd_queue.Queue.create

        Returns:
            cmd_queue.Queue
        """
        import cmd_queue
        queuekw = {}
        if config.backend == 'slurm':
            queuekw.update(config.slurm_options)
        elif config.backend == 'tmux':
            queuekw.update({
                'size': config.tmux_workers,
            })
        queuekw.update(kwargs)
        if 'name' not in queuekw:
            queuekw['name'] = config.queue_name
        queue = cmd_queue.Queue.create(
            backend=config.backend,
            **queuekw)
        if config.virtualenv_cmd:
            queue.add_header_command(config.virtualenv_cmd)
        return queue

    def run_queue(config, queue, print_kwargs=None, **kwargs):
        """
        Execute a queue with options based on this config.

        Args:
            queue (cmd_queue.Queue): queue to run / report
            print_kwargs (None | Dict):
        """
        import cmd_queue
        queue: cmd_queue.Queue
        print_thresh = 30
        if config['print_commands'] == 'auto':
            if len(queue) < print_thresh:
                config['print_commands'] = 1
            else:
                print(f'More than {print_thresh} jobs, skip queue.print_commands. '
                      'If you want to see them explicitly specify print_commands=1')
                config['print_commands'] = 0

        if config['print_queue'] == 'auto':
            if len(queue) < print_thresh:
                config['print_queue'] = 1
            else:
                print(f'More than {print_thresh} jobs, skip queue.print_graph. '
                      'If you want to see them explicitly specify print_queue=1')
                config['print_queue'] = 0

        if config.print_commands:
            if print_kwargs is None:
                print_kwargs = {}
            queue.print_commands(**print_kwargs)

        if config.print_queue:
            queue.print_graph(vertical_chains=True)

        if config.run:
            queue.run(with_textual=config.with_textual,
                      other_session_handler=config.other_session_handler,
                      **kwargs)
