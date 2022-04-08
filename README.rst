Command Queue - cmd_queue
=========================

.. .. |CircleCI| |Travis| |GitlabCIPipeline| |GitlabCICoverage| |Appveyor| |Codecov| |Pypi| |Downloads| |ReadTheDocs|


.. The ``cmd_queue`` module.

.. +------------------+----------------------------------------------+
.. | Read the docs    | https://cmd_queue.readthedocs.io             |
.. +------------------+----------------------------------------------+
.. | Github           | https://github.com/Erotemic/cmd_queue        |
.. +------------------+----------------------------------------------+
.. | Pypi             | https://pypi.org/project/cmd_queue           |
.. +------------------+----------------------------------------------+


This is a simple module for "generating" a bash script that schedules multiples
jobs (in parallel if possible) on a single machine. There are 3 backends with
increasing levels of complexity: serial, tmux, and slurm.

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



Modivation
==========
Recently, I needed to run several jobs on 4 jobs across 2 GPUs and then execute a script after all of them were done. What I should have done was use slurm or some other proper queuing system to schedule the jobs, but instead I wrote my own hacky scheduler using tmux. I opened N (number of parallel workers) tmux sessions and then I ran independent jobs in each different sessions.

This worked unreasonably well for my use cases, and it was nice to be able to effectively schedule jobs without heavyweight software like slurm on my machine.

Eventually I did get slurm on my machine, and I abstracted the API of my tmux_queue to be a general "command queue" that can use 1 of 3 backends: serial, tmux, or slurm.


Examples
========


All of the dependency checking and book keeping logic is handled in bash
itself. Write (or better yet template) your bash scripts in Python, and then
use cmd_queue to "transpile" these sequences of commands to pure bash.


.. code:: python

   import cmd_queue
   self = cmd_queue.Queue.create(name='demo_queue', backend='serial')
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
   self.rprint()

   # Display the real bash that gets executed under the hood
   # that is independencly executable, tracks the success / failure of each job, 
   # and manages dependencies.
   self.rprint(1, 1)

   # Blocking will display a job monitor while it waits for everything to
   # complete
   self.run(block=True)


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
   self.rprint()

   # Display the real bash that gets executed under the hood
   # that is independencly executable, tracks the success / failure of each job, 
   # and manages dependencies.
   self.rprint(1, 1)

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
   self.rprint()

   # Display the real bash that gets executed under the hood
   # that is independencly executable, tracks the success / failure of each job, 
   # and manages dependencies.
   self.rprint(1, 1)

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



Installation
============
This will be on pypi once it is cleaned up, but for now:

python -m pip install git+https://gitlab.kitware.com/computer-vision/cmd_queue.git@main


   


.. |Pypi| image:: https://img.shields.io/pypi/v/cmd_queue.svg
   :target: https://pypi.python.org/pypi/cmd_queue

.. |Downloads| image:: https://img.shields.io/pypi/dm/cmd_queue.svg
   :target: https://pypistats.org/packages/cmd_queue

.. |ReadTheDocs| image:: https://readthedocs.org/projects/cmd_queue/badge/?version=release
    :target: https://cmd_queue.readthedocs.io/en/release/

.. # See: https://ci.appveyor.com/project/jon.crall/cmd_queue/settings/badges
.. |Appveyor| image:: https://ci.appveyor.com/api/projects/status/py3s2d6tyfjc8lm3/branch/master?svg=true
   :target: https://ci.appveyor.com/project/jon.crall/cmd_queue/branch/master

.. |GitlabCIPipeline| image:: https://gitlab.kitware.com/utils/cmd_queue/badges/master/pipeline.svg
   :target: https://gitlab.kitware.com/utils/cmd_queue/-/jobs

.. |GitlabCICoverage| image:: https://gitlab.kitware.com/utils/cmd_queue/badges/master/coverage.svg?job=coverage
    :target: https://gitlab.kitware.com/utils/cmd_queue/commits/master

.. |CircleCI| image:: https://circleci.com/gh/Erotemic/cmd_queue.svg?style=svg
    :target: https://circleci.com/gh/Erotemic/cmd_queue

.. |Travis| image:: https://img.shields.io/travis/Erotemic/cmd_queue/master.svg?label=Travis%20CI
   :target: https://travis-ci.org/Erotemic/cmd_queue

.. |Codecov| image:: https://codecov.io/github/Erotemic/cmd_queue/badge.svg?branch=master&service=github
   :target: https://codecov.io/github/Erotemic/cmd_queue?branch=master
