from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Union

import ubelt as ub


class DuplicateJobError(KeyError): ...


class UnknownBackendError(KeyError): ...


class Job(ub.NiceRepr):
    """
    Base class for a job
    """

    # The following attributes are produced by concrete subclasses
    # (BashJob, SlurmJob, AirflowJob). They are declared here so that
    # generic queue code that walks ``Job`` instances type-checks
    # against the base class without each subclass attribute being
    # flagged as unresolved.
    # ``bookkeeper`` is exposed as an int so backends can accumulate
    # counts; treated as bool elsewhere via truthiness.
    bookkeeper: int = 0
    tags: Any = None
    log: bool = False
    log_fpath: Any = None
    pass_fpath: Any = None
    fail_fpath: Any = None
    skip_fpath: Any = None
    stat_fpath: Any = None

    def __init__(
        self,
        command: Optional[str] = None,
        name: Optional[str] = None,
        depends: Optional[Iterable[Job]] = None,
        **kwargs: Any,
    ) -> None:
        # This is unused, should the slurm and bash job reuse this?
        if depends is not None and not ub.iterable(depends):
            depends = [depends]  # type: ignore
        self.name = name
        self.command = command
        self.depends = depends
        self.kwargs = kwargs

    def __nice__(self) -> str:
        return self.name or ''

    def finalize_text(self, *args: Any, **kwargs: Any) -> str:
        """Render this job to a bash snippet. Implemented by subclasses."""
        raise NotImplementedError


