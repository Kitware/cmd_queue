"""
A very simple queue based on tmux and bash

It should be possible to add more functionality, such as:

    - [x] A linear job queue - via one tmux shell

    - [x] Mulitple linear job queues - via multiple tmux shells

    - [x] Ability to query status of jobs - tmux script writes status to a
          file, secondary thread reads is.

    - [x] Unique identifier per queue

    - [ ] Central scheduler - given that we can know when a job is done
          a central scheduling process can run in the background, check
          the status of existing jobs, and spawn new jobs. --- Maybe not
          needed.

    - [X] Dependencies between jobs - given a central scheduler, it can
          only spawn a new job if a its dependencies have been met.

    - [ ] GPU resource requirements - if a job indicates how much of a
          particular resources it needs, the scheduler can only schedule the
          next job if it "fits" given the resources taken by the current
          running jobs.

    - [x] Duck typed API that uses Slurm if available. Slurm is a robust
          full featured queuing system. If it is available we should
          make it easy for the user to swap the tmux queue for slurm.

    - [x] Duck typed API that uses subprocesses. Tmux is not always available,
          we could go even lighter weight and simply execute a subprocess that
          does the same thing as the linear queue. The downside is you don't
          get the nice tmux way of looking at the status of what the jobs are
          doing, but that doesn't matter in debugged automated workflows, and
          this does seem like a nice simple utility. Doesnt seem to exist
          elsewhere either, but my search terms might be wrong.

    - [ ] Handle the case where some jobs need the GPU and others do not

Example:
    >>> import cmd_queue
    >>> queue = cmd_queue.Queue.create(backend='tmux')
    >>> job1 = queue.submit('echo "Hello World" && sleep 0.1')
    >>> job2 = queue.submit('echo "Hello Kitty" && sleep 0.1', depends=[job1])
    >>> if queue.is_available():
    >>>     queue.run()

"""
import ubelt as ub
# import itertools as it
import uuid

from cmd_queue import base_queue
from cmd_queue import serial_queue
from cmd_queue.util import util_tags


