from __future__ import annotations
# mypy: ignore-errors

from typing import Any, Dict, Iterable, List, Optional, Union

import ubelt as ub


class DuplicateJobError(KeyError):
    ...


class UnknownBackendError(KeyError):
    ...


class Job(ub.NiceRepr):
    """
    Base class for a job
    """
    def __init__(
        self,
        command: Optional[str] = None,
        name: Optional[str] = None,
        depends: Optional[Iterable[Job]] = None,
        **kwargs: Any,
    ) -> None:
        # This is unused, should the slurm and bash job reuse this?
        if depends is not None and not ub.iterable(depends):
            depends = [depends]
        self.name = name
        self.command = command
        self.depends = depends
        self.kwargs = kwargs

    def __nice__(self) -> str:
        return self.name


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
                    new_dep = new.named_jobs[dep.name]
                    new_depends.append(new_dep)
            # TODO: carry over metadata
            new.submit(job.command, depends=new_depends, name=job.name)
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
        graph = self._dependency_graph()
        # Find the jobs that nobody depends on
        sink_jobs = [graph.nodes[n]['job'] for n, d in graph.out_degree if d == 0]
        # All new jobs must depend on these jobs
        self.all_depends = sink_jobs
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
        os.chmod(self.fpath, (
            stat.S_IXUSR | stat.S_IXGRP | stat.S_IRUSR |
            stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP))
        return self.fpath

    def _new_job(
        self,
        command: str,
        depends: Optional[Iterable[Job]] = None,
        **kwargs: Any,
    ) -> Job:
        """
        Backend hook: create and return a Job instance appropriate for this backend.
        Must be implemented by backend queues.
        """
        raise NotImplementedError

    def _default_job_name(self) -> str:
        return self.name + '-job-{}'.format(self.num_real_jobs)

    def _normalize_depends(
        self,
        depends: Optional[Union[Job, str, Iterable[Union[Job, str]]]],
    ) -> List[Job]:
        if depends is None:
            return []
        if isinstance(depends, str) or not ub.iterable(depends):
            depends = [depends]
        try:
            return [
                self.named_jobs[dep] if isinstance(dep, str) else dep
                for dep in depends
            ]
        except Exception:
            print('self.named_jobs = {}'.format(ub.urepr(self.named_jobs, nl=1)))
            raise

    def _apply_all_depends(
        self,
        depends: Optional[Union[Job, str, Iterable[Union[Job, str]]]],
    ) -> List[Job]:
        if self.all_depends:
            if depends is None:
                depends = list(self.all_depends)
            else:
                if isinstance(depends, str) or not ub.iterable(depends):
                    depends = [depends]
                depends = list(self.all_depends) + list(depends)
        return self._normalize_depends(depends)

    def _register_job(self, job: Job) -> None:
        self.jobs.append(job)
        if job.name in self.named_jobs:
            raise DuplicateJobError(f'duplicate key {job.name}')
        self.named_jobs[job.name] = job
        if not getattr(job, 'bookkeeper', False):
            self.num_real_jobs += 1

    def submit(self, command: Union[str, Job], **kwargs: Any) -> Job:
        """
        Args:
            command (str | Job): The command to execute
            name: specify the name of the job
            **kwargs: backend-specific job arguments
        """
        # TODO: we could accept additional args here that modify how we handle
        # the command in the bash script we build (i.e. if the script is
        # allowed to fail or not)
        # self.commands.append(command)
        if isinstance(command, Job):
            job = command
        elif isinstance(command, str):
            name = kwargs.get('name', None)
            if name is None:
                kwargs['name'] = self._default_job_name()
            depends = self._apply_all_depends(kwargs.pop('depends', None))
            job = self._new_job(command=command, depends=depends, **kwargs)
        else:
            raise TypeError(type(command))
        self._register_job(job)
        return job

    @classmethod
    def _backend_classes(cls):
        from cmd_queue import tmux_queue
        from cmd_queue import serial_queue
        from cmd_queue import slurm_queue
        from cmd_queue import airflow_queue
        lut = {
            'serial': serial_queue.SerialQueue,
            'tmux': tmux_queue.TMUXMultiQueue,
            'slurm': slurm_queue.SlurmQueue,
            'airflow': airflow_queue.AirflowQueue,
        }
        return lut

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
        if backend == 'serial':
            from cmd_queue import serial_queue
            kwargs.pop('size', None)
            self = serial_queue.SerialQueue(**kwargs)
        elif backend == 'tmux':
            from cmd_queue import tmux_queue
            self = tmux_queue.TMUXMultiQueue(**kwargs)
        elif backend == 'slurm':
            from cmd_queue import slurm_queue
            kwargs.pop('size', None)
            self = slurm_queue.SlurmQueue(**kwargs)
        elif backend == 'airflow':
            from cmd_queue import airflow_queue
            kwargs.pop('size', None)
            self = airflow_queue.AirflowQueue(**kwargs)
        else:
            raise UnknownBackendError(backend)
        return self

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
            rich_mod = None
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
                nx.write_network_text(reduced_graph, path=print_, end='',
                                      vertical_chains=vertical_chains)
            except Exception as ex:
                print_(f'ex={ex}')
            print_('\n')
        else:
            print_('\nGraph:')
            nx.write_network_text(graph, path=print_, end='',
                                  vertical_chains=vertical_chains)

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
                'cmd_queue', 'colors', 'arg',
                migration='use style="plain" | "rich" | "colors" instead',
                deprecate='now')
            if not colors:
                style = 'plain'
        with_rich = kwargs.get('with_rich', None)
        if with_rich is not None:
            ub.schedule_deprecation(
                'cmd_queue', 'with_rich', 'arg',
                migration='use use style="plain" | "rich" | "colors" instead',
                deprecate='now')
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
            exclude_tags=exclude_tags)
        if style == 'rich':
            from rich.syntax import Syntax
            from rich.panel import Panel
            from rich.console import Console
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
            'cmd_queue', name='rprint', type='arg',
            migration='print_commands',
        )
        self.print_commands(**kwargs)

    def print_graph(self, reduced: bool = True, vertical_chains: bool = False) -> None:
        """
        Renders the dependency graph to an "network text"

        Args:
            reduced (bool): if True only show the implicit dependency forest
        """
        self.write_network_text(reduced=reduced, vertical_chains=vertical_chains)

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
        import networkx as nx
        graph = nx.DiGraph()
        duplicate_names = ub.find_duplicates(self.jobs, key=lambda x: x.name)
        if duplicate_names:
            print('duplicate_names = {}'.format(ub.urepr(duplicate_names, nl=1)))
            raise Exception('Job names must be unique')

        for index, job in enumerate(self.jobs):
            graph.add_node(job.name, job=job, index=index)
        for index, job in enumerate(self.jobs):
            if job.depends:
                for dep in job.depends:
                    if dep is not None:
                        graph.add_edge(dep.name, job.name)
        return graph

    def monitor(self) -> None:
        print('monitor not implemented')

    def _coerce_style(
        self,
        style: str = 'auto',
        with_rich: Optional[bool] = None,
        colors: bool = True,
    ) -> str:
        # Helper
        if with_rich is not None:
            ub.schedule_deprecation(
                'cmd_queue', 'with_rich', 'arg',
                migration='use style="rich" instead')
            if with_rich:
                style = 'rich'
        if style == 'auto':
            style = 'colors' if colors else 'plain'
        return style
