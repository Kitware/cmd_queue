r"""
Work in progress. The idea is to provide a TMUX queue and a SLURM queue that
provide a common high level API, even though functionality might diverge, the
core functionality of running processes asynchronously should be provided.

Notes:
    # Installing and configuring SLURM
    See git@github.com:Erotemic/local.git init/setup_slurm.sh
    Or ~/local/init/setup_slurm.sh in my local checkout

    SUBMIT COMMANDS WILL USE /bin/sh by default, not sure how to fix that
    properly. There are workarounds though.


CommandLine:
   xdoctest -m cmd_queue.slurm_queue __doc__

Example:
    >>> from cmd_queue.slurm_queue import *  # NOQA
    >>> dpath = ub.Path.appdir('slurm_queue/tests')
    >>> queue = SlurmQueue()
    >>> job0 = queue.submit(f'echo "here we go"', name='root job')
    >>> job1 = queue.submit(f'mkdir -p {dpath}', depends=[job0])
    >>> job2 = queue.submit(f'echo "result=42" > {dpath}/test.txt ', depends=[job1])
    >>> job3 = queue.submit(f'cat {dpath}/test.txt', depends=[job2])
    >>> queue.print_commands()
    >>> # xdoctest: +REQUIRES(--run)
    >>> queue.run()
    >>> # Can read the output of jobs after they are done.
    >>> for job in queue.jobs:
    >>>     print('-----------------')
    >>>     print(f'job.name={job.name}')
    >>>     if job.output_fpath.exists():
    >>>         print(job.output_fpath.read_text())
    >>>     else:
    >>>         print('output does not exist')
"""
import ubelt as ub

from cmd_queue import base_queue  # NOQA
from cmd_queue.util import util_tags


try:
    from functools import cache  # Python 3.9+ only
except ImportError:
    from ubelt import memoize as cache


@cache
def _unit_registery():
    import sys
    if sys.version_info[0:2] == (3, 9):
        # backwards compatability support for numpy 2.0 and pint on cp39
        try:
            import numpy as np
        except ImportError:
            ...
        else:
            if not np.__version__.startswith('1.'):
                np.cumproduct = np.cumprod
    import pint
    reg = pint.UnitRegistry()
    return reg


def _coerce_mem_megabytes(mem):
    """
    Transform input into an integer representing amount of megabytes.

    Args:
        mem (int | str): integer number of megabytes or a parseable string

    Returns:
        int: number of megabytes

    Example:
        >>> # xdoctest: +REQUIRES(module:pint)
        >>> from cmd_queue.slurm_queue import *  # NOQA
        >>> print(_coerce_mem_megabytes(30602))
        >>> print(_coerce_mem_megabytes('4GB'))
        >>> print(_coerce_mem_megabytes('32GB'))
        >>> print(_coerce_mem_megabytes('300000000 bytes'))
    """
    if isinstance(mem, int):
        assert mem > 0
    elif isinstance(mem, str):
        reg = _unit_registery()
        mem = reg.parse_expression(mem)
        mem = int(mem.to('megabytes').m)
    else:
        raise TypeError(type(mem))
    return mem


# List of extra keys that can be specified as key/value pairs in sbatch args
# These are acceptable kwargs for SlurmQueue.__init__ and SlurmQueue.submit
__dev__ = r"""
    # Script to build the modifier list

    import ubelt as ub
    import re
    b = xdev.regex_builder.RegexBuilder.coerce('python')

    blocklist = {'job_name', 'output', 'dependency', 'begin'}

    keyval_pat = re.compile(r'--([\w-]+)=')
    text = ub.cmd('sbatch --help')['out']
    lines = ub.oset()
    for key in keyval_pat.findall(text):
        lines.append(key.replace('-', '_'))
    print(ub.urepr(list(lines - blocklist)))


    blocklist = {'mem', 'version', 'help', 'usage'}
    flag_pat = re.compile(r'--([\w-]+) ')
    lines = ub.oset()
    for key in flag_pat.findall(text):
        lines.append(key.replace('-', '_'))
    print(ub.urepr(list(lines - blocklist)))
"""