class TMUXMultiQueue(base_queue.Queue):
    """
    Create multiple sets of jobs to start in detatched tmux sessions

    CommandLine:
        xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue:0
        xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue:2

    Example:
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> self = TMUXMultiQueue(1, 'test-tmux-queue')
        >>> job1 = self.submit('echo hi 1 && false')
        >>> job2 = self.submit('echo hi 2 && true')
        >>> job3 = self.submit('echo hi 3 && true', depends=job1)
        >>> self.rprint()
        >>> self.print_graph()
        >>> if self.is_available():
        >>>     self.run(block=True, onexit='capture', check_other_sessions=0)

    Example:
        >>> from cmd_queue.tmux_queue import *  # NOQA
        >>> import random
        >>> rng = random.Random(54425367001)
        >>> self = TMUXMultiQueue(1, 'real-world-usecase', gres=[0, 1])
        >>> def add_edge(name, depends):
        >>>     if name is not None:
        >>>         _depends = [self.named_jobs[n] for n in depends if n is not None]
        >>>         self.submit(f'echo name={name}, depends={depends} && sleep 0.1', name=name, depends=_depends)
        >>> def add_branch(suffix):
        >>>     f = 0.3
        >>>     pred = f'pred{suffix}' if rng.random() > f else None
        >>>     track = f'track{suffix}' if rng.random() > f else None
        >>>     actclf = f'actclf{suffix}' if rng.random() > f else None
        >>>     pxl_eval = f'pxl_eval{suffix}' if rng.random() > f else None
        >>>     trk_eval = f'trk_eval{suffix}' if rng.random() > f else None
        >>>     act_eval = f'act_eval{suffix}' if rng.random() > f else None
        >>>     add_edge(pred, [])
        >>>     add_edge(track, [pred])
        >>>     add_edge(actclf, [pred])
        >>>     add_edge(pxl_eval, [pred])
        >>>     add_edge(trk_eval, [track])
        >>>     add_edge(act_eval, [actclf])
        >>> for i in range(3):
        >>>     add_branch(str(i))
        >>> self.rprint()
        >>> self.print_graph()
        >>> if self.is_available():
        >>>     self.run(block=1, onexit='', check_other_sessions=0)

    Example:
        >>> from cmd_queue.tmux_queue import TMUXMultiQueue
        >>> self = TMUXMultiQueue(size=2, name='foo')
        >>> print('self = {!r}'.format(self))
        >>> job1 = self.submit('echo hello && sleep 0.5')
        >>> job2 = self.submit('echo world && sleep 0.5', depends=[job1])
        >>> job3 = self.submit('echo foo && sleep 0.5')
        >>> job4 = self.submit('echo bar && sleep 0.5')
        >>> job5 = self.submit('echo spam && sleep 0.5', depends=[job1])
        >>> job6 = self.submit('echo spam && sleep 0.5')
        >>> job7 = self.submit('echo err && false')
        >>> job8 = self.submit('echo spam && sleep 0.5')
        >>> job9 = self.submit('echo eggs && sleep 0.5', depends=[job8])
        >>> job10 = self.submit('echo bazbiz && sleep 0.5', depends=[job9])
        >>> self.write()
        >>> self.rprint()
        >>> if self.is_available():
        >>>     self.run(check_other_sessions=0)
        >>>     self.monitor()
        >>>     self.current_output()
        >>>     self.kill()

    Ignore:
        >>> from cmd_queue.tmux_queue import *  # NOQA
        >>> self = TMUXMultiQueue(2, 'foo', gres=[0, 1])
        >>> job1 = self.submit('echo hello && sleep 0.5')
        >>> job2 = self.submit('echo hello && sleep 0.5')
        >>> self.rprint()
        >>> # --
        >>> from cmd_queue.tmux_queue import *  # NOQA
        >>> self = TMUXMultiQueue(2, 'foo')
        >>> job1 = self.submit('echo hello && sleep 0.5')
        >>> self.sync()
        >>> job2 = self.submit('echo hello && sleep 0.5')
        >>> self.sync()
        >>> job3 = self.submit('echo hello && sleep 0.5')
        >>> self.sync()
        >>> self.rprint()
        >>> # --
        >>> from cmd_queue.tmux_queue import *  # NOQA
        >>> self = TMUXMultiQueue(2, 'foo')
        >>> job1 = self.submit('echo hello && sleep 0.5')
        >>> job2 = self.submit('echo hello && sleep 0.5')
        >>> job3 = self.submit('echo hello && sleep 0.5')
        >>> self.rprint()

    Example:
        >>> # Test complex failure case
        >>> from cmd_queue import Queue
        >>> self = Queue.create(size=2, name='demo-complex-failure', backend='tmux')
        >>> # Submit a binary tree that fails at different levels
        >>> for idx in range(2):
        >>>     # Level 0
        >>>     job1000 = self.submit('true')
        >>>     # Level 1
        >>>     job1100 = self.submit('true', depends=[job1000])
        >>>     job1200 = self.submit('false', depends=[job1000], name=f'false0_{idx}')
        >>>     # Level 2
        >>>     job1110 = self.submit('true', depends=[job1100])
        >>>     job1120 = self.submit('false', depends=[job1100], name=f'false1_{idx}')
        >>>     job1210 = self.submit('true', depends=[job1200])
        >>>     job1220 = self.submit('true', depends=[job1200])
        >>>     # Level 3
        >>>     job1111 = self.submit('true', depends=[job1110])
        >>>     job1112 = self.submit('false', depends=[job1110], name=f'false2_{idx}')
        >>>     job1121 = self.submit('true', depends=[job1120])
        >>>     job1122 = self.submit('true', depends=[job1120])
        >>>     job1211 = self.submit('true', depends=[job1210])
        >>>     job1212 = self.submit('true', depends=[job1210])
        >>>     job1221 = self.submit('true', depends=[job1220])
        >>>     job1222 = self.submit('true', depends=[job1220])
        >>> # Submit a chain that fails in the middle
        >>> chain1 = self.submit('true', name='chain1')
        >>> chain2 = self.submit('true', depends=[chain1], name='chain2')
        >>> chain3 = self.submit('false', depends=[chain2], name='chain3')
        >>> chain4 = self.submit('true', depends=[chain3], name='chain4')
        >>> chain5 = self.submit('true', depends=[chain4], name='chain5')
        >>> # Submit 4 loose passing jobs
        >>> for _ in range(4):
        >>>     self.submit('true', name=f'loose_true{_}')
        >>> # Submit 4 loose failing jobs
        >>> for _ in range(4):
        >>>     self.submit('false', name=f'loose_false{_}')
        >>> self.rprint()
        >>> self.print_graph()
        >>> if self.is_available():
        >>>     self.run(with_textual=False, check_other_sessions=0)
    """
    def __init__(self, size=1, name=None, dpath=None, rootid=None, environ=None,
                 gres=None):
        super().__init__()

        if rootid is None:
            rootid = str(ub.timestamp().split('T')[0]) + '_' + ub.hash_data(uuid.uuid4())[0:8]
        if name is None:
            name = 'unnamed'
        self.name = name
        self.rootid = rootid
        self.pathid = '{}_{}'.format(self.name, self.rootid)
        if dpath is None:
            dpath = ub.Path.appdir('cmd_queue/tmux').ensuredir()
        self.dpath = (ub.Path(dpath) / self.pathid).ensuredir()

        if environ is None:
            environ = {}

        # Note: size can be changed as long as it happens before the queue is
        # written and run.
        self.size = size
        self.environ = environ
        self.fpath = self.dpath / f'run_queues_{self.name}.sh'
        self.gres = gres
        self.cmd_verbose = 2

        self.jobs = []
        self.header_commands = []

        self._tmux_session_prefix = 'cmdq_'

        self._new_workers()

    @classmethod
    def is_available(cls):
        """
        Determines if we can run the tmux queue or not.
        """
        return ub.find_exe('tmux')

    def _new_workers(self, start=0):
        import itertools as it
        per_worker_environs = [self.environ] * self.size
        if self.gres:
            # TODO: more sophisticated GPU policy?
            per_worker_environs = [
                ub.dict_union(e, {
                    'CUDA_VISIBLE_DEVICES': str(cvd),
                })
                for cvd, e in zip(it.cycle(self.gres), per_worker_environs)
            ]

        workers = [
            serial_queue.SerialQueue(
                name='{}{}_{:03d}'.format(self._tmux_session_prefix, self.name, worker_idx),
                rootid=self.rootid,
                dpath=self.dpath,
                environ=e
            )
            for worker_idx, e in enumerate(per_worker_environs, start=start)
        ]
        return workers

    def __nice__(self):
        return ub.repr2(self.jobs)

    def _semaphore_wait_command(self, flag_fpaths, msg):
        r"""
        TODO: use flock?

        Ignore:

            #  In queue 1
            flock /var/lock/lock1.lock python -c 'while True: print(".", end="")'

            #  In queue 2
            flock /var/lock/lock2.lock python -c 'while True: print(".", end="")'

            #  In queue 3
            flock /var/lock/lock1.lock echo "first lock finished" && \
                flock /var/lock/lock2.lock echo "second lock finished" && \
                    python -c "print('this command depends on lock1 and lock2 procs completing')"


            flock /var/lock/lock2.lock echo "second lock finished"

            flock /var/lock/lock1.lock /var/lock/lock2.lock -c python -c 'while True: print("hi")'
        """
        # TODO: use inotifywait
        conditions = ['[ ! -f {} ]'.format(p) for p in flag_fpaths]
        condition = ' || '.join(conditions)
        # TODO: count number of files that exist
        command = ub.codeblock(
            f'''
            printf "{msg} "
            while {condition};
            do
               sleep 1;
            done
            printf "finished {msg} "
            ''')
        return command

    def _semaphore_signal_command(self, flag_fpath):
        return ub.codeblock(
            f'''
            # Signal this worker is complete
            mkdir -p {flag_fpath.parent} && touch {flag_fpath}
            '''
        )

    def order_jobs(self):
        """
        Example:
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> self = TMUXMultiQueue(5, 'foo')
            >>> job1a = self.submit('echo hello && sleep 0.5')
            >>> job1b = self.submit('echo hello && sleep 0.5')
            >>> job2a = self.submit('echo hello && sleep 0.5', depends=[job1a])
            >>> job2b = self.submit('echo hello && sleep 0.5', depends=[job1b])
            >>> job3 = self.submit('echo hello && sleep 0.5', depends=[job2a, job2b])
            >>> self.rprint()

            self.run(block=True, check_other_sessions=0)

        Example:
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> self = TMUXMultiQueue(5, 'foo')
            >>> job0 = self.submit('true')
            >>> job1 = self.submit('true')
            >>> job2 = self.submit('true', depends=[job0])
            >>> job3 = self.submit('true', depends=[job1])
            >>> #job2c = self.submit('true', depends=[job1a, job1b])
            >>> #self.sync()
            >>> job4 = self.submit('true', depends=[job2, job3, job1])
            >>> job5 = self.submit('true', depends=[job4])
            >>> job6 = self.submit('true', depends=[job4])
            >>> job7 = self.submit('true', depends=[job4])
            >>> job8 = self.submit('true', depends=[job5])
            >>> job9 = self.submit('true', depends=[job6])
            >>> job10 = self.submit('true', depends=[job6])
            >>> job11 = self.submit('true', depends=[job7])
            >>> job12 = self.submit('true', depends=[job10, job11])
            >>> job13 = self.submit('true', depends=[job4])
            >>> job14 = self.submit('true', depends=[job13])
            >>> job15 = self.submit('true', depends=[job4])
            >>> job16 = self.submit('true', depends=[job15, job13])
            >>> job17 = self.submit('true', depends=[job4])
            >>> job18 = self.submit('true', depends=[job17])
            >>> job19 = self.submit('true', depends=[job14, job16, job17])
            >>> self.print_graph(reduced=False)
            ...
            Graph:
            ╟── foo-job-0
            ╎   └─╼ foo-job-2
            ╎       └─╼ foo-job-4 ╾ foo-job-3, foo-job-1
            ╎           ├─╼ foo-job-5
            ╎           │   └─╼ foo-job-8
            ╎           ├─╼ foo-job-6
            ╎           │   ├─╼ foo-job-9
            ╎           │   └─╼ foo-job-10
            ╎           │       └─╼ foo-job-12 ╾ foo-job-11
            ╎           ├─╼ foo-job-7
            ╎           │   └─╼ foo-job-11
            ╎           │       └─╼  ...
            ╎           ├─╼ foo-job-13
            ╎           │   ├─╼ foo-job-14
            ╎           │   │   └─╼ foo-job-19 ╾ foo-job-16, foo-job-17
            ╎           │   └─╼ foo-job-16 ╾ foo-job-15
            ╎           │       └─╼  ...
            ╎           ├─╼ foo-job-15
            ╎           │   └─╼  ...
            ╎           └─╼ foo-job-17
            ╎               ├─╼ foo-job-18
            ╎               └─╼  ...
            ╙── foo-job-1
                ├─╼ foo-job-3
                │   └─╼  ...
                └─╼  ...
            >>> self.rprint()
            >>> # self.run(block=True)
        """
        import networkx as nx
        from cmd_queue.util.util_networkx import graph_str
        graph = self._dependency_graph()

        # Get rid of implicit dependencies
        try:
            reduced_graph = nx.transitive_reduction(graph)
        except Exception as ex:
            print('ex = {!r}'.format(ex))
            print('graph = {!r}'.format(graph))
            print(len(graph.nodes))
            print('graph.nodes = {}'.format(ub.repr2(graph.nodes, nl=1)))
            print('graph.edges = {}'.format(ub.repr2(graph.edges, nl=1)))
            print(len(graph.edges))
            print(graph.is_directed())
            print(nx.is_forest(graph))
            print(nx.is_directed_acyclic_graph(graph))
            simple_cycles = list(nx.cycles.simple_cycles(graph))
            print('simple_cycles = {}'.format(ub.repr2(simple_cycles, nl=1)))
            import xdev
            xdev.embed()
            print(graph_str(graph))
            raise

        in_cut_nodes = set()
        out_cut_nodes = set()
        cut_edges = []
        for n in reduced_graph.nodes:
            # TODO: need to also check that the paths to a source node are
            # not unique, otherwise we dont need to cut the node, but extra
            # cuts wont matter, just make it less effiicent
            in_d = reduced_graph.in_degree[n]
            out_d = reduced_graph.out_degree[n]
            if in_d > 1:
                cut_edges.extend(list(reduced_graph.in_edges(n)))
                in_cut_nodes.add(n)
            if out_d > 1:
                cut_edges.extend(list(reduced_graph.out_edges(n)))
                out_cut_nodes.add(n)

        cut_graph = reduced_graph.copy()
        cut_graph.remove_edges_from(cut_edges)

        # Get all the node groups disconnected by the cuts
        condensed = nx.condensation(reduced_graph, nx.weakly_connected_components(cut_graph))

        # Rank each condensed group, which defines
        # what order it is allowed to be executed in
        rankings = ub.ddict(set)
        condensed_order = list(nx.topological_sort(condensed))
        for c_node in condensed_order:
            members = set(condensed.nodes[c_node]['members'])
            ancestors = set(ub.flatten([nx.ancestors(reduced_graph, m) for m in members]))
            cut_in_ancestors = ancestors & in_cut_nodes
            cut_out_ancestors = ancestors & out_cut_nodes
            cut_in_members = members & in_cut_nodes
            rank = len(cut_in_members) + len(cut_out_ancestors) + len(cut_in_ancestors)
            for m in members:
                rankings[rank].update(members)

        if 0:
            from graphid.util import util_graphviz
            import kwplot
            kwplot.autompl()
            util_graphviz.show_nx(graph, fnum=1)
            util_graphviz.show_nx(reduced_graph, fnum=3)
            util_graphviz.show_nx(condensed, fnum=2)

        # cmd_queue.graph_str(condensed, write=print)

        # Each rank defines a group that must itself be ordered
        # Ranks will execute sequentially, members within the
        # rank *might* be run in parallel
        ranked_job_groups = []
        for rank, group in sorted(rankings.items()):
            subgraph = graph.subgraph(group)
            # Only things that can run in parallel are disconnected components
            parallel_groups = []
            for wcc in list(nx.weakly_connected_components(subgraph)):
                sub_subgraph = subgraph.subgraph(wcc)
                wcc_order = list(nx.topological_sort(sub_subgraph))
                parallel_groups.append(wcc_order)
            # Ranked bins
            # Solve a bin packing problem to partition these into self.size groups
            from cmd_queue.util.util_algo import balanced_number_partitioning
            group_weights = list(map(len, parallel_groups))
            groupxs = balanced_number_partitioning(group_weights, num_parts=self.size)
            rank_groups = [list(ub.take(parallel_groups, gxs)) for gxs in groupxs]
            rank_groups = [g for g in rank_groups if len(g)]

            # Reorder each group to better agree with submission order
            rank_jobs = []
            for group in rank_groups:
                priorities = []
                for nodes in group:
                    nodes_index = min(graph.nodes[n]['index'] for n in nodes)
                    priorities.append(nodes_index)
                final_queue_order = list(ub.flatten(ub.take(group, ub.argsort(priorities))))
                final_queue_jobs = [graph.nodes[n]['job'] for n in final_queue_order]
                rank_jobs.append(final_queue_jobs)
            ranked_job_groups.append(rank_jobs)

        queue_workers = []
        flag_dpath = (self.dpath / 'semaphores')
        prev_rank_flag_fpaths = None
        for rank, rank_jobs in enumerate(ranked_job_groups):
            # Hack, abuse init workers each time to construct workers
            workers = self._new_workers(start=len(queue_workers))
            rank_workers = []
            for worker, jobs in zip(workers, rank_jobs):
                # Add a dummy job to wait for dependencies of this linear queue

                if prev_rank_flag_fpaths:
                    command = self._semaphore_wait_command(prev_rank_flag_fpaths, msg=f"wait for previous rank {rank - 1}")
                    # Note: this should not be a real job
                    worker.submit(command, bookkeeper=1)

                for job in jobs:
                    # worker.submit(job.command)
                    worker.submit(job)

                rank_workers.append(worker)

            queue_workers.extend(rank_workers)

            # Add a dummy job at the end of each worker to signal finished
            rank_flag_fpaths = []
            num_rank_workers = len(rank_workers)
            for worker_idx, worker in enumerate(rank_workers):
                rank_flag_fpath = flag_dpath / f'rank_flag_{rank}_{worker_idx}_{num_rank_workers}.done'
                command = self._semaphore_signal_command(rank_flag_fpath)
                # Note: this should not be a real job
                worker.submit(command, bookkeeper=1)
                rank_flag_fpaths.append(rank_flag_fpath)
            prev_rank_flag_fpaths = rank_flag_fpaths

        # Overwrite workers with our new dependency aware workers
        for worker in queue_workers:
            for header_command in self.header_commands:
                worker.add_header_command(header_command)
        self.workers = queue_workers

    def add_header_command(self, command):
        """
        Adds a header command run at the start of each queue
        """
        self.header_commands.append(command)

    def finalize_text(self):
        self.order_jobs()
        # Create a driver script
        driver_lines = [ub.codeblock(
            '''
            #!/bin/bash
            # Driver script to start the tmux-queue
            echo "submitting {} jobs"
            ''').format(self.num_real_jobs)]
        for queue in self.workers:
            # run_command_in_tmux_queue(command, name)
            # TODO: figure out how to forward environment variables from the
            # running sessions. We dont want to log secrets to plaintext.
            part = ub.codeblock(
                f'''
                ### Run Queue: {queue.pathid} with {len(queue)} jobs
                tmux new-session -d -s {queue.pathid} "bash"
                tmux send -t {queue.pathid} \\
                    "source {queue.fpath}" \\
                    Enter
                ''').format()
            driver_lines.append(part)
        driver_lines += ['echo "jobs submitted"']
        driver_text = '\n\n'.join(driver_lines)
        return driver_text

    def write(self):
        self.order_jobs()
        for queue in self.workers:
            queue.write()
        super().write()

    def kill_other_queues(self, ask_first=True):
        """
        Find other tmux sessions that look like they were started with
        cmd_queue and kill them.
        """
        import parse
        queue_name_pattern = parse.Parser(self._tmux_session_prefix + '{name}_{rootid}')
        current_sessions = self._tmux_current_sessions()
        other_session_ids = []
        for info in current_sessions:
            matched = queue_name_pattern.parse(info['id'])
            if matched is not None:
                if self.name == matched['name']:
                    other_session_ids.append(info['id'])
        print(f'other_session_ids={other_session_ids}')
        if other_session_ids:
            print('It looks like there are other running cmd-queue sessions')
            print('Commands to kill them:')
            kill_commands = []
            for sess_id in other_session_ids:
                command2 = f'tmux kill-session -t {sess_id}'
                print(command2)
                kill_commands.append(command2)
            from rich import prompt
            if not ask_first or prompt.Confirm().ask('Do you want to kill the other sessions?'):
                for command in kill_commands:
                    ub.cmd(command, verbose=self.cmd_verbose)

    def run(self, block=True, onfail='kill', onexit='', system=False,
            with_textual='auto', check_other_sessions='auto'):

        if not self.is_available():
            raise Exception('tmux not found')
        if check_other_sessions:
            if check_other_sessions == 'auto':
                if not has_stdin():
                    check_other_sessions = False
            if check_other_sessions:
                self.kill_other_queues(ask_first=True)

        self.write()
        ub.cmd(f'bash {self.fpath}', verbose=self.cmd_verbose, check=True,
               system=system)
        if block:
            agg_state = self.monitor(with_textual=with_textual)
            if onexit == 'capture':
                self.capture()
            if not agg_state['failed']:
                if onfail == 'kill':
                    self.kill()
            return agg_state

    def read_state(self):
        agg_state = {}
        worker_states = []
        for worker in self.workers:
            state = worker.read_state()
            worker_states.append(state)
        agg_state['worker_states'] = worker_states
        try:
            agg_state['total'] = sum(s['total'] for s in worker_states)
            agg_state['failed'] = sum(s['failed'] for s in worker_states)
            agg_state['passed'] = sum(s['passed'] for s in worker_states)
            agg_state['skipped'] = sum(s['skipped'] for s in worker_states)
            agg_state['rootid'] = ub.peek(s['rootid'] for s in worker_states)
            states = set(s['status'] for s in worker_states)
            agg_state['status'] = 'done' if states == {'done'} else 'not-done'
        except Exception:
            pass
        return agg_state

    def serial_run(self):
        """
        Hack to run everything without tmux. This really should be a different
        "queue" backend.

        See Serial Queue instead
        """
        # deprecate: use serial queue instead
        self.order_jobs()
        queue_fpaths = []
        for queue in self.workers:
            fpath = queue.write()
            queue_fpaths.append(fpath)
        for fpath in queue_fpaths:
            ub.cmd(f'{fpath}', verbose=self.cmd_verbose, check=True)

    def monitor(self, refresh_rate=0.4, with_textual='auto'):
        """
        Monitor progress until the jobs are done

        CommandLine:
            xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.monitor:0
            xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.monitor:1 --interact

        Example:
            >>> # xdoctest: +REQUIRES(--interact)
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> self = TMUXMultiQueue(size=3, name='test-queue-monitor')
            >>> job = None
            >>> for i in range(10):
            >>>     job = self.submit('sleep 2 && echo "hello 2"', depends=job)
            >>> job = None
            >>> for i in range(10):
            >>>     job = self.submit('sleep 3 && echo "hello 2"', depends=job)
            >>> job = None
            >>> for i in range(5):
            >>>     job = self.submit('sleep 5 && echo "hello 2"', depends=job)
            >>> self.rprint()
            >>> if self.is_available():
            >>>     self.run(block=True, check_other_sessions=0)

        Example:
            >>> # xdoctest: +REQUIRES(--interact)
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> # Setup a lot of longer running jobs
            >>> n = 128
            >>> self = TMUXMultiQueue(size=n, name='test-giant-queue-monitor')
            >>> for i in range(n):
            >>>     job = None
            >>>     for i in range(4):
            >>>         job = self.submit('sleep 1 && echo "hello 2"', depends=job)
            >>> self.rprint()
            >>> if self.is_available():
            >>>     self.run(block=True, check_other_sessions=0)
        """
        print('Start monitor')
        if with_textual == 'auto':
            with_textual = CmdQueueMonitorApp is not None
            # If we dont have stdin (i.e. running in pytest) we cant use
            # textual.
            if not has_stdin():
                with_textual = False

        if with_textual:
            self._textual_monitor()
        else:
            self._simple_rich_monitor(refresh_rate)
        table, finished, agg_state = self._build_status_table()
        return agg_state

    def _textual_monitor(self):
        from rich import print as rprint
        print('Kill commands:')
        for command in self._kill_commands():
            print(command)
        table_fn = self._build_status_table
        app = CmdQueueMonitorApp(table_fn, kill_fn=self.kill)
        app.run()

        table, finished, agg_state = self._build_status_table()
        rprint(table)

        if not app.graceful_exit:
            from rich.prompt import Confirm
            flag = Confirm.ask('do you to kill the procs?')
            if flag:
                self.kill()
            raise Exception('User Stopped The Monitor')

    def _simple_rich_monitor(self, refresh_rate=0.4):
        import time
        from rich.live import Live
        print('Kill commands:')
        for command in self._kill_commands():
            print(command)
        try:
            table, finished, agg_state = self._build_status_table()
            with Live(table, refresh_per_second=4) as live:
                while not finished:
                    time.sleep(refresh_rate)
                    table, finished, agg_state = self._build_status_table()
                    live.update(table)
        except KeyboardInterrupt:
            from rich.prompt import Confirm
            flag = Confirm.ask('do you to kill the procs?')
            if flag:
                self.kill()

    def _build_status_table(self):
        from rich.table import Table
        # https://rich.readthedocs.io/en/stable/live.html
        table = Table()
        columns = ['tmux session name', 'status', 'passed', 'failed', 'skipped', 'total']
        for col in columns:
            table.add_column(col)

        finished = True
        agg_state = {
            'name': 'agg',
            'status': '',
            'failed': 0,
            'passed': 0,
            'skipped': 0,
            'total': 0
        }

        for worker in self.workers:
            pass_color = ''
            fail_color = ''
            skip_color = ''
            state = worker.read_state()
            if state['status'] == 'unknown':
                finished = False
                pass_color = '[yellow]'
            else:
                finished &= (state['status'] == 'done')
                if state['status'] == 'done':
                    pass_color = '[green]'

                if (state['failed'] > 0):
                    fail_color = '[red]'
                if (state['skipped'] > 0):
                    skip_color = '[yellow]'

                agg_state['total'] += state['total']
                agg_state['passed'] += state['passed']
                agg_state['failed'] += state['failed']
                agg_state['skipped'] += state['skipped']

            table.add_row(
                state['name'],
                state['status'],
                f"{pass_color}{state['passed']}",
                f"{fail_color}{state['failed']}",
                f"{skip_color}{state['skipped']}",
                f"{state['total']}",
            )

        if not finished:
            agg_state['status'] = 'run'
        else:
            agg_state['status'] = 'done'

        if len(self.workers) > 1:
            table.add_row(
                agg_state['name'],
                agg_state['status'],
                f"{agg_state['passed']}",
                f"{agg_state['failed']}",
                f"{agg_state['skipped']}",
                f"{agg_state['total']}",
            )
        return table, finished, agg_state

    def rprint(self, with_status=False, with_gaurds=False, with_rich=0,
               with_locks=1, colors=1, exclude_tags=None):
        """
        Print info about the commands, optionally with rich

        Example:
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> self = TMUXMultiQueue(size=2, name='test-rprint-tmux-queue')
            >>> self.submit('echo hi 1', name='job1')
            >>> self.submit('echo boilerplate job1', depends='job1', tags='boilerplate')
            >>> self.submit('echo hi 2', log=False)
            >>> self.submit('echo hi 3')
            >>> self.submit('echo hi 4')
            >>> self.submit('echo hi 5', log=False, name='job5')
            >>> self.submit('echo boilerplate job2', depends='job5', tags='boilerplate')
            >>> self.submit('echo hi 6', name='job6', depends='job5')
            >>> self.submit('echo hi 7', name='job7', depends='job5')
            >>> self.submit('echo boilerplate job3', depends=['job6', 'job7'], tags='boilerplate')
            >>> print('\n\n---\n\n')
            >>> self.rprint(with_status=1, with_gaurds=1, with_locks=1, with_rich=1)
            >>> print('\n\n---\n\n')
            >>> self.rprint(with_status=0, with_gaurds=1, with_locks=1, with_rich=1)
            >>> print('\n\n---\n\n')
            >>> self.rprint(with_status=0, with_gaurds=0, with_locks=0, with_rich=1)
            >>> print('\n\n---\n\n')
            >>> self.rprint(with_status=0, with_gaurds=0, with_locks=0,
            ...             with_rich=1, exclude_tags='boilerplate')
        """
        from rich.panel import Panel
        from rich.syntax import Syntax
        from rich.console import Console
        self.order_jobs()
        console = Console()

        exclude_tags = util_tags.Tags.coerce(exclude_tags)
        for queue in self.workers:
            queue.rprint(with_status=with_status, with_gaurds=with_gaurds,
                         with_rich=with_rich, with_locks=with_locks,
                         colors=colors, exclude_tags=exclude_tags)

        code = self.finalize_text()
        if with_rich:
            console.print(Panel(Syntax(code, 'bash'), title=str(self.fpath)))
        else:
            if colors:
                print(ub.highlight_code('# --- ' + str(self.fpath), 'bash'))
                print(ub.highlight_code(code, 'bash'))
            else:
                print('# --- ' + str(self.fpath))
                print(code)

    def current_output(self):
        for queue in self.workers:
            print('\n\nqueue = {!r}'.format(queue))
            # First print out the contents for debug
            ub.cmd(f'tmux capture-pane -p -t "{queue.pathid}:0.0"', verbose=self.cmd_verbose)

    def _print_commands(self):
        # First print out the contents for debug
        for queue in self.workers:
            command1 = f'tmux capture-pane -p -t "{queue.pathid}:0.0"'
            yield command1

    def _kill_commands(self):
        for queue in self.workers:
            # Then kill it
            command2 = f'tmux kill-session -t {queue.pathid}'
            yield command2

    def capture(self):
        for command in self._print_commands():
            ub.cmd(command, verbose=self.cmd_verbose)

    def kill(self):
        # Kills all the tmux panes
        for command in self._kill_commands():
            ub.cmd(command, verbose=self.cmd_verbose)

    def _tmux_current_sessions(self):
        # Kills all the tmux panes
        info = ub.cmd('tmux list-sessions')
        sessions = []
        for line in info['out'].split('\n'):
            line = line.strip()
            if line:
                session_id, rest = line.split(':', 1)
                sessions.append({
                    'id': session_id,
                    'rest': rest
                })
        return sessions


def has_stdin():
    import sys
    try:
        sys.stdin.fileno()
    except Exception:
        return False
    else:
        return True


try:
    import textual  # NOQA
    from cmd_queue.monitor_app import CmdQueueMonitorApp
except ImportError:
    CmdQueueMonitorApp = None


if 0:
    __tmux_notes__ = """
    # Useful tmux commands

    tmux list-commands


    tmux new-session -d -s {queue.pathid} "bash"
    tmux send -t {queue.pathid} "source {queue.fpath}" Enter

    tmux new-session -d -s my_session_id "bash"

    # References:
    # https://stackoverflow.com/questions/20701757/tmux-setting-environment-variables-for-sessions
    # Requires tmux 3.2
    export MYSECRET=12345
    tmux new-session -d -s my_session_id "bash"

    tmux set -t my_session_id update-environment MYSECRET

    tmux list-sessions
    tmux list-panes -a
    tmux list-windows -a

    # This can query the content of the current pane
    tmux capture-pane -p -t "my_session_id:0.0"

    tmux attach-session -t my_session_id

    tmux kill-session -t my_session_id

    tmux list-windows -t my_session_id

    tmux capture-pane -t my_session_id
    tmux capture-pane --help
    -t my_session_id
    """
