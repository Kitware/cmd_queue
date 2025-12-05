Command Queue - cmd_queue
=========================

.. ..  |Appveyor| |Codecov|

|Pypi| |Downloads| |GitlabCIPipeline| |GitlabCICoverage| |ReadTheDocs|


+------------------+-------------------------------------------------------------------------------------+
| Read the docs    | https://cmd-queue.readthedocs.io                                                    |
+------------------+-------------------------------------------------------------------------------------+
| Gitlab           | https://gitlab.kitware.com/computer-vision/cmd_queue                                |
+------------------+-------------------------------------------------------------------------------------+
| Pypi             | https://pypi.org/project/cmd_queue                                                  |
+------------------+-------------------------------------------------------------------------------------+
| Slides           | https://docs.google.com/presentation/d/1BjJkjMx6bxu1uek-hAGpwj760u9rraVn7st8J5OsZME |
+------------------+-------------------------------------------------------------------------------------+


This is a simple module for "generating" a bash script that schedules multiples
jobs (in parallel if possible) on a single machine.

Overview
========

cmd_queue lets you define a DAG of shell commands once and then materialize it
into runnable scripts for different environments. The same queue definition can
run sequentially in the foreground, distribute work across local tmux sessions,
or emit slurm submissions for HPC clusters.

Key capabilities include:

* Python and Bash APIs for describing jobs, dependencies, and metadata.
* DAG visualization via ``print_graph`` and command inspection via
  ``print_commands`` before execution.
* Swappable backends so you can iterate locally in serial or tmux and later
  scale out with slurm.
* Rich-based monitoring / live control when running interactive queues.

Project Layout
==============

* ``cmd_queue/`` contains the implementation, with backends in
  ``serial_queue.py``, ``tmux_queue.py``, and ``slurm_queue.py`` plus CLI
  helpers in ``main.py`` and ``cli_boilerplate.py``.
* ``examples/`` provides sample pipelines.
* ``docs/`` hosts the Sphinx documentation (``make -C docs html``).
* ``tests/`` contains automated checks; ``run_tests.py`` is a convenience entry
  point for running them with coverage.
* Helper scripts such as ``run_developer_setup.sh`` (installs dependencies in
  editable mode) and ``run_linter.sh`` (flake8) support local development.

Quickstart
==========

Python API
----------

.. code:: python

   import cmd_queue
   queue = cmd_queue.Queue.create(backend='serial', name='demo')
   job_a = queue.submit('echo "hello"', name='job_a')
   job_b = queue.submit('echo "after a"', depends=[job_a], name='job_b')
   queue.print_commands()

Bash / CLI
----------

.. code:: bash

   # Create a queue persisted as JSON under ~/.cache/cmd_queue/cli
   cmd_queue new "my_queue"

   # Add jobs; the double dash forwards the remaining arguments to the job
   cmd_queue submit "my_queue" --  echo "\"do work\""
   cmd_queue submit "my_queue" --name="post" --depends="my_queue-job-0" -- \
       echo "\"after first job\""

   # Inspect and then execute
   cmd_queue show "my_queue"
   cmd_queue run "my_queue" --backend=serial

Additional usage examples – including tmux and slurm execution – live in the
module docstrings (``cmd_queue.__init__``) and the online documentation.


Notice the ``--backend`` arugment. There are 3 backends with increasing levels
of complexity: serial, tmux, and slurm.

In serial mode, a single bash script gets written that executes your jobs in
sequence. There are no external dependencies

In tmux mode, multiple tmux sessions get opened and each of them executes your
independent parts of your jobs. Dependencies are handled.

In slurm mode, a real heavy-weight scheduling algorithm is used. In this mode
we simply convert your jobs to slurm commands and execute them.

Under the hood we build a DAG based on your specified dependencies and use this
to appropriately order jobs.

By default, bash scripts that would execute your jobs print to the console.
This gives the user fine-grained control if they only want to run a subset of a
pipeline manually. But if asked to run, cmd_queue will execute the bash jobs.

Features
~~~~~~~~

* Bash command scheduling

* Execution is optional, can just print commands instead

* No-parallelism always-available serial backend

* Tmux based lightweight backend

* Slurm based heavyweight backend

* Python and Bash interface

* Rich monitoring / live-control


Installation
============

The cmd_queue package is available on pypi.

.. code:: bash

    pip install cmd_queue