SLURM_SBATCH_KVARGS = [
    'array',
    'account',
    'bb',
    'bbf',
    # 'begin',
    'comment',
    'cpu_freq',
    'cpus_per_task',
    # 'dependency',
    'deadline',
    'delay_boot',
    'chdir',
    'error',
    'export_file',
    'gid',
    'gres',
    'gres_flags',
    'input',
    # 'job_name',
    'licenses',
    'clusters',
    'distribution',
    'mail_type',
    'mail_user',
    'mcs_label',
    'ntasks',
    'ntasks_per_node',
    'nodes',
    # 'output',
    'partition',
    'power',
    'priority',
    'profile',
    'qos',
    'core_spec',
    'signal',
    'switches',
    'thread_spec',
    'time',
    'time_min',
    'uid',
    'wckey',
    'cluster_constraint',
    'constraint',
    'nodefile',
    'mem',
    'mincpus',
    'reservation',
    'tmp',
    'nodelist',
    'exclude',
    'mem_per_cpu',
    'sockets_per_node',
    'cores_per_socket',
    'threads_per_core',
    'extra_node_info',
    'ntasks_per_core',
    'ntasks_per_socket',
    'hint',
    'mem_bind',
    'cpus_per_gpu',
    'gpus',
    'gpu_bind',
    'gpu_freq',
    'gpus_per_node',
    'gpus_per_socket',
    'gpus_per_task',
    'mem_per_gpu',
]

SLURM_SBATCH_FLAGS = [
    'get_user_env',
    'hold',
    'ignore_pbs',
    'no_kill',
    'container',
    'no_requeue',
    'overcommit',
    'parsable',
    'quiet',
    'reboot',
    'requeue',
    'oversubscribe',
    'spread_job',
    'use_min_nodes',
    'verbose',
    'wait',
    'contiguous',
    'mem_per_cpu',
]


class SlurmJob(base_queue.Job):
    """
    Represents a slurm job that hasn't been submitted yet

    Example:
        >>> # xdoctest: +REQUIRES(module:pint)
        >>> from cmd_queue.slurm_queue import *  # NOQA
        >>> self = SlurmJob('python -c print("hello world")', 'hi', cpus=5, gpus=1, mem='10GB')
        >>> command = self._build_sbatch_args()
        >>> print('command = {!r}'.format(command))
        >>> self = SlurmJob('python -c print("hello world")', 'hi', cpus=5, gpus=1, mem='10GB', depends=[self])
        >>> command = self._build_command()
        >>> print(command)
    """
    def __init__(self, command, name=None, output_fpath=None, depends=None,
                 cpus=None, gpus=None, mem=None, begin=None, shell=None,
                 tags=None, **kwargs):
        super().__init__()
        if name is None:
            import uuid
            name = 'job-' + str(uuid.uuid4())
        if depends is not None and not ub.iterable(depends):
            depends = [depends]
        self.unused_kwargs = kwargs
        self.command = command
        self.name = name
        self.output_fpath = output_fpath
        self.depends = depends
        self.cpus = cpus
        self.gpus = gpus
        self.mem = mem
        self.begin = begin
        self.shell = shell
        self.tags = util_tags.Tags.coerce(tags)
        # Extra arguments for sbatch
        self._sbatch_kvargs = ub.udict(kwargs) & SLURM_SBATCH_KVARGS
        self._sbatch_flags = ub.udict(kwargs) & SLURM_SBATCH_FLAGS
        # if shell not in {None, 'bash'}:
        #     raise NotImplementedError(shell)

        self.jobid = None  # only set once this is run (maybe)
        # --partition=community --cpus-per-task=5 --mem=30602 --gres=gpu:1

    def __nice__(self):
        return repr(self.command)

    def _build_command(self, jobname_to_varname=None):
        args = self._build_sbatch_args(jobname_to_varname=jobname_to_varname)
        return ' \\\n    '.join(args)

    def _build_sbatch_args(self, jobname_to_varname=None):
        sbatch_args = ['sbatch']
        if self.name:
            sbatch_args.append(f'--job-name="{self.name}"')
        if self.cpus:
            sbatch_args.append(f'--cpus-per-task={self.cpus}')
        if self.mem:
            mem = _coerce_mem_megabytes(self.mem)
            sbatch_args.append(f'--mem={mem}')
        if self.gpus and 'gres' not in self._sbatch_kvargs:
            ub.schedule_deprecation(
                'cmd_queue', name='gres', type='argument',
                migration=ub.paragraph(
                    '''
                    the handling of gres here is broken and will be changed in
                    the future. For now specify gres explicitly in
                    slurm_options or the kwargs for the queue.
                    '''),
                deprecate='now'
            )
            # NOTE: the handling of gres here is broken and will be changed in
            # the future. For now specify gres explicitly in slurm_options
            def _coerce_gres(gpus):
                if isinstance(gpus, str):
                    gres = gpus
                elif isinstance(gpus, int):
                    gres = f'gpu:{gpus}'
                elif isinstance(gpus, list):
                    gres = 'gpu:0'  # hack
                else:
                    raise TypeError(type(self.gpus))
                return gres
            gres = _coerce_gres(self.gpus)
            sbatch_args.append(f'--gres="{gres}"')
        if self.output_fpath:
            sbatch_args.append(f'--output="{self.output_fpath}"')

        for key, value in self._sbatch_kvargs.items():
            key = key.replace('_', '-')
            if value is not None:
                sbatch_args.append(f'--{key}="{value}"')

        for key, flag in self._sbatch_flags.items():
            if flag:
                key = key.replace('_', '-')
                sbatch_args.append(f'--{key}"')

        if self.depends:
            # TODO: other depends parts
            type_to_dependencies = {
                'afterok': [],
            }
            depends = self.depends if ub.iterable(self.depends) else [self.depends]

            for item in depends:
                if isinstance(item, SlurmJob):
                    jobid = item.jobid
                    if jobid is None and item.name:
                        if jobname_to_varname and item.name in jobname_to_varname:
                            jobid = '${%s}' % jobname_to_varname[item.name]
                        else:
                            jobid = f"$(squeue --noheader --format %i --name '{item.name}')"
                    type_to_dependencies['afterok'].append(jobid)
                else:
                    # if isinstance(item, int):
                    #     type_to_dependencies['afterok'].append(item)
                    # elif isinstance(item, str):
                    #     name = item
                    #     item = f"$(squeue --noheader --format %i --name '{name}')"
                    #     type_to_dependencies['afterok'].append(item)
                    # else:
                    raise TypeError(type(item))

            # squeue --noheader --format %i --name <JOB_NAME>
            depends_parts = []
            for type_, jobids in type_to_dependencies.items():
                if jobids:
                    part = ':'.join([str(j) for j in jobids])
                    depends_parts.append(f'{type_}:{part}')
            depends_part = ','.join(depends_parts)
            sbatch_args.append(f'"--dependency={depends_part}"')
            # Kills jobs too fast
            # sbatch_args.append('"--kill-on-invalid-dep=yes"')

        if self.begin:
            if isinstance(self.begin, int):
                sbatch_args.append(f'"--begin=now+{self.begin}"')
            else:
                sbatch_args.append(f'"--begin={self.begin}"')

        import shlex
        wrp_command = shlex.quote(self.command)

        if self.shell:
            wrp_command = shlex.quote(self.shell + ' -c ' + wrp_command)

        sbatch_args.append(f'--wrap {wrp_command}')
        return sbatch_args


