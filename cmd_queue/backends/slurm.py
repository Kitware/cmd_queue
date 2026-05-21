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

SeeAlso:
    * https://github.com/amq92/simple_slurm

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
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Union

import ubelt as ub

from cmd_queue import base_queue  # NOQA
from cmd_queue.util import util_tags

try:
    from functools import cache  # Python 3.9+ only
except ImportError:
    from ubelt import memoize as cache


@cache
def _unit_registery() -> Any:
    import sys

    if sys.version_info[0:2] == (3, 9):
        # backwards compatibility support for numpy 2.0 and pint on cp39
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


def _coerce_mem_megabytes(mem: Union[int, str]) -> int:
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

    def __init__(
        self,
        command: str,
        name: Optional[str] = None,
        output_fpath: Optional[Any] = None,
        depends: Optional[Iterable[base_queue.Job]] = None,
        cpus: Optional[Any] = None,
        gpus: Optional[Any] = None,
        mem: Optional[Any] = None,
        begin: Optional[Any] = None,
        shell: Optional[Any] = None,
        tags: Optional[Any] = None,
        preamble: List[str] | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        if name is None:
            import uuid

            name = 'job-' + str(uuid.uuid4())
        if depends is not None and not ub.iterable(depends):
            depends = [depends]  # type: ignore
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
        # ub.udict.__and__ accepts list-of-keys (dict-key intersection);
        # ty's stub typing for the operator only recognizes set/dict.
        self._sbatch_kvargs = ub.udict(kwargs) & SLURM_SBATCH_KVARGS  # ty: ignore[unsupported-operator]
        self._sbatch_flags = ub.udict(kwargs) & SLURM_SBATCH_FLAGS  # ty: ignore[unsupported-operator]
        self.preamble = preamble
        # if shell not in {None, 'bash'}:
        #     raise NotImplementedError(shell)

        self.jobid = None  # only set once this is run (maybe)
        # --partition=community --cpus-per-task=5 --mem=30602 --gres=gpu:1

    def __nice__(self) -> str:
        return repr(self.command)

    def _build_command(
        self,
        jobname_to_varname: Optional[Dict[str, str]] = None,
        global_preamble: Optional[List[str]] = None,
    ) -> str:
        args = self._build_sbatch_args(
            jobname_to_varname=jobname_to_varname,
            global_preamble=global_preamble,
        )
        return ' \\\n    '.join(args)

    def _build_sbatch_args(
        self,
        jobname_to_varname: Optional[Dict[str, str]] = None,
        global_preamble: Optional[List[str]] = None,
    ) -> List[str]:
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
                'cmd_queue',
                name='gres',
                type='argument',
                migration=ub.paragraph(
                    """
                    the handling of gres here is broken and will be changed in
                    the future. For now specify gres explicitly in
                    slurm_options or the kwargs for the queue.
                    """
                ),
                deprecate='now',
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
            depends = (
                self.depends if ub.iterable(self.depends) else [self.depends]
            )

            for item in depends:
                if isinstance(item, SlurmJob):
                    jobid = item.jobid
                    if jobid is None and item.name:
                        if (
                            jobname_to_varname
                            and item.name in jobname_to_varname
                        ):
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

        _preamble = []
        if global_preamble:
            _preamble.extend(global_preamble)
        if self.preamble:
            _preamble.append(self.preamble)

        if _preamble:
            wrp_command = shlex.quote(' && '.join(_preamble + [self.command]))  # ty: ignore[invalid-argument-type]
        else:
            wrp_command = shlex.quote(self.command)  # ty: ignore[invalid-argument-type]

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
        >>> self.add_preamble_command('export FOO=bar')
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

    def __init__(
        self,
        name: Optional[str] = None,
        shell: Optional[str] = None,
        preamble: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        import time
        import uuid

        self.jobs = []
        if name is None:
            name = 'SQ'
        self.name = name
        stamp = time.strftime('%Y%m%dT%H%M%S')
        self.unused_kwargs = kwargs
        self.queue_id = (
            name + '-' + stamp + '-' + ub.hash_data(uuid.uuid4())[0:8]
        )
        self.dpath = ub.Path.appdir('cmd_queue/slurm') / self.queue_id
        if 0:
            # hack for submission on different systems, probably dont want to
            # do this.
            self.dpath = self.dpath.shrinkuser(home='$HOME')

        self.log_dpath = self.dpath / 'logs'
        self.fpath = self.dpath / (self.queue_id + '.sh')
        self.shell = shell
        self.preamble = []
        self.all_depends = None
        # ub.udict.__and__ accepts list-of-keys (dict-key intersection);
        # ty's stub typing for the operator only recognizes set/dict.
        self._sbatch_kvargs = ub.udict(kwargs) & SLURM_SBATCH_KVARGS  # ty: ignore[unsupported-operator]
        self._sbatch_flags = ub.udict(kwargs) & SLURM_SBATCH_FLAGS  # ty: ignore[unsupported-operator]
        self._include_monitor_metadata = True
        self.jobid_fpath = None

        if preamble:
            self.add_preamble_command(preamble)

    def __nice__(self) -> str:
        return self.queue_id

    @staticmethod
    def _slurm_checks() -> None:
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
        status['squeue_working'] = ub.cmd('squeue')['ret'] == 0

        sinfo = ub.cmd('sinfo --json')
        status['sinfo_working'] = False
        if sinfo['ret'] == 0:
            import json

            status['sinfo_working'] = True
            # ub.cmd().stdout is typed ``str | bytes | None`` but returns
            # a populated str here (default ``output=True``).
            status['sinfo_version_str'] = (
                ub.cmd('sinfo --version').stdout.strip().split(' ')[1]  # ty: ignore[unresolved-attribute, invalid-argument-type]
            )
            sinfo_out = json.loads(sinfo['out'])
            nodes = sinfo_out['nodes']
            node_states = [node['state'] for node in nodes]
            has_working_nodes = not all(
                'down' in str(state).lower() for state in node_states
            )
            status['has_working_nodes'] = has_working_nodes

    @staticmethod
    def is_available() -> bool:
        """
        Determines if we can run the slurm queue or not.
        """
        if ub.find_exe('squeue'):
            import psutil

            slurmd_running = any(
                p.name() == 'slurmd' for p in psutil.process_iter()
            )
            if slurmd_running:
                squeue_working = ub.cmd('squeue')['ret'] == 0
                if squeue_working:
                    # Check if nodes are available or down
                    # note: the --json command is not available in
                    # slurm-wlm 19.05.5, but it is in slurm-wlm 21.08.5
                    sinfo_version_str = (
                        ub.cmd('sinfo --version').stdout.strip().split(' ')[1]  # ty: ignore[unresolved-attribute, invalid-argument-type]
                    )
                    sinfo_major_version = int(sinfo_version_str.split('.')[0])  # ty: ignore[invalid-argument-type]
                    if sinfo_major_version < 21:
                        # Dont check in this case
                        return True
                    else:
                        import json

                        # sinfo --json changed between v22 and v23
                        # https://github.com/SchedMD/slurm/blob/slurm-23.02/RELEASE_NOTES#L230
                        if sinfo_major_version >= 21:
                            sinfo = ub.cmd('sinfo --json')
                        else:
                            sinfo = ub.cmd('scontrol show nodes --json')
                        if sinfo['ret'] == 0:
                            sinfo_out = json.loads(sinfo['out'])
                            if 'nodes' in sinfo_out:
                                nodes = sinfo_out['nodes']
                            elif 'sinfo' in sinfo_out:
                                # on v23 this seems to be the output format.
                                items = sinfo_out['sinfo']
                                nodes = [item['node'] for item in items]

                            # FIXME: this might be an incorrect check on v22
                            # the v23 version seems different, but I don't have
                            # v22 setup anymore. Might not be worth supporting.
                            node_states = [node['state'] for node in nodes]
                            if sinfo_major_version > 21:
                                has_working_nodes = not all(
                                    'down' in str(state).lower()
                                    for state in node_states
                                )
                            else:
                                has_working_nodes = not all(
                                    'DOWN' in state for state in node_states
                                )
                            if has_working_nodes:
                                return True

        return False

    def submit(  # ty: ignore[invalid-method-override]
        self,
        command: str,
        preamble: Optional[Union[str, List[str]]] = None,
        **kwargs: Any,
    ) -> SlurmJob:
        """
        Submit a command to this slurm queue

        Args:
            command (str): command line to execute.
            preamble (str | List[str] | None):
                job specific setup steps(s) to execute before the command
            **kwargs:
                name (str | None): name of job
                shell (str | None): shell to use, defaults to bash
                depends (str | List[str] | None): name of jobs to depend on
                **slurm_options:see SLURM_SBATCH_KVARGS and SLURM_SBATCH_FLAGS

        Returns:
            SlurmJob
        """
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
                for dep in depends
            ]

        _kwargs = self._sbatch_kvargs | kwargs
        job = SlurmJob(command, depends=depends, preamble=preamble, **_kwargs)
        self.jobs.append(job)
        self.num_real_jobs += 1
        # job.name is always populated above, but ty sees ``str | None``.
        self.named_jobs[job.name] = job  # ty: ignore[invalid-assignment]
        return job

    def order_jobs(self) -> List[SlurmJob]:
        """
        Get a topological sorting of the jobs in this DAG.

        Returns:
            List[SlurmJob]: ordered jobs
        """
        import networkx as nx

        graph = self._dependency_graph()
        if 0:
            print(nx.forest_str(nx.minimum_spanning_arborescence(graph)))
        new_order = []
        for node in nx.topological_sort(graph):
            job = graph.nodes[node]['job']
            new_order.append(job)
        return new_order

    def finalize_text(
        self, exclude_tags: Optional[Any] = None, **kwargs: Any
    ) -> str:
        """
        Serialize the state of the queue into a bash script.

        Returns:
            str
        """
        # generating the slurm bash script is straightforward because slurm
        # will take of the hard stuff (like scheduling) for us.  we just need
        # to effectively encode the DAG as a list of sbatch commands.
        exclude_tags = util_tags.Tags.coerce(exclude_tags)
        new_order = self.order_jobs()
        commands = []
        homevar = '$HOME'
        commands.append(f'mkdir -p "{self.log_dpath.shrinkuser(homevar)}"')
        jobname_to_varname = {}
        global_preamble = self.preamble
        for job in new_order:
            if exclude_tags and exclude_tags.intersection(job.tags):
                continue
            # args = job._build_sbatch_args(jobname_to_varname)
            # command = ' '.join(args)
            command = job._build_command(
                jobname_to_varname, global_preamble=global_preamble
            )
            if 1:
                varname = 'JOB_{:03d}'.format(len(jobname_to_varname))
                command = f'{varname}=$({command} --parsable)'
                jobname_to_varname[job.name] = varname
            commands.append(command)
        self.jobname_to_varname = jobname_to_varname

        self._include_monitor_metadata = True
        if self._include_monitor_metadata:
            # Build a command to dump the job-ids for this queue to disk to
            # allow us to track them in the monitor.
            from cmd_queue.util import util_bash

            json_fmt_parts = [
                (job_varname, '%s', '$' + job_varname)
                for job_varname in self.jobname_to_varname.values()
            ]
            self.jobid_fpath = self.fpath.augment(ext='.jobids.json')
            command = util_bash.bash_json_dump(json_fmt_parts, self.jobid_fpath)
            commands.append(command)

        text = '\n'.join(commands)
        return text

    def run(
        self,
        block: bool = True,
        system: bool = False,
        onfail: str = '',
        onexit: str = '',
        monitor: str = 'hybrid',
        **kw: Any,
    ) -> Optional[Any]:
        """
        Execute the queue.

        Args:
            monitor (str): where the live status UI runs while
                ``block=True``.

                * ``'hybrid'`` (default): inline UI in the current
                  shell *and* a detached ``cmd_queue monitor`` tmux
                  session you can press ``[a]`` to attach to. The
                  side session is killed when the inline monitor
                  exits. Falls back to ``'inline'`` when tmux is
                  unavailable.
                * ``'inline'``: renders only in the current shell.
                * ``'tmux'``: spawns ``cmd_queue monitor`` only in a
                  detached tmux session so the UI survives the
                  calling shell closing — useful for slurm jobs
                  whose workers run on the cluster long after the
                  submit shell might be gone.
                * ``'none'``: skips the UI but still blocks when
                  ``block=True``.
        """
        if not self.is_available():
            raise Exception('slurm backend is not available')
        self.log_dpath.ensuredir()
        self.write()
        manifest_path = self._write_monitor_manifest()
        ub.cmd(f'bash {self.fpath}', verbose=3, check=True, system=system)
        if not block:
            return None
        if monitor == 'inline':
            return self.monitor(onfail=onfail, onexit=onexit)
        if monitor == 'hybrid':
            from cmd_queue.util.util_tmux import tmux as _tmux

            side_session = None
            if ub.find_exe('tmux'):
                extra_args = []
                if onfail:
                    extra_args.append(f'--onfail={onfail}')
                if onexit:
                    extra_args.append(f'--onexit={onexit}')
                side_session = f'cmdq-monitor-{self.queue_id}'
                from rich import print as rich_print

                rich_print(
                    f'[dim]Spawned attachable monitor in tmux session[/dim] '
                    f'{side_session} [dim](press [a] to attach)[/dim]'
                )
                _tmux.spawn_monitor_session(
                    session_name=side_session,
                    manifest_path=manifest_path,
                    attach=False,
                    verbose=0,
                    extra_args=extra_args,
                )
            else:
                import warnings

                warnings.warn(
                    "monitor='hybrid' requested but tmux not found; "
                    'falling back to inline-only monitor.'
                )
            try:
                return self.monitor(
                    onfail=onfail,
                    onexit=onexit,
                    side_session=side_session,
                )
            finally:
                if side_session and _tmux.has_session(side_session):
                    _tmux.kill_session(side_session, verbose=0)
        if monitor == 'none':
            from rich import print as rich_print

            rich_print(
                '[bold]Queue running detached.[/bold] '
                f'Reattach with: cmd_queue monitor --manifest={manifest_path}'
            )
            return None
        if monitor == 'tmux':
            if not ub.find_exe('tmux'):
                import warnings

                warnings.warn(
                    "monitor='tmux' requested but tmux not found; "
                    'falling back to inline monitor.'
                )
                return self.monitor(onfail=onfail, onexit=onexit)
            from cmd_queue.util.util_tmux import tmux as _tmux

            extra_args = []
            if onfail:
                extra_args.append(f'--onfail={onfail}')
            if onexit:
                extra_args.append(f'--onexit={onexit}')
            session_name = f'cmdq-monitor-{self.queue_id}'
            from rich import print as rich_print

            rich_print(
                f'[bold]Launching monitor in tmux session[/bold] {session_name}'
            )
            _tmux.spawn_monitor_session(
                session_name=session_name,
                manifest_path=manifest_path,
                attach=False,
                verbose=0,
                extra_args=extra_args,
            )
            job_names = {job.name for job in self.jobs}

            def _is_finished() -> bool:
                if not job_names:
                    return True
                info = ub.cmd('squeue --format="%j"')
                still_queued = {
                    line.strip()
                    for line in info['out'].splitlines()
                    if line.strip() in job_names
                }
                return not still_queued

            _tmux.block_with_attach_prompt(
                session_name=session_name,
                is_finished_fn=_is_finished,
                refresh_rate=5.0,
                label=f'queue {self.name or self.queue_id}',
            )
            return None
        raise ValueError(
            "monitor must be one of 'hybrid', 'inline', 'tmux', 'none'; "
            f'got {monitor!r}'
        )

    def monitor(
        self,
        refresh_rate: float = 0.4,
        # TODO: use or document as unused or make the signature sane across
        # clsses
        with_textual: str | bool = 'auto',
        onfail: str = '',
        onexit: str = '',
        side_session: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Monitor progress until the jobs are done.

        Owns post-run cleanup so that whether the monitor runs inline or
        in a separate process (tmux monitor backend, ``cmd_queue
        monitor`` CLI), the same finalization happens.

        Args:
            onfail (str): if ``'kill'``, scancel the queue's jobs after
                the monitor exits when there are failures. Slurm has no
                tmux-style sessions to clean up on success, so this only
                fires on failure.
            onexit (str): currently unused for slurm (kept for API
                parity with the tmux backend).

        CommandLine:
            xdoctest -m cmd_queue.slurm_queue SlurmQueue.monitor --dev --run

        Example:
            >>> # xdoctest: +REQUIRES(--dev)
            >>> from cmd_queue.slurm_queue import *  # NOQA
            >>> dpath = ub.Path.appdir('slurm_queue/tests/test-slurm-failed-monitor')
            >>> queue = SlurmQueue()
            >>> job0 = queue.submit(f'echo "here we go"', name='job0')
            >>> job1 = queue.submit(f'echo "this job will pass, allowing dependencies to run" && true', depends=[job0])
            >>> job2 = queue.submit(f'echo "this job will run and pass" && sleep 10 && true', depends=[job1])
            >>> job3 = queue.submit(f'echo "this job will run and fail" && false', depends=[job1])
            >>> job4 = queue.submit(f'echo "this job will fail, preventing dependencies from running" && false', depends=[job0])
            >>> job5 = queue.submit(f'echo "this job will never run" && true', depends=[job4])
            >>> job6 = queue.submit(f'echo "this job will also never run" && false', depends=[job4])
            >>> queue.print_commands()
            >>> # xdoctest: +REQUIRES(--run)
            >>> queue.run()
        """

        import io

        import pandas as pd
        from rich.table import Table

        from cmd_queue.backends.tmux import (
            _attach_hint_renderable,
            _run_live_with_attach,
        )

        jobid_history = set()

        num_at_start = None

        job_status_table = None
        if self.jobid_fpath is not None:

            class UnableToMonitor(Exception): ...

            try:
                import json

                if not self.jobid_fpath.exists():
                    raise UnableToMonitor
                jobid_lut = json.loads(self.jobid_fpath.read_text())
                job_status_table = [
                    {
                        'job_varname': job_varname,
                        'job_id': job_id,
                        'status': 'unknown',
                        'needs_update': True,
                    }
                    for job_varname, job_id in jobid_lut.items()
                ]
            except UnableToMonitor:
                print('ERROR: Unable to monitors jobids')

        def update_jobid_status():
            import rich

            assert job_status_table is not None
            for row in job_status_table:
                if row['needs_update']:
                    job_id = row['job_id']
                    out = ub.cmd(f'scontrol show job "{job_id}"')
                    # ub.cmd().stdout is typed ``str | bytes | None`` but
                    # is always a str here.
                    info = parse_scontrol_output(out.stdout)  # ty: ignore[invalid-argument-type]
                    row['JobState'] = info['JobState']
                    row['ExitCode'] = info.get('ExitCode', None)
                    # https://slurm.schedmd.com/job_state_codes.html
                    if info['JobState'].startswith('FAILED'):
                        row['status'] = 'failed'
                        rich.print(f'[red] Failed job: {info["JobName"]}')
                        if info['StdErr'] == info['StdOut']:
                            rich.print(f'[red]  * Logs: {info["StdErr"]}')
                        else:
                            rich.print(f'[red] StdErr: {info["StdErr"]}')
                            rich.print(f'[red] StdOut: {info["StdOut"]}')
                        row['needs_update'] = False
                    elif info['JobState'].startswith('CANCELLED'):
                        rich.print(f'[yellow] Skip job: {info["JobName"]}')
                        row['status'] = 'skipped'
                        row['needs_update'] = False
                    elif info['JobState'].startswith('COMPLETED'):
                        rich.print(f'[green] Completed job: {info["JobName"]}')
                        row['status'] = 'passed'
                        row['needs_update'] = False
                    elif info['JobState'].startswith('RUNNING'):
                        row['status'] = 'running'
                    elif info['JobState'].startswith('PENDING'):
                        row['status'] = 'pending'
                    else:
                        row['status'] = 'unknown'
            # print(f'job_status_table = {ub.urepr(job_status_table, nl=1)}')

        def update_status_table():
            nonlocal num_at_start

            # TODO: move this block into into the version where job status
            # table is not available, and reimplement it for the per-job style
            # of query. The reason we have it out here now is because we need
            # to implement the HACK_KILL_BROKEN_JOBS in the alternate case.
            if True:
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
                    broken_jobs = df[
                        df['NODELIST(REASON)'] == '(DependencyNeverSatisfied)'
                    ]
                    if len(broken_jobs):
                        for name in broken_jobs['NAME']:
                            ub.cmd(f'scancel --name="{name}"')

            if num_at_start is None:
                num_at_start = len(df)

            if job_status_table is not None:
                update_jobid_status()
                state = ub.dict_hist(
                    [row['status'] for row in job_status_table]
                )
                state.setdefault('passed', 0)
                state.setdefault('failed', 0)
                state.setdefault('skipped', 0)
                state.setdefault('pending', 0)
                state.setdefault('unknown', 0)
                state.setdefault('running', 0)
                state['total'] = len(job_status_table)

                state['other'] = state['total'] - (
                    state['passed']
                    + state['failed']
                    + state['skipped']
                    + state['running']
                    + state['pending']
                )
                pass_color = ''
                fail_color = ''
                skip_color = ''
                finished = (
                    state['pending'] + state['unknown'] + state['running'] == 0
                )
                if state['failed'] > 0:
                    fail_color = '[red]'
                if state['skipped'] > 0:
                    skip_color = '[yellow]'
                if finished:
                    pass_color = '[green]'

                header = [
                    'passed',
                    'failed',
                    'skipped',
                    'running',
                    'pending',
                    'other',
                    'total',
                ]
                row_values = [
                    f'{pass_color}{state["passed"]}',
                    f'{fail_color}{state["failed"]}',
                    f'{skip_color}{state["skipped"]}',
                    f'{state["running"]}',
                    f'{state["pending"]}',
                    f'{state["other"]}',
                    f'{state["total"]}',
                ]
            else:
                # TODO: determine if slurm has accounting on, and if we can
                # figure out how many jobs errored / passed
                header = [
                    'num_running',
                    'num_in_queue',
                    'total_monitored',
                    'num_at_start',
                ]
                row_values = [
                    f'{num_running}',
                    f'{num_in_queue}',
                    f'{total_monitored}',
                    f'{num_at_start}',
                ]
                # row_values.append(str(state.get('FAIL', 0)))
                # row_values.append(str(state.get('SKIPPED', 0)))
                # row_values.append(str(state.get('PENDING', 0)))
                finished = num_in_queue == 0

            table = Table(*header, title='slurm-monitor')

            table.add_row(*row_values)

            return table, finished

        agg_state: Dict[str, Any] = {}

        def _update_agg_state() -> None:
            if job_status_table is None:
                return
            counts = ub.dict_hist([row['status'] for row in job_status_table])
            for key in ('passed', 'failed', 'skipped'):
                agg_state[key] = counts.get(key, 0)
            agg_state['total'] = len(job_status_table)

        try:
            import sys

            from rich.console import Group

            def _build_renderable() -> Any:
                table, finished = update_status_table()
                hint = (
                    _attach_hint_renderable(side_session)
                    if side_session
                    else None
                )
                renderable = Group(table, hint) if hint is not None else table
                # The slurm Live loop tracks completion via a separate
                # variable than tmux; agg_state is updated post-loop.
                return renderable, finished, None

            refresh_rate = 0.4
            use_keys = side_session is not None and sys.stdin.isatty()
            _run_live_with_attach(
                build_renderable=_build_renderable,
                refresh_rate=refresh_rate,
                side_session=side_session if use_keys else None,
            )
            _update_agg_state()
        except KeyboardInterrupt:
            from rich.prompt import Confirm

            flag = Confirm.ask('do you to kill the procs?')
            if flag:
                self.kill()
            return agg_state

        # Slurm has no idle sessions to clean up on success, so onfail='kill'
        # only fires when there are observed failures.
        if onfail == 'kill' and agg_state.get('failed'):
            self.kill()
        return agg_state

    def kill(self) -> None:
        cancel_commands = []
        for job in self.jobs:
            cancel_commands.append(f'scancel --name="{job.name}"')
        for cmd in cancel_commands:
            ub.cmd(cmd, verbose=2)

    def read_state(self) -> Dict[str, Any]:
        # Not possible to get full info, but we probably could do better than
        # this
        return {}

    def _build_monitor_manifest(self) -> Dict[str, Any]:
        """Snapshot enough state for an out-of-process monitor to reattach."""
        return {
            'backend': 'slurm',
            'name': self.name or self.queue_id,
            'queue_id': self.queue_id,
            'dpath': str(self.dpath),
            'fpath': str(self.fpath),
            'jobid_fpath': str(self.jobid_fpath) if self.jobid_fpath else None,
            'job_names': [job.name for job in self.jobs],
        }

    def _write_monitor_manifest(self) -> Any:
        """Persist the monitor manifest to ``<dpath>/monitor_manifest.json``."""
        from cmd_queue import monitor_manifest as mm

        path = mm.manifest_path_for_dpath(self.dpath)
        manifest = self._build_monitor_manifest()
        mm.write_manifest(manifest, path)
        # Register under both queue_id (always unique) and the user-supplied
        # name (when distinct) so `cmd_queue monitor <name-or-id>` finds it.
        mm.update_active_index(self.queue_id, path)
        if self.name and self.name != self.queue_id:
            mm.update_active_index(self.name, path)
        return path

    @classmethod
    def _from_manifest(cls, manifest: Dict[str, Any]) -> 'SlurmQueue':
        """Reconstruct a queue suitable for ``monitor()`` / ``kill()`` only."""
        self = cls.__new__(cls)
        base_queue.Queue.__init__(self)
        self.queue_id = manifest['queue_id']
        self.name = manifest.get('name', self.queue_id)
        self.dpath = ub.Path(manifest['dpath'])
        self.fpath = ub.Path(manifest['fpath'])
        self.log_dpath = self.dpath / 'logs'
        self.shell = None
        self.preamble = []
        self.all_depends = None
        self._sbatch_kvargs = ub.udict()
        self._sbatch_flags = ub.udict()
        self._include_monitor_metadata = False
        jobid_fpath = manifest.get('jobid_fpath')
        self.jobid_fpath = ub.Path(jobid_fpath) if jobid_fpath else None
        self.unused_kwargs = {}
        # The reconstructed jobs only need a name for kill() (scancel --name).
        self.jobs = [
            SlurmJob(command='', name=name)
            for name in manifest.get('job_names', [])
        ]
        return self

    def print_commands(self, *args: Any, **kwargs: Any) -> None:
        r"""
        Print info about the commands, optionally with rich

        Args:
            exclude_tags (List[str] | None):
                if specified exclude jobs submitted with these tags.

            style (str):
                can be 'colors', 'rich', or 'plain'

            **kwargs: extra backend-specific args passed to finalize_text

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


def parse_scontrol_output(output: str) -> dict:
    """
    Parses the output of `scontrol show job` into a dictionary.

    Example:
        from cmd_queue.slurm_queue import *  # NOQA
        # Example usage
        output = ub.codeblock(
            '''
            JobId=307 JobName=J0002-SQ-2025 with a space 0218T165929-9a50513a
               UserId=joncrall(1000) GroupId=joncrall(1000) MCS_label=N/A
               Priority=1 Nice=0 Account=(null) QOS=(null)
               JobState=COMPLETED Reason=None Dependency=(null)
               Requeue=1 Restarts=0 BatchFlag=1 Reboot=0 ExitCode=0:0
               RunTime=00:00:10 TimeLimit=365-00:00:00 TimeMin=N/A
               SubmitTime=2025-02-18T16:59:30 EligibleTime=2025-02-18T16:59:33
               AccrueTime=Unknown
               StartTime=2025-02-18T16:59:33 EndTime=2025-02-18T16:59:43 Deadline=N/A
               SuspendTime=None SecsPreSuspend=0 LastSchedEval=2025-02-18T16:59:33 Scheduler=Backfill
               Partition=priority AllocNode:Sid=localhost:215414
               ReqNodeList=(null) ExcNodeList=(null)
               NodeList=toothbrush
               BatchHost=toothbrush
               NumNodes=1 NumCPUs=2 NumTasks=1 CPUs/Task=1 ReqB:S:C:T=0:0:*:*
               ReqTRES=cpu=1,mem=120445M,node=1,billing=1
               AllocTRES=cpu=2,node=1,billing=2
               Socks/Node=* NtasksPerN:B:S:C=0:0:*:* CoreSpec=*
               MinCPUsNode=1 MinMemoryNode=0 MinTmpDiskNode=0
               Features=(null) DelayBoot=00:00:00
               OverSubscribe=OK Contiguous=0 Licenses=(null) Network=(null)
               Command=(null)
               WorkDir=/home/joncrall/code/cmd_queue
               StdErr="cmd_queue/slurm/SQ-2025021 with a space 8T165929-9a50513a/logs/J0002-SQ-20250218T165929-9a50513a.sh"
               StdIn=/dev/null
               StdOut="slurm/SQ-20 with and = 250218T165929-9a50513a/logs/J0002-SQ-20250218T165929-9a50513a.sh"
               Power=
             ''')
        parse_scontrol_output(output)
    """
    import re

    # These keys should be the last key on a line. They are allowed to contain
    # space and equal characters.
    special_keys = [
        'JobName',
        'WorkDir',
        'StdErr',
        'StdIn',
        'StdOut',
        'Command',
        'NodeList',
        'BatchHost',
        'Partition',
    ]
    patterns = '(' + '|'.join(f' {re.escape(k)}=' for k in special_keys) + ')'
    pat = re.compile(patterns)

    # Initialize dictionary to store parsed key-value pairs
    parsed_data = {}

    # Split the input into lines
    for line in output.splitlines():
        # First, check for special keys (those with spaces before the equal sign)
        match = pat.search(line)
        if match:
            # Special case: Key is a special key with a space
            startpos = match.start()
            leading_part = line[:startpos]
            special_part = line[startpos + 1 :]
            key, value = special_part.split('=', 1)
            parsed_data[key] = value.strip()
            line = leading_part

        # Now, handle the general case: split by spaces and then by "="
        line = line.strip()
        if line:
            parts = line.split(' ')
            for part in parts:
                key, value = part.split('=', 1)
                parsed_data[key] = value

    return parsed_data


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

# the implementation now lives under cmd_queue.backends.