class Queue(ub.NiceRepr):
    """
    Base class for a queue.

    Use the ``create`` classmethod to make a concrete instance with an
    available backend.
    """

    def __init__(self) -> None:
        self.num_real_jobs: int = 0
        self.all_depends: Optional[List[Job]] = None
        self.named_jobs: Dict[str, Job] = {}
        self.preamble: List[str] = []
        self.jobs: List[Job] = []
        self.job_info_dpath: Any = None
        self.name: str = ''
        self.fpath: Any = None

    @property
    def header_commands(self) -> List[str]:
        return self.preamble

    def add_header_command(self, command: Union[str, List[str]]) -> None:
        ub.schedule_deprecation(
            modname='cmd_queue',
            name='add_header_command',
            type='function',
            migration='use preamble kwarg or add_preamble_command instead',
            deprecate='now',
        )
        self.add_preamble_command(command)

    def add_preamble_command(self, command: Union[str, List[str]]) -> None:
        if isinstance(command, list):
            self.preamble.extend(command)
        else:
            self.preamble.append(command)

    def change_backend(self, backend: str, **kwargs: Any) -> Queue:
        """
        Create a new version of this queue with a different backend.

        Currently metadata is not carried over. Submit an MR if you need this
        functionality.

        Example:
            >>> from cmd_queue import Queue
            >>> self = Queue.create(size=5, name='demo')
            >>> self.submit('echo "Hello World"', name='job1a')
            >>> self.submit('echo "Hello Revocable"', name='job1b')
            >>> self.submit('echo "Hello Crushed"', depends=['job1a'], name='job2a')
            >>> self.submit('echo "Hello Shadow"', depends=['job1b'], name='job2b')
            >>> self.submit('echo "Hello Excavate"', depends=['job2a', 'job2b'], name='job3')
            >>> self.submit('echo "Hello Barrette"', depends=[], name='jobX')
            >>> self.submit('echo "Hello Overwrite"', depends=['jobX'], name='jobY')
            >>> self.submit('echo "Hello Giblet"', depends=['jobY'], name='jobZ')
            >>> serial_backend = self.change_backend('serial')
            >>> tmux_backend = self.change_backend('tmux')
            >>> slurm_backend = self.change_backend('slurm')
            >>> airflow_backend = self.change_backend('airflow')
            >>> serial_backend.print_commands()
            >>> tmux_backend.print_commands()
            >>> slurm_backend.print_commands()
            >>> airflow_backend.print_commands()
        """
        new = Queue.create(backend=backend, **kwargs)
        for job_name, job in self.named_jobs.items():
            new_depends = []
            if job.depends:
                for dep in job.depends:
                    # named_jobs only contains non-None-named jobs by
                    # construction, but ``Job.name`` is typed Optional.
                    new_dep = new.named_jobs[dep.name]  # ty: ignore[invalid-argument-type]
                    new_depends.append(new_dep)
            # TODO: carry over metadata
            new.submit(job.command, depends=new_depends, name=job.name)  # ty: ignore[invalid-argument-type]
        return new

        for job in self.jobs:
            new.submit(job.commands)
            pass

    def __len__(self) -> int:
        return self.num_real_jobs

    def sync(self) -> Queue:
        """
        Mark that all future jobs will depend on the current sink jobs

        Returns:
            Queue:
                a reference to the queue (for chaining)
        """
        from cmd_queue import _graph

        # Find the jobs that nobody depends on.
        self.all_depends = _graph.sink_jobs(self.jobs)
        return self

    def write(self) -> Any:
        """
        Writes the underlying files that defines the queue for whatever program
        will ingest it to run it.
        """
        import os
        import stat

        text = self.finalize_text()
        self.fpath.parent.ensuredir()
        self.fpath.write_text(text)
        os.chmod(
            self.fpath,
            (
                stat.S_IXUSR
                | stat.S_IXGRP
                | stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IRGRP
                | stat.S_IWGRP
            ),
        )
        return self.fpath

    def submit(self, command: Union[str, Job], **kwargs: Any) -> Job:
        """
        Args:
            command (str | Job): The command to execute
            name: specify the name of the job
            **kwargs: passed to :class:`cmd_queue.serial_queue.BashJob`
        """
        # TODO: we could accept additional args here that modify how we handle
        # the command in the bash script we build (i.e. if the script is
        # allowed to fail or not)
        # self.commands.append(command)
        if 'info_dpath' not in kwargs:
            kwargs['info_dpath'] = self.job_info_dpath

        if isinstance(command, str):
            name = kwargs.get('name', None)
            if name is None:
                name = kwargs['name'] = self.name + '-job-{}'.format(
                    self.num_real_jobs
                )

            # TODO: make sure name is path safe.
            if ':' in name:
                raise ValueError('Name must be path-safe')

            from cmd_queue import _graph

            depends = kwargs.get('depends', None)
            depends = _graph.merge_sync_depends(self.all_depends, depends)
            kwargs['depends'] = depends
            depends = kwargs.pop('depends', None)
            if depends is not None:
                # Resolve any strings to job objects.
                try:
                    depends = _graph.resolve_dependency_refs(
                        depends, self.named_jobs
                    )
                except Exception:
                    print(
                        'self.named_jobs = {}'.format(
                            ub.urepr(self.named_jobs, nl=1)
                        )
                    )
                    raise
            from cmd_queue.backends.serial import BashJob

            job = BashJob(command, depends=depends, **kwargs)
        elif isinstance(command, Job):
            # Assume job is already a bash job
            job = command
        else:
            raise TypeError(type(command))
        self.jobs.append(job)

        try:
            if job.name in self.named_jobs:
                raise DuplicateJobError(f'duplicate key {job.name}')
        except Exception:
            raise

        # job.name is set by submit() above before this line, but ty
        # only sees ``Optional[str]`` from the Job base class.
        self.named_jobs[job.name] = job  # ty: ignore[invalid-assignment]

        if not job.bookkeeper:
            self.num_real_jobs += 1
        return job

    @classmethod
    def _backend_classes(cls):
        from cmd_queue import _registry

        return _registry.backend_classes()

    @classmethod
    def available_backends(cls) -> List[str]:
        lut = cls._backend_classes()
        available = [name for name, qcls in lut.items() if qcls.is_available()]
        return available

    @classmethod
    def create(cls, backend: str = 'serial', **kwargs: Any) -> Queue:
        """
        Main entry point to create a queue

        Args:
            **kwargs:
                environ (dict | None): environment variables
                name (str): queue name
                dpath (str): queue work directory
                gpus (int): number of gpus
                size (int): only for tmux queue, number of parallel queues
        """
        from cmd_queue import _registry

        try:
            return _registry.create_backend(backend, **kwargs)
        except _registry.UnknownBackendName:
            raise UnknownBackendError(backend)

    def write_network_text(
        self,
        reduced: bool = True,
        rich: Union[bool, str] = 'auto',
        vertical_chains: bool = False,
    ) -> None:
        # TODO: change rich to style
        try:
            import rich as rich_mod
        except ImportError:
            rich_mod = None  # type: ignore
        if rich == 'auto':
            rich = rich_mod is not None

        if rich:
            print_ = rich_mod.print
        else:
            print_ = print

        import networkx as nx

        graph = self._dependency_graph()
        if reduced:
            print_('\nGraph (reduced):')
            try:
                reduced_graph = nx.transitive_reduction(graph)
                nx.write_network_text(
                    reduced_graph,
                    path=print_,
                    end='',
                    vertical_chains=vertical_chains,
                )
            except Exception as ex:
                print_(f'ex={ex}')
            print_('\n')
        else:
            print_('\nGraph:')
            nx.write_network_text(
                graph, path=print_, end='', vertical_chains=vertical_chains
            )

    def print_commands(
        self,
        with_status: bool = False,
        with_gaurds: bool = False,
        with_locks: bool = True,
        exclude_tags: Optional[List[str]] = None,
        style: str = 'colors',
        **kwargs: Any,
    ) -> None:
        """
        Args:
            with_status (bool):
                tmux / serial only, show bash status boilerplate

            with_gaurds (bool):
                tmux / serial only, show bash guards boilerplate

            with_locks (bool | int):
                tmux, show tmux lock boilerplate

            exclude_tags (List[str] | None):
                if specified exclude jobs submitted with these tags.

            style (str):
                can be 'colors', 'rich', or 'plain'

            **kwargs: extra backend-specific args passed to finalize_text

        CommandLine:
            xdoctest -m cmd_queue.slurm_queue SlurmQueue.print_commands
            xdoctest -m cmd_queue.serial_queue SerialQueue.print_commands
            xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.print_commands
        """
        colors = kwargs.get('colors', None)
        if colors is not None:
            ub.schedule_deprecation(
                'cmd_queue',
                'colors',
                'arg',
                migration='use style="plain" | "rich" | "colors" instead',
                deprecate='now',
            )
            if not colors:
                style = 'plain'
        with_rich = kwargs.get('with_rich', None)
        if with_rich is not None:
            ub.schedule_deprecation(
                'cmd_queue',
                'with_rich',
                'arg',
                migration='use use style="plain" | "rich" | "colors" instead',
                deprecate='now',
            )
            if with_rich:
                style = 'rich'
        if style == 'auto':
            style = 'colors' if colors else 'plain'
            # style = 'rich' if colors else 'plain'

        from cmd_queue.util import util_tags

        exclude_tags = util_tags.Tags.coerce(exclude_tags)
        code = self.finalize_text(
            with_status=with_status,
            with_gaurds=with_gaurds,
            with_locks=with_locks,
            exclude_tags=exclude_tags,
        )
        if style == 'rich':
            from rich.console import Console
            from rich.panel import Panel
            from rich.syntax import Syntax

            console = Console()
            console.print(Panel(Syntax(code, 'bash'), title=str(self.fpath)))
        elif style == 'colors':
            print(ub.highlight_code(f'# --- {str(self.fpath)}', 'bash'))
            print(ub.highlight_code(code, 'bash'))
        elif style == 'plain':
            print(f'# --- {str(self.fpath)}')
            print(code)
        else:
            raise KeyError(f'Unknown style={style}')

    def rprint(self, **kwargs: Any) -> None:
        ub.schedule_deprecation(
            'cmd_queue',
            name='rprint',
            type='arg',
            migration='print_commands',
        )
        self.print_commands(**kwargs)

    def print_graph(
        self, reduced: bool = True, vertical_chains: bool = False
    ) -> None:
        """
        Renders the dependency graph to an "network text"

        Args:
            reduced (bool): if True only show the implicit dependency forest
        """
        self.write_network_text(
            reduced=reduced, vertical_chains=vertical_chains
        )

    def _dependency_graph(self) -> Any:
        """
        Builds a networkx dependency graph for the current jobs

        Example:
            >>> from cmd_queue import Queue
            >>> self = Queue.create(size=5, name='foo')
            >>> job1a = self.submit('echo hello && sleep 0.5')
            >>> job1b = self.submit('echo hello && sleep 0.5')
            >>> job2a = self.submit('echo hello && sleep 0.5', depends=[job1a])
            >>> job2b = self.submit('echo hello && sleep 0.5', depends=[job1b])
            >>> job3 = self.submit('echo hello && sleep 0.5', depends=[job2a, job2b])
            >>> jobX = self.submit('echo hello && sleep 0.5', depends=[])
            >>> jobY = self.submit('echo hello && sleep 0.5', depends=[jobX])
            >>> jobZ = self.submit('echo hello && sleep 0.5', depends=[jobY])
            >>> graph = self._dependency_graph()
            >>> self.print_graph()
        """
        from cmd_queue import _graph

        return _graph.build_dependency_graph(self.jobs)

    def monitor(
        self,
        refresh_rate: float = 0.4,
        with_textual: str | bool = 'auto',
        onfail: str = '',
        onexit: str = '',
    ) -> None:
        print('monitor not implemented')

    # Subclass-supplied entry points. Declaring them here lets callers
    # type-check against the abstract ``Queue`` (e.g. the value
    # returned by ``Queue.create``) without each backend's overrides
    # being flagged. The bodies just raise so a missing override is
    # caught at runtime rather than silently no-oping.

    def finalize_text(self, **kwargs: Any) -> str:
        raise NotImplementedError

    def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def kill(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def read_state(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


    def _coerce_style(
        self,
        style: str = 'auto',
        with_rich: Optional[bool] = None,
        colors: bool | int = True,
    ) -> str:
        from cmd_queue import _rendering

        return _rendering.coerce_style(style, with_rich, colors)