The serial queue backend will always work. To gain access other backends you
must install their associated dependencies. The tmux backend is the easiest and
simply requires that tmux is installed (e.g. ``sudo apt install tmux`` on
Debian systems).

Other backends require more complex setups. The slurm backend will require that
`slurm is installed <https://slurm.schedmd.com/quickstart_admin.html>`_ and the
daemon is running. The slurm backend is functional and tested, but improvements
can still be made (help wanted). The airflow backend similarly requires a
configured airflow server, but is not fully functional or tested (contributions
to make airflow work / easier are wanted!).


Tmux Queue Demo
===============

After installing, the following command runs a demo of the tmux queue:

.. code:: bash

   # Reproduce the
   INTERACTIVE_TEST=1 xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.monitor:1


This executes the following code, which creates two parallel tmux workers and
submits several bash jobs with non-trivial dependencies.

.. code:: python

     # xdoctest: +REQUIRES(env:INTERACTIVE_TEST)
     from cmd_queue.tmux_queue import *  # NOQA
     # Setup a lot of longer running jobs
     n = 2
     self = TMUXMultiQueue(size=n, name='demo_cmd_queue')
     first_job = None
     for i in range(n):
         prev_job = None
         for j in range(4):
            command = f'sleep 1 && echo "This is job {i}.{j}"'
            job = self.submit(command, depends=prev_job)
            prev_job = job
            first_job = first_job or job
    command = f'sleep 1 && echo "this is the last job"'
    job = self.submit(command, depends=[prev_job, first_job])
    self.print_commands(style='rich')
    self.print_graph()
    if self.is_available():
        self.run(block=True, other_session_handler='kill')


When running the ``print_commands`` command will first display all of the submitted
commands that will be distributed across multiple new tmux sessions. These are
the commands will be executed. This is useful for spot checking that your bash
command templating is correct before the queue is executed with ``run``.


.. .. Screenshot of the print_commands output
.. image:: https://i.imgur.com/rVbyHzM.png
   :height: 300px
   :align: left


The ``print_graph`` command will render the DAG to be executed using
`network text <https://networkx.org/documentation/stable/reference/readwrite/generated/networkx.readwrite.text.write_network_text.html#networkx.readwrite.text.write_network_text>`_.
And finally ``run`` is called with ``block=True``, which starts executing the
DAG and displays progress and job status in rich or textual monitor.

.. .. image:: https://i.imgur.com/RbyTvP9.png
..   :height: 300px
..   :align: left

.. .. Animated gif of the queue from dev/record_demo.sh
.. image:: https://i.imgur.com/4mxFIMk.gif
   :height: 300px
   :align: left


While this is running it is possible to simply attach to a tmux sessions (e.g.
``tmux a``) and inspect a specific queue while it is running. (We recommend
using ``<ctrl-b>s`` inside of a tmux session to view and navigate through the
tmux sessions). Unlike the slurm backend, the entire execution of the DAG is
entirely transparent to the developer! The following screenshot shows the tmux
sessions spawned while running this demo.

.. .. Screenshot of the tmux sessions
.. image:: https://i.imgur.com/46LRK8M.png
   :height: 300px
   :align: left

By default, if there are no errors, these sessions will exit after execution
completes, but this is configurable. Likewise if there are errors, the tmux
sessions will persist to allow for debugging.


Modivation
==========
Recently, I needed to run several jobs on 4 jobs across 2 GPUs and then execute
a script after all of them were done. What I should have done was use slurm or
some other proper queuing system to schedule the jobs, but instead I wrote my
own hacky scheduler using tmux. I opened N (number of parallel workers) tmux
sessions and then I ran independent jobs in each different sessions.

This worked unreasonably well for my use cases, and it was nice to be able to effectively schedule jobs without heavyweight software like slurm on my machine.

Eventually I did get slurm on my machine, and I abstracted the API of my
tmux_queue to be a general "command queue" that can use 1 of 3 backends:
serial, tmux, or slurm.


Niche
=====
There are many DAG schedulers out there:

 * airflow
 * luigi
 * submitit
 * rq_scheduler


The the niche for this is when you have large pipelines of bash commands that
depend on each other and you want to template out those parameters with logic
that you define in Python.

We plan on adding an airflow backend.


Usage
=====


There are two ways to use ``cmd_queue``:

