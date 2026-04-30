from __future__ import annotations
# mypy: ignore-errors

"""
A very simple queue based on tmux and bash

It should be possible to add more functionality, such as:

    - [x] A linear job queue - via one tmux shell

    - [x] Multiple linear job queues - via multiple tmux shells

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
import uuid
from typing import Any, Dict, Iterable, List, Optional

import ubelt as ub
# import itertools as it

from cmd_queue import base_queue
from cmd_queue import serial_queue
from cmd_queue.util.util_tmux import tmux


class TMUXMultiQueue(base_queue.Queue):
    """
    Create multiple sets of jobs to start in detached tmux sessions

    CommandLine:
        xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue:0
        xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue:2

    Example:
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> self = TMUXMultiQueue(1, 'test-tmux-queue')
        >>> job1 = self.submit('echo hi 1 && false')
        >>> job2 = self.submit('echo hi 2 && true')
        >>> job3 = self.submit('echo hi 3 && true', depends=job1)
        >>> self.print_commands()
        >>> self.print_graph()
        >>> if self.is_available():
        >>>     self.run(block=True, onexit='capture', check_other_sessions=0)

    Example:
        >>> from cmd_queue.tmux_queue import *  # NOQA
        >>> import random
        >>> rng = random.Random(54425367001)
        >>> self = TMUXMultiQueue(1, 'real-world-usecase', gpus=[0, 1])
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
        >>> self.print_commands()
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
        >>> self.print_commands()
        >>> if self.is_available():
        >>>     self.run(check_other_sessions=0)
        >>>     self.monitor()
        >>>     self.current_output()
        >>>     self.kill()

    Ignore:
        >>> from cmd_queue.tmux_queue import *  # NOQA
        >>> self = TMUXMultiQueue(2, 'foo', gpus=[0, 1])
        >>> job1 = self.submit('echo hello && sleep 0.5')
        >>> job2 = self.submit('echo hello && sleep 0.5')
        >>> self.print_commands()
        >>> # --
        >>> from cmd_queue.tmux_queue import *  # NOQA
        >>> self = TMUXMultiQueue(2, 'foo')
        >>> job1 = self.submit('echo hello && sleep 0.5')
        >>> self.sync()
        >>> job2 = self.submit('echo hello && sleep 0.5')
        >>> self.sync()
        >>> job3 = self.submit('echo hello && sleep 0.5')
        >>> self.sync()
        >>> self.print_commands()
        >>> # --
        >>> from cmd_queue.tmux_queue import *  # NOQA
        >>> self = TMUXMultiQueue(2, 'foo')
        >>> job1 = self.submit('echo hello && sleep 0.5')
        >>> job2 = self.submit('echo hello && sleep 0.5')
        >>> job3 = self.submit('echo hello && sleep 0.5')
        >>> self.print_commands()

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
        >>> self.print_commands()
        >>> self.print_graph()
        >>> if self.is_available():
        >>>     self.run(with_textual=False, check_other_sessions=0)
    """
    def __init__(
        self,
        size: int = 1,
        name: Optional[str] = None,
        dpath: Optional[Any] = None,
        rootid: Optional[str] = None,
        environ: Optional[Dict[str, str]] = None,
        preamble: Optional[List[str]] = None,
        gpus: Optional[Any] = None,
        gres: Optional[Any] = None,
    ) -> None:
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
        if size <= 0:
            raise ValueError(f'tmux queue size must be positive got size={size}')
        self.size = size
        self.environ = environ
        self.fpath = self.dpath / f'run_queues_{self.name}.sh'

        if gpus is None and gres is not None:
            gpus = gres

        self.gpus = gpus

        self.cmd_verbose = 2

        self.jobs = []
        self.preamble = []

        self._tmux_session_prefix = 'cmdq_'
        self.job_info_dpath = self.dpath / 'job_info'

        self._new_workers()

        if preamble is not None:
            self.add_preamble_commands(preamble)

    @classmethod
    def is_available(cls) -> bool:
        """
        Determines if we can run the tmux queue or not.
        """
        return ub.find_exe('tmux')

    def _new_workers(self, start: int = 0) -> List[serial_queue.SerialQueue]:
        import itertools as it
        per_worker_environs = [self.environ] * self.size
        if self.gpus:
            # TODO: more sophisticated GPU policy?
            per_worker_environs = [
                ub.dict_union(e, {
                    'CUDA_VISIBLE_DEVICES': str(cvd),
                })
                for cvd, e in zip(it.cycle(self.gpus), per_worker_environs)
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

    def __nice__(self) -> str:
        return ub.urepr(self.jobs)

    def _semaphore_wait_command(self, flag_fpaths: Iterable[str], msg: str) -> str:
        r"""
        TODO: use flock? or inotify?

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

        Example:
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> flag_fpaths = ['foo.txt']
            >>> msg = 'waiting'
            >>> command = TMUXMultiQueue._semaphore_wait_command(None, flag_fpaths, msg)
            >>> print(command)
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

    def order_jobs(self) -> None:
        """
        TODO: ability to shuffle jobs subject to graph constraints

        Example:
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> self = TMUXMultiQueue(5, 'foo')
            >>> job1a = self.submit('echo hello && sleep 0.5')
            >>> job1b = self.submit('echo hello && sleep 0.5')
            >>> job2a = self.submit('echo hello && sleep 0.5', depends=[job1a])
            >>> job2b = self.submit('echo hello && sleep 0.5', depends=[job1b])
            >>> job3 = self.submit('echo hello && sleep 0.5', depends=[job2a, job2b])
            >>> self.print_commands()

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
            >>> self.print_commands()
            >>> # self.run(block=True)

        Example:
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> self = TMUXMultiQueue(2, 'test-order-case')
            >>> self.submit('echo slow1', name='slow1')
            >>> self.submit('echo fast1', name='fast1')
            >>> self.submit('echo slow2', name='slow2')
            >>> self.submit('echo fast2', name='fast2')
            >>> self.submit('echo slow3', name='slow3')
            >>> self.submit('echo fast3', name='fast3')
            >>> self.submit('echo slow4', name='slow4')
            >>> self.submit('echo fast4', name='fast4')
            >>> self.print_graph(reduced=False)
            >>> self.print_commands()
        """
        import networkx as nx
        graph = self._dependency_graph()

        # Get rid of implicit dependencies
        try:
            reduced_graph = nx.transitive_reduction(graph)
        except Exception as ex:
            print('ex = {!r}'.format(ex))
            print('graph = {!r}'.format(graph))
            print(len(graph.nodes))
            print('graph.nodes = {}'.format(ub.urepr(graph.nodes, nl=1)))
            print('graph.edges = {}'.format(ub.urepr(graph.edges, nl=1)))
            print(len(graph.edges))
            print(graph.is_directed())
            print(nx.is_forest(graph))
            print(nx.is_directed_acyclic_graph(graph))
            simple_cycles = list(nx.cycles.simple_cycles(graph))
            print('simple_cycles = {}'.format(ub.urepr(simple_cycles, nl=1)))
            nx.write_network_text(graph, print, end="")
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

        # TODO: can we use nx.topological_generations for a more elegant
        # solution here?

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
            # Weighting by job heaviness would help here.
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

        if self.size == 1:
            # If we can only execute one command at a time we dont need to
            # split up the ranks, which means we dont need semaphores.
            serial_groups = []
            for rank_jobs in ranked_job_groups:
                serial_groups.extend(list(ub.flatten(rank_jobs)))
            ranked_job_groups = [[serial_groups]]

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
            for header_command in self.preamble:
                worker.add_preamble_command(header_command)
        self.workers = queue_workers

    def finalize_text(self, **kwargs: Any) -> str:
        self.order_jobs()
        # Create a driver script
        driver_lines = [ub.codeblock(
            f'''
            #!/bin/bash
            # Driver script to start the tmux-queue
            echo "Submitting {self.num_real_jobs} jobs to a tmux queue"
            ''')]
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
        driver_lines += [f'echo "Spread jobs across {len(self.workers)} tmux workers"']
        driver_text = '\n\n'.join(driver_lines)
        return driver_text

    def write(self) -> Any:
        self.order_jobs()
        for queue in self.workers:
            queue.write()
        super().write()

    def kill_other_queues(self, ask_first: bool = True) -> None:
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
        # print(f'other_session_ids={other_session_ids}')
        if other_session_ids:
            print(f'Detected {len(other_session_ids)} other running cmd-queue sessions with the same name')
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

    def handle_other_sessions(self, other_session_handler: str) -> None:
        if other_session_handler == 'auto':
            from cmd_queue.tmux_queue import has_stdin
            if has_stdin():
                other_session_handler = 'ask'
            else:
                other_session_handler = 'kill'  # default headless behavior
        if other_session_handler == 'ask':
            self.kill_other_queues(ask_first=True)
        elif other_session_handler == 'kill':
            self.kill_other_queues(ask_first=False)
        elif other_session_handler == 'ignore':
            ...
        else:
            raise KeyError(other_session_handler)

    def run(
        self,
        block: bool = True,
        onfail: str = 'kill',
        onexit: str = '',
        system: bool = False,
        with_textual: str = 'auto',
        check_other_sessions: Optional[bool] = None,
        other_session_handler: str = 'auto',
        monitor: str = 'inline',
        **kw: Any,
    ) -> None:
        """
        Execute the queue.

        Args:
            other_session_handler (str):
                How to handle potentially conflicting existing tmux runners
                with the same queue name.  Can be 'kill', 'ask', or 'ignore',
                or 'auto' - which defaults to 'ask' if stdin is available and
                'kill' if it is not.

            monitor (str):
                Where the live status UI runs while ``block=True``.

                * ``'inline'`` (default): renders in the current shell, just
                  like today. Closing the shell loses the view.
                * ``'tmux'``: spawns ``cmd_queue monitor --manifest=...``
                  in a detached tmux session and (when interactive) attaches
                  the user to it. The current process still blocks until
                  jobs finish (and runs the post-run cleanup), so detaching
                  the tmux UI does not return control to the caller.
                * ``'none'``: no UI; the call still blocks via a headless
                  state-file poll when ``block=True``.
        """

        if not self.is_available():
            raise Exception('tmux not found')

        # TODO: need to port or generalize some of this logic to serial / slurm
        # queues.
        self.handle_other_sessions(other_session_handler)

        if check_other_sessions:
            ub.schedule_deprecation(
                'tmux_queue', 'check_other_sessions', 'argument')
            if check_other_sessions == 'auto':
                if not has_stdin():
                    check_other_sessions = False
            if check_other_sessions:
                self.kill_other_queues(ask_first=True)

        self.write()
        manifest_path = self._write_monitor_manifest()
        ub.cmd(f'bash {self.fpath}', verbose=self.cmd_verbose, check=True,
               system=system)
        if not block:
            return None
        return self._dispatch_monitor(
            monitor=monitor,
            manifest_path=manifest_path,
            onfail=onfail,
            onexit=onexit,
            with_textual=with_textual,
        )

    def _print_done_summary(self, agg_state: Dict[str, Any]) -> None:
        from rich import print as rich_print
        failed = agg_state.get('failed', 0)
        passed = agg_state.get('passed', 0)
        skipped = agg_state.get('skipped', 0)
        total = agg_state.get('total', 0)
        if failed:
            status_str = '[bold red]FAILED[/bold red]'
        else:
            status_str = '[bold green]PASSED[/bold green]'
        rich_print(
            f'\nQueue complete: {status_str}  '
            f'passed=[green]{passed}[/green]  '
            f'failed=[red]{failed}[/red]  '
            f'skipped=[yellow]{skipped}[/yellow]  '
            f'total={total}'
        )
        failed_jobs, skipped_jobs, status_by_name = (
            self._collect_failed_and_skipped()
        )
        if failed_jobs:
            rich_print('[bold red]Failed jobs:[/bold red]')
            any_log_missing = False
            for job in failed_jobs:
                log_fpath = getattr(job, 'log_fpath', None)
                if (getattr(job, 'log', False) and log_fpath is not None
                        and log_fpath.exists()):
                    rich_print(
                        f'  [red]{job.name}[/red]  log: {log_fpath}'
                    )
                else:
                    any_log_missing = True
                    rich_print(f'  [red]{job.name}[/red]  [dim](no log)[/dim]')
            if any_log_missing:
                rich_print(
                    '[yellow]Note:[/yellow] failure logs are not '
                    'enabled for some failed jobs (pass log=True at '
                    'submit time to capture stdout/stderr to disk).'
                )
        if skipped_jobs:
            rich_print('[bold yellow]Skipped jobs:[/bold yellow]')
            for job in skipped_jobs:
                reason = self._skip_reason(job, status_by_name)
                if reason:
                    rich_print(
                        f'  [yellow]{job.name}[/yellow]  ({reason})'
                    )
                else:
                    rich_print(f'  [yellow]{job.name}[/yellow]')

    def _dispatch_monitor(
        self,
        monitor: str,
        manifest_path: Any,
        onfail: str,
        onexit: str,
        with_textual: str = 'auto',
    ) -> Any:
        if monitor == 'inline':
            return self.monitor(
                with_textual=with_textual,
                onfail=onfail,
                onexit=onexit,
            )
        if monitor == 'none':
            from rich import print as rich_print
            rich_print(
                '[bold]Queue running detached.[/bold] '
                f'Reattach with: cmd_queue monitor --manifest={manifest_path}'
            )
            agg_state = self._headless_block_until_done()
            self._print_done_summary(agg_state)
            return agg_state
        if monitor == 'tmux':
            if not ub.find_exe('tmux'):
                import warnings
                warnings.warn(
                    "monitor='tmux' requested but tmux not found; "
                    "falling back to inline monitor.")
                return self.monitor(
                    with_textual=with_textual,
                    onfail=onfail,
                    onexit=onexit,
                )
            extra_args = []
            if onfail:
                extra_args.append(f'--onfail={onfail}')
            if onexit:
                extra_args.append(f'--onexit={onexit}')
            session_name = f'cmdq-monitor-{self.pathid}'
            from rich import print as rich_print
            rich_print(
                f'[bold]Launching monitor in tmux session[/bold] {session_name}'
            )
            tmux.spawn_monitor_session(
                session_name=session_name,
                manifest_path=manifest_path,
                attach=False,
                verbose=0,
                extra_args=extra_args,
            )
            # Don't pull the user's terminal into the monitor session; let
            # them attach on demand and freely detach back to this shell.
            def _is_finished() -> bool:
                _, finished, _ = self._build_status_table()
                return finished
            tmux.block_with_attach_prompt(
                session_name=session_name,
                is_finished_fn=_is_finished,
                refresh_rate=1.0,
                label=f'queue {self.name}',
            )
            _, _, agg_state = self._build_status_table()
            self._print_done_summary(agg_state)
            return agg_state
        raise ValueError(
            f"monitor must be one of 'inline', 'tmux', 'none'; got {monitor!r}"
        )

    def _headless_block_until_done(self, refresh_rate: float = 1.0) -> Any:
        """Poll the per-worker state files until all workers are finished.

        Used as the parent-side block-wait when the visible monitor is
        running elsewhere (in a tmux session, or not at all).
        """
        import time
        while True:
            table, finished, agg_state = self._build_status_table()
            if finished:
                return agg_state
            time.sleep(refresh_rate)

    def read_state(self) -> Any:
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

    def serial_run(self) -> None:
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

    def monitor(
        self,
        refresh_rate: float = 0.4,
        with_textual: str = 'auto',
        onfail: str = '',
        onexit: str = '',
    ) -> None:
        """
        Monitor progress until the jobs are done.

        Owns post-run cleanup so that whether the monitor runs inline or
        in a separate process (tmux monitor backend, ``cmd_queue
        monitor`` CLI), the same finalization happens.

        Args:
            onfail (str): if ``'kill'`` and the queue ends with no
                failures, kill the now-idle tmux sessions. (The arg is
                named for historical reasons; the original behavior was
                "tear down on a clean exit, leave alive on failure so
                the user can investigate.")
            onexit (str): if ``'capture'``, dump tmux pane contents
                after the queue finishes.

        CommandLine:
            xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.monitor:0
            INTERACTIVE_TEST=1 xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.monitor:1

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
            >>> self.print_commands()
            >>> if self.is_available():
            >>>     self.run(block=True, check_other_sessions=0)

        Example:
            >>> # xdoctest: +REQUIRES(env:INTERACTIVE_TEST)
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> # Setup a lot of longer running jobs
            >>> n = 2
            >>> self = TMUXMultiQueue(size=n, name='demo_cmd_queue')
            >>> first_job = None
            >>> for i in range(n):
            ...     prev_job = None
            ...     for j in range(4):
            ...         command = f'sleep 1 && echo "This is job {i}.{j}"'
            ...         job = self.submit(command, depends=prev_job)
            ...         prev_job = job
            ...         first_job = first_job or job
            >>> command = f'sleep 1 && echo "this is the last job"'
            >>> job = self.submit(command, depends=[prev_job, first_job])
            >>> self.print_commands(style='rich')
            >>> self.print_graph()
            >>> if self.is_available():
            ...     self.run(block=True, other_session_handler='kill')
        """
        # print('Start monitor')
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
        if onexit == 'capture':
            self.capture()
        if onfail == 'kill' and not agg_state.get('failed'):
            self.kill()
        self._print_done_summary(agg_state)
        return agg_state

    def _textual_monitor(self):
        from rich import print as rich_print

        if 0:
            print('Kill commands:')
            for command in self._kill_commands():
                print(command)

        is_running = True
        while is_running:
            table_fn = self._build_status_table
            app = CmdQueueMonitorApp(table_fn, kill_fn=self.kill)
            app.run()

            table, finished, agg_state = self._build_status_table()
            rich_print(table)

            if app.graceful_exit:
                is_running = False
            else:
                from rich.prompt import Confirm
                flag = Confirm.ask('do you to kill the procs?')
                if flag:
                    self.kill()
                    is_running = False

    def _collect_failed_and_skipped(self):
        """Walk worker.jobs and partition into failed / skipped lists.

        A job is *failed* if its fail_fpath exists, and *skipped* if its
        skip_fpath exists. The two are mutually exclusive: the bash
        boilerplate writes one or the other but never both.
        """
        failed = []
        skipped = []
        # Map job name -> status so we can fill in skip reasons.
        status_by_name: Dict[str, str] = {}
        for worker in self.workers:
            for job in getattr(worker, 'jobs', []):
                fail_fpath = getattr(job, 'fail_fpath', None)
                skip_fpath = getattr(job, 'skip_fpath', None)
                if fail_fpath is not None and fail_fpath.exists():
                    failed.append(job)
                    if getattr(job, 'name', None):
                        status_by_name[job.name] = 'failed'
                elif skip_fpath is not None and skip_fpath.exists():
                    skipped.append(job)
                    if getattr(job, 'name', None):
                        status_by_name[job.name] = 'skipped'
        return failed, skipped, status_by_name

    @staticmethod
    def _skip_reason(job: Any, status_by_name: Dict[str, str]) -> str:
        """Best-effort explanation of why a job was skipped.

        Looks at the job's recorded dependency names and reports the
        first one whose status is not 'passed'. Returns a short string
        like 'dep proc-A failed' or '' if no clear reason.
        """
        depends = getattr(job, 'depends', None) or []
        bad = []
        for dep_name in depends:
            if not dep_name:
                continue
            st = status_by_name.get(dep_name)
            if st in ('failed', 'skipped'):
                bad.append((dep_name, st))
        if not bad:
            return ''
        if len(bad) == 1:
            name, st = bad[0]
            return f'dep {name} {st}'
        names = ', '.join(f'{n} {s}' for n, s in bad)
        return f'deps: {names}'

    def _build_failed_jobs_renderable(self) -> Any:
        """Renderable summary of failed and skipped jobs, or None.

        Used by the live monitor to surface failures and skips (and the
        reason for each skip) as soon as they happen, rather than only
        in the post-run summary.
        """
        failed, skipped, status_by_name = self._collect_failed_and_skipped()
        if not failed and not skipped:
            return None
        from rich.table import Table
        from rich.console import Group
        from rich.text import Text

        renderables = []
        any_log_missing = False

        if failed:
            ftable = Table(
                title='Failed jobs', title_style='bold red',
                show_header=True, header_style='red',
            )
            ftable.add_column('name', style='red')
            ftable.add_column('log')
            for job in failed:
                log_fpath = getattr(job, 'log_fpath', None)
                if (getattr(job, 'log', False) and log_fpath is not None
                        and log_fpath.exists()):
                    ftable.add_row(job.name, str(log_fpath))
                else:
                    any_log_missing = True
                    ftable.add_row(job.name, '[dim](no log)[/dim]')
            renderables.append(ftable)

        if skipped:
            stable = Table(
                title='Skipped jobs', title_style='bold yellow',
                show_header=True, header_style='yellow',
            )
            stable.add_column('name', style='yellow')
            stable.add_column('reason')
            for job in skipped:
                reason = self._skip_reason(job, status_by_name)
                stable.add_row(job.name, reason or '[dim](unknown)[/dim]')
            renderables.append(stable)

        if any_log_missing:
            renderables.append(Text(
                'Note: failure logs are not enabled for some failed '
                'jobs (pass log=True at submit time).',
                style='yellow',
            ))

        if len(renderables) == 1:
            return renderables[0]
        return Group(*renderables)

    def _build_live_renderable(self):
        from rich.console import Group
        table, finished, agg_state = self._build_status_table()
        failed = self._build_failed_jobs_renderable()
        renderable = Group(table, failed) if failed is not None else table
        return renderable, finished, agg_state

    def _simple_rich_monitor(self, refresh_rate=0.4):
        import time
        from rich.live import Live
        if 0:
            print('Kill commands:')
            for command in self._kill_commands():
                print(command)
        try:
            renderable, finished, agg_state = self._build_live_renderable()
            with Live(renderable, refresh_per_second=4) as live:
                while not finished:
                    time.sleep(refresh_rate)
                    renderable, finished, agg_state = (
                        self._build_live_renderable()
                    )
                    live.update(renderable)
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

    def print_commands(self, *args: Any, **kwargs: Any) -> None:
        r"""
        Print info about the commands, optionally with rich

        Args:
            with_status (bool):
                tmux / serial only, show bash status boilerplate

            with_gaurds (bool):
                tmux / serial only, show bash guards boilerplate

            with_locks (bool):
                tmux, show tmux lock boilerplate

            exclude_tags (List[str] | None):
                if specified exclude jobs submitted with these tags.

            style (str):
                can be 'colors', 'rich', or 'plain'

            **kwargs: extra backend-specific args passed to finalize_text

        CommandLine:
            xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.print_commands

        Example:
            >>> from cmd_queue.tmux_queue import *  # NOQA
            >>> self = TMUXMultiQueue(size=2, name='test-print-commands-tmux-queue')
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
            >>> self.print_commands(with_status=1, with_gaurds=1, with_locks=1, style='rich')
            >>> print('\n\n---\n\n')
            >>> self.print_commands(with_status=0, with_gaurds=1, with_locks=1, style='rich')
            >>> print('\n\n---\n\n')
            >>> self.print_commands(with_status=0, with_gaurds=0, with_locks=0, style='rich')
            >>> print('\n\n---\n\n')
            >>> self.print_commands(with_status=0, with_gaurds=0, with_locks=0,
            ...             style='auto', exclude_tags='boilerplate')
        """
        self.order_jobs()
        for queue in self.workers:
            queue.print_commands(*args, **kwargs)
        super().print_commands(*args, **kwargs)

    def current_output(self) -> None:
        for queue in self.workers:
            print('\n\nqueue = {!r}'.format(queue))
            # First print out the contents for debug
            tmux.capture_pane(target_session=queue.pathid, verbose=self.cmd_verbose)

    def _print_commands(self):
        # First print out the contents for debug
        for queue in self.workers:
            command1 = tmux._capture_pane_command(target_session=queue.pathid)
            yield command1

    def _kill_commands(self):
        for queue in self.workers:
            command2 = tmux._kill_session_command(target_session=queue.pathid)
            yield command2

    def capture(self) -> None:
        for command in self._print_commands():
            ub.cmd(command, verbose=self.cmd_verbose)

    def kill(self) -> None:
        # Kills all the tmux panes
        for command in self._kill_commands():
            ub.cmd(command, verbose=self.cmd_verbose)

    def _tmux_current_sessions(self):
        sessions = tmux.list_sessions()
        return sessions

    def _build_monitor_manifest(self) -> Dict[str, Any]:
        """Snapshot enough state for an out-of-process monitor to reattach."""
        workers_info = []
        for worker in self.workers:
            jobs_info = []
            for job in getattr(worker, 'jobs', []):
                fail_fpath = getattr(job, 'fail_fpath', None)
                skip_fpath = getattr(job, 'skip_fpath', None)
                log_fpath = getattr(job, 'log_fpath', None)
                depends = getattr(job, 'depends', None) or []
                depends_names = [
                    getattr(d, 'name', None) for d in depends
                    if d is not None and getattr(d, 'name', None)
                ]
                jobs_info.append({
                    'name': getattr(job, 'name', None),
                    'log': bool(getattr(job, 'log', False)),
                    'fail_fpath': str(fail_fpath) if fail_fpath else None,
                    'skip_fpath': str(skip_fpath) if skip_fpath else None,
                    'log_fpath': str(log_fpath) if log_fpath else None,
                    'depends': depends_names,
                })
            workers_info.append({
                'name': worker.name,
                'rootid': worker.rootid,
                'dpath': str(worker.dpath),
                'pathid': worker.pathid,
                'state_fpath': str(worker.state_fpath),
                'fpath': str(worker.fpath),
                'environ': dict(worker.environ or {}),
                'jobs': jobs_info,
            })
        return {
            'backend': 'tmux',
            'name': self.name,
            'rootid': self.rootid,
            'pathid': self.pathid,
            'dpath': str(self.dpath),
            'fpath': str(self.fpath),
            'size': self.size,
            'gpus': self.gpus,
            'tmux_session_prefix': self._tmux_session_prefix,
            'workers': workers_info,
        }

    def _write_monitor_manifest(self) -> Any:
        """Persist the monitor manifest to ``<dpath>/monitor_manifest.json``."""
        from cmd_queue import monitor_manifest as mm
        path = mm.manifest_path_for_dpath(self.dpath)
        manifest = self._build_monitor_manifest()
        mm.write_manifest(manifest, path)
        mm.update_active_index(self.name, path)
        return path

    @classmethod
    def _from_manifest(cls, manifest: Dict[str, Any]) -> "TMUXMultiQueue":
        """Reconstruct a queue suitable for ``monitor()`` / ``kill()`` only."""
        self = cls.__new__(cls)
        # Initialize the base Queue state without re-creating workers / dpaths.
        base_queue.Queue.__init__(self)
        self.name = manifest['name']
        self.rootid = manifest['rootid']
        self.pathid = manifest.get('pathid', '{}_{}'.format(self.name, self.rootid))
        self.dpath = ub.Path(manifest['dpath'])
        self.fpath = ub.Path(manifest['fpath'])
        self.size = manifest['size']
        self.gpus = manifest.get('gpus')
        self.environ = {}
        self.cmd_verbose = 2
        self._tmux_session_prefix = manifest.get('tmux_session_prefix', 'cmdq_')
        self.job_info_dpath = self.dpath / 'job_info'
        self.preamble = []
        self.jobs = []
        import types
        workers = []
        for w in manifest.get('workers', []):
            worker = serial_queue.SerialQueue(
                name=w['name'],
                rootid=w['rootid'],
                dpath=ub.Path(w['dpath']),
                environ=w.get('environ') or {},
            )
            # Rehydrate lightweight job stubs so the monitor can show
            # per-job failure rows. We don't need the full BashJob — only
            # the attributes the failed-jobs renderer reads.
            stubs = []
            for j in w.get('jobs') or []:
                stubs.append(types.SimpleNamespace(
                    name=j.get('name'),
                    log=bool(j.get('log', False)),
                    fail_fpath=ub.Path(j['fail_fpath']) if j.get('fail_fpath') else None,
                    skip_fpath=ub.Path(j['skip_fpath']) if j.get('skip_fpath') else None,
                    log_fpath=ub.Path(j['log_fpath']) if j.get('log_fpath') else None,
                    depends=list(j.get('depends') or []),
                ))
            worker.jobs = stubs
            workers.append(worker)
        self.workers = workers
        return self


