r"""
Helper script to wrap a command with sbatch, but using a more srun like syntax.

.. code:: bash

    python -m cmd_queue.slurmify \
        --jobname="my_job" \
        --depends=None \
        --gpus=1 \
        --mem=16GB \
        --cpus_per_task=5 \
        --ntasks=1 \
        --ntasks-per-node=1 \
        --partition=community \
        -- \
            python -c 'import sys; print("hello world"); sys.exit(0)'
"""
#!/usr/bin/env python3
import scriptconfig as scfg
import ubelt as ub


class SlurmifyCLI(scfg.DataConfig):
    __command__ = 'slurmify'

    jobname = scfg.Value(None, help='for submit, this is the name of the new job')
    depends = scfg.Value(None, help='comma separated jobnames to depend on')

    command = scfg.Value(None, type=str, position=1, nargs='*', help=ub.paragraph(
        '''
        Specifies the bash command to queue.
        Care must be taken when specifying this argument.  If specifying as a
        key/value pair argument, it is important to quote and escape the bash
        command properly.  A more convinient way to specify this command is as
        a positional argument. End all of the options to this CLI with `--` and
        then specify your full command.
        '''))

    gpus = scfg.Value(None, help='a comma separated list of the gpu numbers to spread across. tmux backend only.')
    workers = scfg.Value(1, help='number of concurrent queues for the tmux backend.')

    mem = scfg.Value(None, help='')
    partition = scfg.Value(1, help='slurm partition')

    ntasks = scfg.Value(None, help='')
    ntasks_per_node = scfg.Value(None, help='')
    cpus_per_task = scfg.Value(None, help='')

    @classmethod
    def main(cls, cmdline=1, **kwargs):
        """
        Example:
            >>> # xdoctest: +SKIP
            >>> from cmd_queue.slurmify import *  # NOQA
            >>> cmdline = 0
            >>> kwargs = dict()
            >>> cls = SlurmifyCLI
            >>> cls.main(cmdline=cmdline, **kwargs)
        """
        import rich
        from rich.markup import escape
        config = cls.cli(cmdline=cmdline, data=kwargs, strict=True)
        rich.print('config = ' + escape(ub.urepr(config, nl=1)))

        # import json
        # Run a new CLI queue
        row = {'type': 'command', 'command': config['command']}
        if config.jobname:
            row['name'] = config.jobname
        if config.depends:
            row['depends'] = config.depends

        import cmd_queue
        queue = cmd_queue.Queue.create(
            size=max(1, config['workers']),
            backend='slurm',
            name='slurmified',
            gpus=config['gpus'],
            mem=config['mem'],
            partition=config['partition'],
            ntasks=config['ntasks'],
            ntasks_per_node=config['ntasks_per_node'],
        )
        try:
            bash_command = row['command']
            if isinstance(bash_command, list):
                if len(bash_command) == 1:
                    # hack
                    import shlex
                    if shlex.quote(bash_command[0]) == bash_command[0]:
                        bash_command = bash_command[0]
                    else:
                        bash_command = shlex.quote(bash_command[0])
                else:
                    import shlex
                    bash_command = ' '.join([shlex.quote(str(p)) for p in bash_command])
            submitkw = ub.udict(row) & {'name', 'depends'}
            queue.submit(bash_command, log=False, **submitkw)
        except Exception:
            print('row = {}'.format(ub.urepr(row, nl=1)))
            raise
        queue.print_commands()

        # config.cli_queue_fpath.write_text(json.dumps(row))
        # 'sbatch --job-name="test_job1" --output="$HOME/.cache/slurm/logs/job-%j-%x.out" --wrap=""

__cli__ = SlurmifyCLI

if __name__ == '__main__':
    """

    CommandLine:
        python ~/code/cmd_queue/cmd_queue/slurmify.py
        python -m cmd_queue.slurmify
    """
    __cli__.main()