1. In Python create a Queue object, and then call the .submit method to pass it
   a shell invocation. It returns an object that you can use to specify
   dependencies of any further calls to .submit. This simply organizes all of
   your CLI invocations into a bash script, which can be inspected and then
   run. There are different backends that enable parallel execution of jobs
   when dependencies allow.

2. There is a way to use it via the CLI, with details shown in cmd_queue
   --help. Usage is basically the same.  You create a queue, submit jobs to it,
   you can inspect it, and you can run it.


Example usage in Python:

.. code:: python

   import cmd_queue

   # Create a Queue object
   self = cmd_queue.Queue.create(name='demo_queue', backend='serial')

   # Submit bash invocations that you want to run, and mark dependencies.
   job1 = self.submit('echo hello')
   job2 = self.submit('echo world', depends=[job1])
   job3 = self.submit('echo foo')
   job4 = self.submit('echo bar', depends=[job2, job3])
   job5 = self.submit('echo spam', depends=[job1])

   # Print a graph of job dependencies
   self.print_graph()

   # Display the simplified bash script to be executed.
   self.print_commands()

   # Execute the jobs
   self.run()


Example usage in the CLI:

.. code:: bash

    # Create a Queue
    cmd_queue new "demo_cli_queue"

    # Submit bash invocations that you want to run, and mark dependencies.
    cmd_queue submit --jobname job1 "demo_cli_queue" -- echo hello
    cmd_queue submit --jobname job2 --depends job1 "demo_cli_queue" -- echo world
    cmd_queue submit --jobname job3 "demo_cli_queue" -- echo foo
    cmd_queue submit --jobname job4 --depends job1,job2 "demo_cli_queue" -- echo bar
    cmd_queue submit --jobname job5 --depends job1  "demo_cli_queue" -- echo spam

    # Display the simplified bash script to be executed.
    cmd_queue show "demo_cli_queue" --backend=serial

    # Execute the jobs
    cmd_queue run "demo_cli_queue" --backend=serial




Examples
========


All of the dependency checking and book keeping logic is handled in bash
itself. Write (or better yet template) your bash scripts in Python, and then
use cmd_queue to "transpile" these sequences of commands to pure bash.


.. code:: python

   import cmd_queue

   # Create a Queue object
   self = cmd_queue.Queue.create(name='demo_queue', backend='serial')

   # Submit bash invocations that you want to run, and mark dependencies.
   job1 = self.submit('echo hello && sleep 0.5')
   job2 = self.submit('echo world && sleep 0.5', depends=[job1])
   job3 = self.submit('echo foo && sleep 0.5')
   job4 = self.submit('echo bar && sleep 0.5')
   job5 = self.submit('echo spam && sleep 0.5', depends=[job1])
   job6 = self.submit('echo spam && sleep 0.5')
   job7 = self.submit('echo err && false')
   job8 = self.submit('echo spam && sleep 0.5')
   job9 = self.submit('echo eggs && sleep 0.5', depends=[job8])
   job10 = self.submit('echo bazbiz && sleep 0.5', depends=[job9])

   # Display the simplified bash script to be executed.
   self.print_commands()

   # Execute the jobs
   self.run()


This prints the bash commands in an appropriate order to resolve dependencies.


.. code:: bash

    # --- /home/joncrall/.cache/base_queue/demo_queue_2022-04-08_cc9d551e/demo_queue_2022-04-08_cc9d551e.sh

    #!/bin/bash
    #
    # Jobs
    #
    ### Command 1 / 10 - demo_queue-job-0
    echo hello && sleep 0.5
    #
    ### Command 2 / 10 - demo_queue-job-1
    echo world && sleep 0.5
    #
    ### Command 3 / 10 - demo_queue-job-2
    echo foo && sleep 0.5
    #
    ### Command 4 / 10 - demo_queue-job-3
    echo bar && sleep 0.5
    #
    ### Command 5 / 10 - demo_queue-job-4
    echo spam && sleep 0.5
    #
    ### Command 6 / 10 - demo_queue-job-5
    echo spam && sleep 0.5
    #
    ### Command 7 / 10 - demo_queue-job-6
    echo err && false
    #
    ### Command 8 / 10 - demo_queue-job-7
    echo spam && sleep 0.5
    #
    ### Command 9 / 10 - demo_queue-job-8
    echo eggs && sleep 0.5
    #
    ### Command 10 / 10 - demo_queue-job-9
    echo bazbiz && sleep 0.5