def has_stdin() -> bool:
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
    if not hasattr(CmdQueueMonitorApp, 'run'):
        raise ImportError('Current textual monitor is broken on new versions')
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


    # Example of passing environment variables (but does not use new-session)
    export MYVAR1=123
    export MYVAR2=456
    tmux -L MYVAR1 -L MYVAR2
    echo $MYVAR1
    echo $MYVAR2

    # References
    https://unix.stackexchange.com/questions/743817/how-to-start-tmux-in-a-way-that-it-inherits-all-environment-variables-from-the-c
    https://stackoverflow.com/questions/20701757/tmux-setting-environment-variables-for-sessions
    https://github.com/orgs/tmux/discussions/3659

    # Can start a new session with a specific environment variable
    export MYVAR1=123
    tmux new-session -d -s my_session_id -e "MYVAR1=$MYVAR1" -- "bash"

    # Show the environment of the new session
    tmux show-env -t my_session_id

    tmux ls
    tmux kill-session -t my_session_id

    tmux new-session -d -s my_session_id -e "MYVAR1" -- "bash"



    #### to start a tmux session with 4 panes
    tmux new-session -d -s my_session_id1 "bash"
    tmux send -t my_session_id1 "tmux split-window -h -t 0" Enter
    tmux send -t my_session_id1 "tmux split-window -v -t 0" Enter
    tmux send -t my_session_id1 "tmux split-window -v -t 2" Enter

    # Now send a command to each pane
    tmux send -t my_session_id1 "tmux select-pane -t 0" Enter
    tmux send -t my_session_id1 "echo pane0" Enter
    tmux send -t my_session_id1 "tmux select-pane -t 1" Enter
    tmux send -t my_session_id1 "echo pane1" Enter
    tmux send -t my_session_id1 "tmux select-pane -t 2" Enter
    tmux send -t my_session_id1 "echo pane2" Enter
    tmux send -t my_session_id1 "tmux select-pane -t 3" Enter
    tmux send -t my_session_id1 "echo pane3" Enter

    # https://stackoverflow.com/questions/54954177/how-to-write-a-tmux-script-so-that-it-automatically-split-windows-and-opens-a-se
    # https://tmuxcheatsheet.com/
    # https://gist.github.com/Starefossen/5955406

    # List the bindings
    tmux list-keys

    # Can arange the splits in a session via a preset layout
    # Preset layouts are:
    # even-horizontal, even-vertical, main-horizontal, main-vertical, or tiled.
    tmux select-layout -t "${SESSION_NAME}" even-vertical

    # switch to an existing session
    tmux switch -t "${SESSION_NAME}"

    """
