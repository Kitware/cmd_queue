"""
Simplify chaining of multiple shell commands


Serves as a frontend for several DAG backends, including our own custom tmux
queue. We also support slurm and will soon support airflow.

Example:
    >>> import cmd_queue
    >>> print(cmd_queue.Queue.available_backends())  # xdoctest: +IGNORE_WANT
    ['serial', 'tmux', 'slurm']
    >>> queue = cmd_queue.Queue.create(backend='serial')
    >>> job1a = queue.submit('echo hello && sleep 0.5')
    >>> job1b = queue.submit('echo hello && sleep 0.5')
    >>> job2a = queue.submit('echo hello && sleep 0.5', depends=[job1a])
    >>> job2b = queue.submit('echo hello && sleep 0.5', depends=[job1b])
    >>> job3 = queue.submit('echo hello && sleep 0.5', depends=[job2a, job2b])
    >>> jobX = queue.submit('echo hello && sleep 0.5', depends=[])
    >>> jobY = queue.submit('echo hello && sleep 0.5', depends=[jobX])
    >>> jobZ = queue.submit('echo hello && sleep 0.5', depends=[jobY])
    ...
    >>> queue.print_graph()
    Graph:
    ╟── -job-0
    ╎   └─╼ -job-2
    ╎       └─╼ -job-4 ╾ -job-3
    ╟── -job-1
    ╎   └─╼ -job-3
    ╎       └─╼  ...
    ╙── -job-5
        └─╼ -job-6
            └─╼ -job-7
    >>> queue.rprint(with_rich=0, colors=0)
    # --- ...
    #!/bin/bash
    #
    # Jobs
    #
    ### Command 1 / 8 - -job-0
    echo hello && sleep 0.5
    #
    ### Command 2 / 8 - -job-1
    echo hello && sleep 0.5
    #
    ### Command 3 / 8 - -job-2
    echo hello && sleep 0.5
    #
    ### Command 4 / 8 - -job-3
    echo hello && sleep 0.5
    #
    ### Command 5 / 8 - -job-4
    echo hello && sleep 0.5
    #
    ### Command 6 / 8 - -job-5
    echo hello && sleep 0.5
    #
    ### Command 7 / 8 - -job-6
    echo hello && sleep 0.5
    #
    ### Command 8 / 8 - -job-7
    echo hello && sleep 0.5
    >>> # Note: xdoctest doesnt seem to capture the set -x parts. Not sure why.
    >>> queue.run(block=True)  # xdoctest: +IGNORE_WANT
    ┌─── START CMD ───
    [ubelt.cmd] ...@...:...$ bash ...sh
    hello
    + echo hello
    + sleep 0.5
    hello
    + echo hello
    + sleep 0.5
    + echo hello
    hello
    + sleep 0.5
    + echo hello
    hello
    + sleep 0.5
    + echo hello
    hello
    + sleep 0.5
    + echo hello
    hello
    + sleep 0.5
    hello
    + echo hello
    + sleep 0.5
    hello
    + echo hello
    + sleep 0.5
    └─── END CMD ───

"""

__mkinit__ = """
mkinit -m cmd_queue
"""
__version__ = '0.1.0'
__author__ = 'Kitware Inc., Jon Crall'
__author_email__ = 'kitware@kitware.com, jon.crall@kitware.com'
__url__ = 'https://gitlab.kitware.com/computer-vision/cmd_queue'


__submodules__ = {
    'base_queue': ['Queue'],
}
from cmd_queue import base_queue

from cmd_queue.base_queue import (Queue,)

__all__ = ['Queue', 'base_queue']