The same code can be run in parallel by chosing a more powerful backend.
The tmux backend is the lightest weight parallel backend.

.. code:: python

   # Need to tell the tmux queue how many processes can run at the same time
   import cmd_queue
   self = cmd_queue.Queue.create(size=4, name='demo_queue', backend='tmux')
   job1 = self.submit('echo hello && sleep 0.5')
   job2 = self.submit('echo world && sleep 0.5', depends=[job1])
   job3 = self.submit('echo foo && sleep 0.5')
   job4 = self.submit('echo bar && sleep 0.5')
   job5 = self.submit('echo spam && sleep 0.5', depends=[job1])
   job6 = self.submit('echo spam && sleep 0.5')
   job7 = self.submit('echo err && false')
   job8 = self.submit('echo spam && sleep 0.5')
   job9 = self.submit('echo eggs && sleep 0.5', depends=[job8])
   job10 = self.submit('echo bazbiz && sleep 0.5', depends=[job9])

   # Display the "user-friendly" pure bash
   self.print_commands()

   # Display the real bash that gets executed under the hood
   # that is independencly executable, tracks the success / failure of each job,
   # and manages dependencies.
   self.print_commands(1, 1)

   # Blocking will display a job monitor while it waits for everything to
   # complete
   self.run(block=True)


This prints the sequence of bash commands that will be executed in each tmux session.

.. code:: bash

    # --- /home/joncrall/.cache/base_queue/demo_queue_2022-04-08_a1ef7600/queue_demo_queue_0_2022-04-08_a1ef7600.sh

    #!/bin/bash
    #
    # Jobs
    #
    ### Command 1 / 3 - demo_queue-job-7
    echo spam && sleep 0.5
    #
    ### Command 2 / 3 - demo_queue-job-8
    echo eggs && sleep 0.5
    #
    ### Command 3 / 3 - demo_queue-job-9
    echo bazbiz && sleep 0.5

    # --- /home/joncrall/.cache/base_queue/demo_queue_2022-04-08_a1ef7600/queue_demo_queue_1_2022-04-08_a1ef7600.sh

    #!/bin/bash
    #
    # Jobs
    #
    ### Command 1 / 2 - demo_queue-job-2
    echo foo && sleep 0.5
    #
    ### Command 2 / 2 - demo_queue-job-6
    echo err && false

    # --- /home/joncrall/.cache/base_queue/demo_queue_2022-04-08_a1ef7600/queue_demo_queue_2_2022-04-08_a1ef7600.sh

    #!/bin/bash
    #
    # Jobs
    #
    ### Command 1 / 2 - demo_queue-job-0
    echo hello && sleep 0.5
    #
    ### Command 2 / 2 - demo_queue-job-5
    echo spam && sleep 0.5

    # --- /home/joncrall/.cache/base_queue/demo_queue_2022-04-08_a1ef7600/queue_demo_queue_3_2022-04-08_a1ef7600.sh

    #!/bin/bash
    #
    # Jobs
    #
    ### Command 1 / 1 - demo_queue-job-3
    echo bar && sleep 0.5

    # --- /home/joncrall/.cache/base_queue/demo_queue_2022-04-08_a1ef7600/queue_demo_queue_4_2022-04-08_a1ef7600.sh

    #!/bin/bash
    #
    # Jobs
    #
    ### Command 1 / 1 - demo_queue-job-4
    echo spam && sleep 0.5

    # --- /home/joncrall/.cache/base_queue/demo_queue_2022-04-08_a1ef7600/queue_demo_queue_5_2022-04-08_a1ef7600.sh

    #!/bin/bash
    #
    # Jobs
    #
    ### Command 1 / 1 - demo_queue-job-1
    echo world && sleep 0.5



Slurm mode is the real deal. But you need slurm installed on your machint to
use it. Asking for tmux is a might ligher weight tool. We can specify slurm
options here

