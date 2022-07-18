import ubelt as ub


class Job(ub.NiceRepr):
    """
    Base class for a job
    """
    def __init__(self, command=None, name=None, depends=None, **kwargs):
        if depends is not None and not ub.iterable(depends):
            depends = [depends]
        self.name = name
        self.command = command
        self.depends = depends
        self.kwargs = kwargs

    def __nice__(self):
        return self.name


class Queue(ub.NiceRepr):
    """
    Base class for a queue
    """

    def __init__(self):
        self.num_real_jobs = 0
        self.all_depends = None
        self.named_jobs = {}

    def __len__(self):
        return self.num_real_jobs

    def sync(self):
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

    def write(self):
        """
        Writes the underlying files that defines the queue for whatever program
        will ingest it to run it.
        """
        import os
        import stat
        text = self.finalize_text()
        self.fpath.parent.ensuredir()
        with open(self.fpath, 'w') as file:
            file.write(text)
        os.chmod(self.fpath, (
            stat.S_IXUSR | stat.S_IXGRP | stat.S_IRUSR |
            stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP))
        return self.fpath

    def submit(self, command, **kwargs):
        # TODO: we could accept additional args here that modify how we handle
        # the command in the bash script we build (i.e. if the script is
        # allowed to fail or not)
        # self.commands.append(command)
        # hack
        from cmd_queue import serial_queue

        if isinstance(command, str):
            name = kwargs.get('name', None)
            if name is None:
                name = kwargs['name'] = self.name + '-job-{}'.format(self.num_real_jobs)
            if self.all_depends:
                depends = kwargs.get('depends', None)
                if depends is None:
                    depends = self.all_depends
                else:
                    if not ub.iterable(depends):
                        depends = [depends]
                    depends = self.all_depends + depends
                kwargs['depends'] = depends
            job = serial_queue.BashJob(command, **kwargs)
        else:
            # Assume job is already a bash job
            job = command
        self.jobs.append(job)

        try:
            if job.name in self.named_jobs:
                raise KeyError(f'duplicate key {job.name}')
        except Exception:
            raise

        self.named_jobs[job.name] = job

        if not job.bookkeeper:
            self.num_real_jobs += 1
        return job

    @classmethod
    def available_backends(cls):
        available = ['serial']
        if ub.find_exe('tmux'):
            available.append('tmux')
        if ub.find_exe('slurm'):
            if ub.cmd('squeue')['ret'] == 0:
                available.append('slurm')
        return available

    @classmethod
    def create(cls, backend='serial', **kwargs):
        from cmd_queue import tmux_queue
        from cmd_queue import serial_queue
        from cmd_queue import slurm_queue
        if backend == 'serial':
            kwargs.pop('size', None)
            self = serial_queue.SerialQueue(**kwargs)
        elif backend == 'tmux':
            self = tmux_queue.TMUXMultiQueue(**kwargs)
        elif backend == 'slurm':
            kwargs.pop('size', None)
            self = slurm_queue.SlurmQueue(**kwargs)
        else:
            raise KeyError
        return self

    def print_graph(self, reduced=True):
        """
        Renders the dependency graph to an "network text"

        Args:
            reduced (bool): if True only show the implicit dependency forest
        """
        from cmd_queue import util
        import networkx as nx
        graph = self._dependency_graph()
        if reduced:
            print('\nGraph (reduced):')
            try:
                reduced_graph = nx.transitive_reduction(graph)
                print(util.graph_str(reduced_graph))
            except Exception as ex:
                print(f'ex={ex}')
            print('\n')
        else:
            print('\nGraph:')
            print(util.graph_str(graph))

    def _dependency_graph(self):
        """
        Builds a networkx dependency graph for the current jobs

        Example:
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> self = TMUXMultiQueue(5, 'foo')
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
            print('duplicate_names = {}'.format(ub.repr2(duplicate_names, nl=1)))
            raise Exception('Job names must be unique')

        for index, job in enumerate(self.jobs):
            graph.add_node(job.name, job=job, index=index)
        for index, job in enumerate(self.jobs):
            if job.depends:
                for dep in job.depends:
                    if dep is not None:
                        graph.add_edge(dep.name, job.name)
        return graph

    def monitor(self):
        print('monitor not implemented')