class SlurmQueue(base_queue.Queue):
    """
    CommandLine:
       xdoctest -m cmd_queue.slurm_queue SlurmQueue

    Example:
        >>> from cmd_queue.slurm_queue import *  # NOQA
        >>> self = SlurmQueue()
        >>> job0 = self.submit('echo "hi from $SLURM_JOBID"')
        >>> job1 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job0])
        >>> job2 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job1])
        >>> job3 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job1, job2])
        >>> self.write()
        >>> self.print_commands()
        >>> # xdoctest: +REQUIRES(--run)
        >>> if not self.is_available():
        >>>     self.run()

    Example:
        >>> from cmd_queue.slurm_queue import *  # NOQA
        >>> self = SlurmQueue()
        >>> job0 = self.submit('echo "hi from $SLURM_JOBID"', begin=0)
        >>> job1 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job0])
        >>> job2 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job1])
        >>> job3 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job2])
        >>> job4 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job3])
        >>> job5 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job4])
        >>> job6 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job0])
        >>> job7 = self.submit('echo "hi from $SLURM_JOBID"', depends=[job5, job6])
        >>> self.write()
        >>> self.print_commands()
        >>> # xdoctest: +REQUIRES(--run)
        >>> if not self.is_available():
        >>>     self.run()

    Example:
        >>> from cmd_queue.slurm_queue import *  # NOQA
        >>> self = SlurmQueue(shell='/bin/bash')
        >>> self.add_header_command('export FOO=bar')
        >>> job0 = self.submit('echo "$FOO"')
        >>> job1 = self.submit('echo "$FOO"', depends=job0)
        >>> job2 = self.submit('echo "$FOO"')
        >>> job3 = self.submit('echo "$FOO"', depends=job2)
        >>> self.sync()
        >>> job4 = self.submit('echo "$FOO"')
        >>> self.sync()
        >>> job5 = self.submit('echo "$FOO"')
        >>> self.print_commands()
    """
    def __init__(self, name=None, shell=None, **kwargs):
        super().__init__()
        import uuid
        import time
        self.jobs = []
        if name is None:
            name = 'SQ'
        stamp = time.strftime('%Y%m%dT%H%M%S')
        self.unused_kwargs = kwargs
        self.queue_id = name + '-' + stamp + '-' + ub.hash_data(uuid.uuid4())[0:8]
        self.dpath = ub.Path.appdir('cmd_queue/slurm') / self.queue_id
        if 0:
            # hack for submission on different systems, probably dont want to
            # do this.
            self.dpath = self.dpath.shrinkuser(home='$HOME')

        self.log_dpath = self.dpath / 'logs'
        self.fpath = self.dpath / (self.queue_id + '.sh')
        self.shell = shell
        self.header_commands = []
        self.all_depends = None
        self._sbatch_kvargs = ub.udict(kwargs) & SLURM_SBATCH_KVARGS
        self._sbatch_flags = ub.udict(kwargs) & SLURM_SBATCH_FLAGS

    def __nice__(self):
        return self.queue_id

    @classmethod
    def _slurm_checks(cls):
        status = {}
        info = {}
        info['squeue_fpath'] = ub.find_exe('squeue')
        status['has_squeue'] = bool(info['squeue_fpath'])
        status['slurmd_running'] = False
        import psutil
        for p in psutil.process_iter():
            if p.name() == 'slurmd':
                status['slurmd_running'] = True
                info['slurmd_info'] = {
                    'pid': p.pid,
                    'name': p.name(),
                    'status': p.status(),
                    'create_time': p.create_time(),
                }
                break
        status['squeue_working'] = (ub.cmd('squeue')['ret'] == 0)

        sinfo = ub.cmd('sinfo --json')
        status['sinfo_working'] = False
        if sinfo['ret'] == 0:
            status['sinfo_working'] = True
            import json
            sinfo_out = json.loads(sinfo['out'])
            has_working_nodes = not all(
                node['state'] == 'down'
                for node in sinfo_out['nodes'])
            status['has_working_nodes'] = has_working_nodes

    @classmethod
    def is_available(cls):
        """
        Determines if we can run the slurm queue or not.
        """
        if ub.find_exe('squeue'):
            import psutil
            slurmd_running = any(p.name() == 'slurmd' for p in psutil.process_iter())
            if slurmd_running:
                squeue_working = (ub.cmd('squeue')['ret'] == 0)
                if squeue_working:
                    # Check if nodes are available or down
                    # note: the --json command is not available in
                    # slurm-wlm 19.05.5, but it is in slurm-wlm 21.08.5
                    sinfo_version_str = ub.cmd('sinfo --version').stdout.strip().split(' ')[1]
                    sinfo_major_version = int(sinfo_version_str.split('.')[0])
                    if sinfo_major_version < 21:
                        # Dont check in this case
                        return True
                    else:
                        sinfo = ub.cmd('sinfo --json')
                        if sinfo['ret'] == 0:
                            import json
                            sinfo_out = json.loads(sinfo['out'])
                            has_working_nodes = not all(
                                node['state'] == 'down'
                                for node in sinfo_out['nodes'])
                            if has_working_nodes:
                                return True
        return False

    def submit(self, command, **kwargs):
        name = kwargs.get('name', None)
        if name is None:
            name = kwargs['name'] = f'J{len(self.jobs):04d}-{self.queue_id}'
            # + '-job-{}'.format(len(self.jobs))
        if 'output_fpath' not in kwargs:
            kwargs['output_fpath'] = self.log_dpath / (name + '.sh')
        if self.shell is not None:
            kwargs['shell'] = kwargs.get('shell', self.shell)
        if self.all_depends:
            depends = kwargs.get('depends', None)
            if depends is None:
                depends = self.all_depends
            else:
                if not ub.iterable(depends):
                    depends = [depends]
                depends = self.all_depends + depends
            kwargs['depends'] = depends

        depends = kwargs.pop('depends', None)
        if depends is not None:
            # Resolve any strings to job objects
            if not ub.iterable(depends):
                depends = [depends]
            depends = [
                self.named_jobs[dep] if isinstance(dep, str) else dep
                for dep in depends]

        _kwargs = self._sbatch_kvargs | kwargs
        job = SlurmJob(command, depends=depends, **_kwargs)
        self.jobs.append(job)
        self.num_real_jobs += 1
        self.named_jobs[job.name] = job
        return job

    def add_header_command(self, command):
        self.header_commands.append(command)

    def order_jobs(self):
        import networkx as nx
        graph = self._dependency_graph()
        if 0:
            print(nx.forest_str(nx.minimum_spanning_arborescence(graph)))
        new_order = []
        for node in nx.topological_sort(graph):
            job = graph.nodes[node]['job']
            new_order.append(job)
        return new_order

    def finalize_text(self, exclude_tags=None, **kwargs):
        exclude_tags = util_tags.Tags.coerce(exclude_tags)
        new_order = self.order_jobs()
        commands = []
        homevar = '$HOME'
        commands.append(f'mkdir -p "{self.log_dpath.shrinkuser(homevar)}"')
        jobname_to_varname = {}
        for job in new_order:
            if exclude_tags and exclude_tags.intersection(job.tags):
                continue
            # args = job._build_sbatch_args(jobname_to_varname)
            # command = ' '.join(args)
            command = job._build_command(jobname_to_varname)
            if self.header_commands:
                command = ' && '.join(self.header_commands + [command])
            if 1:
                varname = 'JOB_{:03d}'.format(len(jobname_to_varname))
                command = f'{varname}=$({command} --parsable)'
                jobname_to_varname[job.name] = varname
            commands.append(command)
        self.jobname_to_varname = jobname_to_varname
        text = '\n'.join(commands)
        return text

    def run(self, block=True, system=False, **kw):
        if not self.is_available():
            raise Exception('slurm backend is not available')
        self.log_dpath.ensuredir()
        self.write()
        ub.cmd(f'bash {self.fpath}', verbose=3, check=True, system=system)
        if block:
            return self.monitor()

    def monitor(self, refresh_rate=0.4):
        """
        Monitor progress until the jobs are done
        """

        import time
        from rich.live import Live
        from rich.table import Table
        import io
        import pandas as pd
        jobid_history = set()

        num_at_start = None

        def update_status_table():
            nonlocal num_at_start
            # https://rich.readthedocs.io/en/stable/live.html
            info = ub.cmd('squeue --format="%i %P %j %u %t %M %D %R"')
            stream = io.StringIO(info['out'])
            df = pd.read_csv(stream, sep=' ')
            
            # Only include job names that this queue created
            job_names = [job.name for job in self.jobs]
            df = df[df['NAME'].isin(job_names)]
            jobid_history.update(df['JOBID'])

            num_running = (df['ST'] == 'R').sum()
            num_in_queue = len(df)
            total_monitored = len(jobid_history)

            HACK_KILL_BROKEN_JOBS = 1
            if HACK_KILL_BROKEN_JOBS:
                # For whatever reason using kill-on-invalid-dep
                # kills jobs too fast and not when they are in a dependency state not a
                # a never satisfied state. Killing these jobs here seems to fix
                # it.
                broken_jobs = df[df['NODELIST(REASON)'] == '(DependencyNeverSatisfied)']
                if len(broken_jobs):
                    for name in broken_jobs['NAME']:
                        ub.cmd(f'scancel --name="{name}"')

            if num_at_start is None:
                num_at_start = len(df)

            table = Table(*['num_running', 'num_in_queue', 'total_monitored', 'num_at_start'],
                          title='slurm-monitor')

            # TODO: determine if slurm has accounting on, and if we can
            # figure out how many jobs errored / passed

            table.add_row(
                f'{num_running}',
                f'{num_in_queue}',
                f'{total_monitored}',
                f'{num_at_start}',
            )

            finished = (num_in_queue == 0)
            return table, finished

        try:
            table, finished = update_status_table()
            refresh_rate = 0.4
            with Live(table, refresh_per_second=4) as live:
                while not finished:
                    time.sleep(refresh_rate)
                    table, finished = update_status_table()
                    live.update(table)
        except KeyboardInterrupt:
            from rich.prompt import Confirm
            flag = Confirm.ask('do you to kill the procs?')
            if flag:
                self.kill()

    def kill(self):
        cancel_commands = []
        for job in self.jobs:
            cancel_commands.append(f'scancel --name="{job.name}"')
        for cmd in cancel_commands:
            ub.cmd(cmd, verbose=2)

    def read_state(self):
        # Not possible to get full info, but we probably could do better than
        # this
        return {}

    def print_commands(self, *args, **kwargs):
        r"""
        Print info about the commands, optionally with rich

        Args:
            exclude_tags (List[str] | None):
                if specified exclude jobs submitted with these tags.

            style (str):
                can be 'colors', 'rich', or 'plain'

        CommandLine:
            xdoctest -m cmd_queue.slurm_queue SlurmQueue.print_commands

        Example:
            >>> from cmd_queue.slurm_queue import *  # NOQA
            >>> self = SlurmQueue('test-slurm-queue')
            >>> self.submit('echo hi 1')
            >>> self.submit('echo hi 2')
            >>> self.submit('echo boilerplate', tags='boilerplate')
            >>> self.print_commands(with_status=True)
            >>> print('\n\n---\n\n')
            >>> self.print_commands(with_status=0, exclude_tags='boilerplate')
        """
        return super().print_commands(*args, **kwargs)

    rprint = print_commands