.. code:: python

   import cmd_queue
   self = cmd_queue.Queue.create(name='demo_queue', backend='slurm')
   job1 = self.submit('echo hello && sleep 0.5', cpus=4, mem='8GB')
   job2 = self.submit('echo world && sleep 0.5', depends=[job1], parition='default')
   job3 = self.submit('echo foo && sleep 0.5')
   job4 = self.submit('echo bar && sleep 0.5')
   job5 = self.submit('echo spam && sleep 0.5', depends=[job1])
   job6 = self.submit('echo spam && sleep 0.5')
   job7 = self.submit('echo err && false')
   job8 = self.submit('echo spam && sleep 0.5')
   job9 = self.submit('echo eggs && sleep 0.5', depends=[job8])
   job10 = self.submit('echo bazbiz && sleep 0.5', depends=[job9])

   # Display the "user-friendly" pure bash
   self.print_commands()

   # Display the real bash that gets executed under the hood
   # that is independencly executable, tracks the success / failure of each job,
   # and manages dependencies.
   self.print_commands(1, 1)

   # Blocking will display a job monitor while it waits for everything to
   # complete
   self.run(block=True)


This prints the very simple slurm submission script:

.. code:: bash

    # --- /home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/demo_queue-20220408T170615-a9e238b5.sh

    mkdir -p "$HOME/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs"
    JOB_000=$(sbatch --job-name="J0000-demo_queue-20220408T170615-a9e238b5" --cpus-per-task=4 --mem=8000 --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0000-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo hello && sleep 0.5' --parsable)
    JOB_001=$(sbatch --job-name="J0002-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0002-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo foo && sleep 0.5' --parsable)
    JOB_002=$(sbatch --job-name="J0003-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0003-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo bar && sleep 0.5' --parsable)
    JOB_003=$(sbatch --job-name="J0005-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0005-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo spam && sleep 0.5' --parsable)
    JOB_004=$(sbatch --job-name="J0006-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0006-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo err && false' --parsable)
    JOB_005=$(sbatch --job-name="J0007-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0007-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo spam && sleep 0.5' --parsable)
    JOB_006=$(sbatch --job-name="J0001-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0001-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo world && sleep 0.5' "--dependency=afterok:${JOB_000}" --parsable)
    JOB_007=$(sbatch --job-name="J0004-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0004-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo spam && sleep 0.5' "--dependency=afterok:${JOB_000}" --parsable)
    JOB_008=$(sbatch --job-name="J0008-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0008-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo eggs && sleep 0.5' "--dependency=afterok:${JOB_005}" --parsable)
    JOB_009=$(sbatch --job-name="J0009-demo_queue-20220408T170615-a9e238b5" --output="/home/joncrall/.cache/slurm_queue/demo_queue-20220408T170615-a9e238b5/logs/J0009-demo_queue-20220408T170615-a9e238b5.sh" --wrap 'echo bazbiz && sleep 0.5' "--dependency=afterok:${JOB_008}" --parsable)



.. |Pypi| image:: https://img.shields.io/pypi/v/cmd_queue.svg
   :target: https://pypi.python.org/pypi/cmd_queue

.. |Downloads| image:: https://img.shields.io/pypi/dm/cmd_queue.svg
   :target: https://pypistats.org/packages/cmd_queue

.. |ReadTheDocs| image:: https://readthedocs.org/projects/cmd-queue/badge/?version=release
    :target: https://cmd-queue.readthedocs.io/en/release/

.. # See: https://ci.appveyor.com/project/jon.crall/cmd_queue/settings/badges
.. |Appveyor| image:: https://ci.appveyor.com/api/projects/status/py3s2d6tyfjc8lm3/branch/main?svg=true
   :target: https://ci.appveyor.com/project/jon.crall/cmd_queue/branch/main

.. |GitlabCIPipeline| image:: https://gitlab.kitware.com/computer-vision/cmd_queue/badges/main/pipeline.svg
   :target: https://gitlab.kitware.com/computer-vision/cmd_queue/-/jobs

.. |GitlabCICoverage| image:: https://gitlab.kitware.com/computer-vision/cmd_queue/badges/main/coverage.svg?job=coverage
    :target: https://gitlab.kitware.com/computer-vision/cmd_queue/commits/main

.. |CircleCI| image:: https://circleci.com/gh/Erotemic/cmd_queue.svg?style=svg
    :target: https://circleci.com/gh/Erotemic/cmd_queue

.. |Travis| image:: https://img.shields.io/travis/Erotemic/cmd_queue/main.svg?label=Travis%20CI
   :target: https://travis-ci.org/Erotemic/cmd_queue

.. |Codecov| image:: https://codecov.io/github/Erotemic/cmd_queue/badge.svg?branch=main&service=github
   :target: https://codecov.io/github/Erotemic/cmd_queue?branch=main