SLURM_NOTES = r"""
This shows a few things you can do with slurm

# Queue a job in the background
mkdir -p "$HOME/.cache/slurm/logs"
sbatch --job-name="test_job1" --output="$HOME/.cache/slurm/logs/job-%j-%x.out" --wrap="python -c 'import sys; sys.exit(1)'"
sbatch --job-name="test_job2" --output="$HOME/.cache/slurm/logs/job-%j-%x.out" --wrap="echo 'hello'"

#ls $HOME/.cache/slurm/logs
cat "$HOME/.cache/slurm/logs/test_echo.log"

# Queue a job (and block until completed)
srun -c 2 -p priority --gres=gpu:1 echo "hello"
srun echo "hello"

# List jobs in the queue
squeue
squeue --format="%i %P %j %u %t %M %D %R"

# Show job with specific id (e.g. 6)
scontrol show job 6

# Cancel a job with a specific id
scancel 6

# Cancel all jobs from a user
scancel --user="$USER"

# You can setup complicated pipelines
# https://hpc.nih.gov/docs/job_dependencies.html

# Look at finished jobs
# https://ubccr.freshdesk.com/support/solutions/articles/5000686909-how-to-retrieve-job-history-and-accounting

# Jobs within since 3:30pm
sudo sacct --starttime 15:35:00

sudo sacct
sudo sacct --format="JobID,JobName%30,Partition,Account,AllocCPUS,State,ExitCode,elapsed,start"
sudo sacct --format="JobID,JobName%30,State,ExitCode,elapsed,start"


# SHOW ALL JOBS that ran within MinJobAge
scontrol show jobs


# State of each partitions
sinfo

# If the states of the partitions are in drain, find out the reason
sinfo -R

# For "Low socket*core*thre" FIGURE THIS OUT

# Undrain all nodes, first cancel all jobs
# https://stackoverflow.com/questions/29535118/how-to-undrain-slurm-nodes-in-drain-state
scancel --user="$USER"
scancel --state=PENDING
scancel --state=RUNNING
scancel --state=SUSPENDED

sudo scontrol update nodename=namek state=idle



# How to submit a batch job with a dependency

    sbatch --dependency=<type:job_id[:job_id][,type:job_id[:job_id]]> ...

    Dependency types:

    after:jobid[:jobid...]	job can begin after the specified jobs have started
    afterany:jobid[:jobid...]	job can begin after the specified jobs have terminated
    afternotok:jobid[:jobid...]	job can begin after the specified jobs have failed
    afterok:jobid[:jobid...]	job can begin after the specified jobs have run to completion with an exit code of zero (see the user guide for caveats).
    singleton	jobs can begin execution after all previously launched jobs with the same name and user have ended. This is useful to collate results of a swarm or to send a notification at the end of a swarm.




sbatch \
    --job-name="tester1" \
    --output="test-job-%j-%x.out" \
    --cpus-per-task=1 --mem=1000 --gres="gpu:1" \
    --gpu-bind "map_gpu:2,3" \
    --wrap="python -c \"import torch, os; print(os.getenv('CUDA_VISIBLE_DEVICES', 'x')) and torch.rand(1000).to(0)\""
squeue



References:
    https://stackoverflow.com/questions/74164136/slurm-accessing-stdout-stderr-location-of-a-completed-job


"""
