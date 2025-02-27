"""
References:
    https://jmmv.dev/2018/03/shell-readability-strict-mode.html
    https://stackoverflow.com/questions/13195655/bash-set-x-without-it-being-printed
"""
import ubelt as ub
import uuid
from cmd_queue import base_queue
from cmd_queue.util import util_tags
from cmd_queue.util import util_bash


class BashJob(base_queue.Job):
    r"""
    A job meant to run inside of a larger bash file. Analog of SlurmJob

    Attributes:
        name (str): a name for this job

        pathid (str): a unique id based on the name and a hashed uuid

        command (str): the shell command to run

        depends (List[BashJob] | None):
            the jobs that this job depends on. This job will only run once all
            the dependencies have succesfully run.

        bookkeeper (bool): flag indicating if this is a bookkeeping job or not

        info_dpath (PathLike | None): where information about this job will be stored

        log (bool):
            if True, output of the job will be tee-d and saved to a file, this
            can have interactions with normal stdout. Defaults to False.

        tags (List[str] | str | None):
            a list of strings that can be used to group jobs or filter the
            queue or other custom purposes.

        allow_indent (bool):
            In some cases indentation matters for the shell command.
            In that case ensure this is False at the cost of readability in the
            result script.

    TODO:
        - [ ] What is a good name for a a list of jobs that must fail
              for this job to run. Our current depends in analogous to slurm's
              afterok. What is a good variable name for afternotok? Do we
              wrap the job with some sort of negation, so we depend on the
              negation of the job?

        - [ ] Need support for specifying cwd (current working directory) when
              submitting a job.

    CommandLine:
        xdoctest -m cmd_queue.serial_queue BashJob

    Example:
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> # Demo full boilerplate for a job with no dependencies
        >>> self = BashJob('echo hi', 'myjob')
        >>> self.print_commands(1, 1)

    Example:
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> # Demo full boilerplate for a job with dependencies
        >>> dep = BashJob('echo hi', name='job1')
        >>> conditionals = {'on_skip': ['echo "CUSTOM MESSAGE FOR WHEN WE SKIP A JOB"']}
        >>> self = BashJob('echo hi', name='job2', depends=[dep])
        >>> self.print_commands(1, 1, conditionals=conditionals)
    """
    def __init__(self, command, name=None, depends=None, gpus=None, cpus=None,
                 mem=None, bookkeeper=0, info_dpath=None, log=False, tags=None,
                 allow_indent=True, **kwargs):

        if depends is not None and not ub.iterable(depends):
            depends = [depends]
        self.name = name
        self.pathid = self.name + '_' + ub.hash_data(uuid.uuid4())[0:8]
        self.kwargs = kwargs  # unused kwargs
        self.command = command
        self.depends: list[base_queue.Job] = depends
        self.bookkeeper = bookkeeper
        self.log = log
        if info_dpath is None:
            info_dpath = ub.Path.appdir('cmd_queue/jobinfos/') / self.pathid
        self.info_dpath = info_dpath
        self.pass_fpath = self.info_dpath / f'passed/{self.pathid}.pass'
        self.fail_fpath = self.info_dpath / f'failed/{self.pathid}.fail'
        self.stat_fpath = self.info_dpath / f'status/{self.pathid}.stat'
        self.log_fpath = self.info_dpath / f'status/{self.pathid}.logs'
        self.tags = util_tags.Tags.coerce(tags)
        self.allow_indent = allow_indent

    def _test_bash_syntax_errors(self):
        """
        Check for bash syntax errors

        Example:
            >>> from cmd_queue.serial_queue import *  # NOQA
            >>> # Demo full boilerplate for a job with dependencies
            >>> self = BashJob('basd syhi(', name='job1')
            >>> import pytest
            >>> with pytest.raises(SyntaxError):
            >>>     self._test_bash_syntax_errors()
        """
        bash_text = self.finalize_text()
        _check_bash_text_for_syntax_errors(bash_text)

    def finalize_text(self, with_status=True, with_gaurds=True,
                      conditionals=None, **kwargs):
        script = []
        prefix_script = []
        suffix_script = []

        if with_status:
            # Base conditionals
            _job_conditionals = {
                # when the job runs and succeedes
                'on_pass': [
                    f'mkdir -p {self.pass_fpath.parent}',
                    f'printf "pass" > {self.pass_fpath}',
                ],
                # when the job fails or does not run
                'on_fail': [
                    f'mkdir -p {self.fail_fpath.parent}',
                    f'printf "fail" > {self.fail_fpath}',
                ],
                # when dependencies are unmet
                'on_skip': [ ]
            }

            # Append custom conditionals
            if conditionals:
                for k, v in _job_conditionals.items():
                    if k in conditionals:
                        v2 = conditionals.get(k)
                        if not ub.iterable(v2):
                            v2 = [v2]
                        v.extend(v2)

        if with_status:
            prefix_script.append('# Ensure job status directory')
            prefix_script.append(f'mkdir -p {self.stat_fpath.parent}')

        had_conditions = False
        if with_status:
            if self.depends:
                # Dont allow us to run if any dependencies have failed
                conditions = []
                for dep in self.depends:
                    if dep is not None:
                        conditions.append(f'[ -f {dep.pass_fpath} ]')
                # TODO: if we add the ability to depend on jobs failing then
                # add those conditions here.
                if conditions:
                    had_conditions = True
                    condition = ' && '.join(conditions)
                    prefix_script.append(f'if {condition}; then')

        if with_status:
            script.append('# before_command:')
            # import shlex
            json_fmt_parts = [
                ('ret', '%s', 'null'),
                ('name', '"%s"', self.name),
                # ('command', '"%s"', shlex.quote(self.command)),
            ]
            if self.log:
                json_fmt_parts += [
                    ('logs', '"%s"', self.log_fpath),
                ]
            dump_pre_status = util_bash.bash_json_dump(json_fmt_parts,
                                                       self.stat_fpath)
            script.append('# Mark job as running')
            script.append(dump_pre_status)

        if with_gaurds and not self.bookkeeper:
            # -x Tells bash to print the command before it executes it
            # +e tells bash to allow the command to fail
            if self.log:
                # https://stackoverflow.com/questions/6871859/piping-command-output-to-tee-but-also-save-exit-code-of-command
                script.append('set -o pipefail')
            script.append('# Disable exit-on-error, enable command echo')
            script.append('set +e -x')

        if with_status:
            # script.append('#     </before_command> ')
            # script.append('#     <command> ')
            script.append('# ********')
            script.append('# command:')
        if self.log and with_status:
            logged_command = f'({self.command}) 2>&1 | tee {self.log_fpath}'
            script.append(logged_command)
        else:
            script.append(self.command)

        if with_status:
            script.append('# ********')

        if with_status:
            # script.append('#     </command> ')
            # script.append('#     <after_command> ')
            script.append('# after_command:')
        if with_gaurds:
            # Tells bash to stop printing commands, but is clever in that it
            # captures the last return code and doesnt print this command.
            # Also set -e so our boilerplate is not allowed to fail
            script.append('# Capture job return code, disable command echo, enable exit-on-error')
            script.append('{ RETURN_CODE=$? ; set +x -e; } 2>/dev/null')
            if self.log:
                script.append('set +o pipefail')
        else:
            if with_status:
                script.append('# Capture job return code')
                script.append('RETURN_CODE=$?')

        if had_conditions:
            suffix_script.append('else')
            if _job_conditionals['on_skip']:
                on_skip_part = indent(_job_conditionals['on_skip'])
                suffix_script.append(on_skip_part)
            suffix_script.append('    RETURN_CODE=126')
            suffix_script.append('fi')
            if self.allow_indent:
                script = prefix_script + [indent(script)] + suffix_script
            else:
                script = prefix_script + script + suffix_script
        else:
            script = prefix_script + script + suffix_script

        if with_status:
            # import shlex
            json_fmt_parts = [
                ('ret', '%s', '$RETURN_CODE'),
                ('name', '"%s"', self.name),
                # ('command', '"%s"', shlex.quote(self.command)),
            ]
            if self.log:
                json_fmt_parts += [
                    ('logs', '"%s"', self.log_fpath),
                ]
            dump_post_status = util_bash.bash_json_dump(json_fmt_parts,
                                                        self.stat_fpath)

            on_pass_part = indent(_job_conditionals['on_pass'])
            on_fail_part = indent(_job_conditionals['on_fail'])
            conditional_body = '\n'.join([
                'if [[ "$RETURN_CODE" == "0" ]]; then',
                on_pass_part,
                'else',
                on_fail_part,
                'fi'
            ])
            script.append('# Mark job as stopped')
            script.append(dump_post_status)
            script.append(conditional_body)
            # script.append('#     </after_command> ')

        assert isinstance(script, list)
        text = '\n'.join(script)
        return text

    def print_commands(self, with_status=False, with_gaurds=False,
                       with_rich=None, style='colors', **kwargs):
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
            xdoctest -m cmd_queue.serial_queue BashJob.print_commands

        Example:
            >>> from cmd_queue.serial_queue import *  # NOQA
            >>> self = SerialQueue('test-print-commands-serial-queue')
            >>> self.submit('echo hi 1')
            >>> self.submit('echo hi 2')
            >>> print('\n\n---\n\n')
            >>> self.print_commands(with_status=1, with_gaurds=1, style='rich')
            >>> print('\n\n---\n\n')
            >>> self.print_commands(with_status=0, with_gaurds=1, style='rich')
            >>> print('\n\n---\n\n')
            >>> self.print_commands(with_status=0, with_gaurds=0, style='rich')
        """
        style = base_queue.Queue._coerce_style(self, style, with_rich)

        code = self.finalize_text(with_status=with_status,
                                  with_gaurds=with_gaurds, **kwargs)
        if style == 'rich':
            from rich.syntax import Syntax
            from rich.console import Console
            console = Console()
            console.print(Syntax(code, 'bash'))
        elif style == 'colors':
            print(ub.highlight_code(code, 'bash'))
        elif style == 'plain':
            print(code)
        else:
            raise KeyError(f'Unknown style={style}')


class SerialQueue(base_queue.Queue):
    r"""
    A linear job queue written to a single bash file

    Example:
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> self = SerialQueue('test-serial-queue', rootid='test-serial')
        >>> job1 = self.submit('echo "this job fails" && false')
        >>> job2 = self.submit('echo "this job works" && true')
        >>> job3 = self.submit('echo "this job wont run" && true', depends=job1)
        >>> self.print_commands(1, 1)
        >>> self.run()
        >>> state = self.read_state()
        >>> print('state = {}'.format(ub.repr2(state, nl=1)))

    Example:
        >>> # Test case where a job fails
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> self = SerialQueue('test-serial-queue', rootid='test-serial')
        >>> job1 = self.submit('echo "job1 fails" && false')
        >>> job2 = self.submit('echo "job2 never runs"', depends=[job1])
        >>> job3 = self.submit('echo "job3 never runs"', depends=[job2])
        >>> job4 = self.submit('echo "job4 passes" && true')
        >>> job5 = self.submit('echo "job5 fails" && false', depends=[job4])
        >>> job6 = self.submit('echo "job6 never runs"', depends=[job5])
        >>> job7 = self.submit('echo "job7 never runs"', depends=[job4, job2])
        >>> job8 = self.submit('echo "job8 never runs"', depends=[job4, job1])
        >>> self.print_commands(1, 1)
        >>> self.run()
        >>> self.read_state()
    """

    def __init__(self, name='', dpath=None, rootid=None, environ=None, cwd=None, **kwargs):
        super().__init__()
        if rootid is None:
            rootid = str(ub.timestamp().split('T')[0]) + '_' + ub.hash_data(uuid.uuid4())[0:8]
        self.name = name
        self.rootid = rootid
        if dpath is None:
            dpath = ub.Path.appdir('cmd_queue/serial', self.pathid).ensuredir()
        self.dpath = ub.Path(dpath)

        self.unused_kwargs = kwargs

        self.fpath = self.dpath / (self.pathid + '.sh')
        self.state_fpath = self.dpath / 'serial_queue_{}.txt'.format(self.pathid)
        self.environ = environ
        self.header = '#!/bin/bash'
        self.header_commands = []
        self.jobs = []

        self.cwd = cwd
        self.job_info_dpath = self.dpath / 'job_info'

    @property
    def pathid(self):
        """ A path-safe identifier for file names """
        return '{}_{}'.format(self.name, self.rootid)

    def __nice__(self):
        return f'{self.pathid} - {self.num_real_jobs}'

    @classmethod
    def is_available(cls):
        """
        This queue is always available.
        """
        # TODO: get this working
        return True

    def order_jobs(self):
        """
        Ensure jobs within a serial queue are topologically ordered.
        Attempts to preserve input ordering.
        """
        # We need to ensure the jobs are in a topologoical order here.
        import networkx as nx
        graph = self._dependency_graph()
        original_order = [j.name for j in self.jobs]
        from cmd_queue.util import util_networkx
        if not util_networkx.is_topological_order(graph, original_order):
            # If not already topologically sorted, try to make the minimal
            # reordering to achieve it.
            # FIXME: I think this is not a minimal reordering.
            topo_generations = list(nx.topological_generations(graph))
            new_order = []
            original_order = ub.oset(original_order)
            for gen in topo_generations:
                new_order.extend(original_order & gen)
            self.jobs = [self.named_jobs[n] for n in new_order]

    def finalize_text(self, with_status=True, with_gaurds=True,
                      with_locks=True, exclude_tags=None):
        """
        Create the bash script that will:

            1. Run all of the jobs in this queue.
            2. Track the results.
            3. Prevent jobs with unmet dependencies from running.

        """
        import cmd_queue
        self.order_jobs()
        script = [self.header]
        script += ['# Written by cmd_queue {}'.format(cmd_queue.__version__)]

        total = self.num_real_jobs

        if with_gaurds:
            script.append('set -e')

        if with_status:
            script.append(ub.codeblock(
                f'''
                # Init state to keep track of job progress
                (( "_CMD_QUEUE_NUM_FAILED=0" )) || true
                (( "_CMD_QUEUE_NUM_PASSED=0" )) || true
                (( "_CMD_QUEUE_NUM_SKIPPED=0" )) || true
                _CMD_QUEUE_TOTAL={total}
                _CMD_QUEUE_STATUS=""
                '''))

        old_status = None

        def _mark_status(status):
            nonlocal old_status
            # be careful with json formatting here
            if with_status:
                if old_status != status:
                    script.append(ub.codeblock(
                        '''
                        _CMD_QUEUE_STATUS="{}"
                        ''').format(status))

                old_status = status

                # Name, format-string, and value for json status
                json_fmt_parts = [
                    ('status', '"%s"', '$_CMD_QUEUE_STATUS'),
                    ('passed', '%d', '$_CMD_QUEUE_NUM_PASSED'),
                    ('failed', '%d', '$_CMD_QUEUE_NUM_FAILED'),
                    ('skipped', '%d', '$_CMD_QUEUE_NUM_SKIPPED'),
                    ('total', '%d', '$_CMD_QUEUE_TOTAL'),
                    ('name', '"%s"', self.name),
                    ('rootid', '"%s"', self.rootid),
                ]
                dump_code = util_bash.bash_json_dump(json_fmt_parts,
                                                     self.state_fpath)
                script.append('# Update queue status')
                script.append(dump_code)
                # script.append('cat ' + str(self.state_fpath))

        def _command_enter():
            if with_gaurds:
                # Tells bash to print the command before it executes it
                script.append('set -x')

        def _command_exit():
            if with_gaurds:
                script.append('{ set +x; } 2>/dev/null')
            else:
                if with_status:
                    script.append('RETURN_CODE=$?')

        _mark_status('init')
        if self.environ:
            script.append('#')
            script.append('# Environment')
            _mark_status('set_environ')
            if with_gaurds:
                _command_enter()
            script.extend([
                f'export {k}="{v}"' for k, v in self.environ.items()])
            if with_gaurds:
                _command_exit()

        if self.cwd:
            script.append('#')
            script.append('# Working Directory')
            script.append(f'cd {self.cwd}')

        if self.header_commands:
            script.append('#')
            script.append('# Header commands')
            for command in self.header_commands:
                _command_enter()
                script.append(command)
                _command_exit()

        if self.jobs:
            script.append('')
            script.append('# ----')
            script.append('# Jobs')
            script.append('# ----')
            script.append('')

            exclude_tags = util_tags.Tags.coerce(exclude_tags)

            num = 0
            for job in self.jobs:
                if exclude_tags and exclude_tags.intersection(job.tags):
                    continue

                if job.bookkeeper:
                    if with_locks:
                        script.append(job.finalize_text(with_status, with_gaurds))
                else:
                    if with_status:
                        script.append('')
                        script.append('#')
                        script.append('# <job>')

                    _mark_status('run')

                    script.append(ub.codeblock(
                        '''
                        #
                        ### Command {} / {} - {}
                        ''').format(num + 1, total, job.name))

                    conditionals = {
                        'on_pass': '(( "_CMD_QUEUE_NUM_PASSED=_CMD_QUEUE_NUM_PASSED+1" )) || true',
                        'on_fail': '(( "_CMD_QUEUE_NUM_FAILED=_CMD_QUEUE_NUM_FAILED+1" )) || true',
                        'on_skip': '(( "_CMD_QUEUE_NUM_SKIPPED=_CMD_QUEUE_NUM_SKIPPED+1" )) || true',
                    }
                    script.append(job.finalize_text(with_status, with_gaurds, conditionals))
                    if with_status:
                        script.append('# </job>')
                        script.append('#')
                        script.append('')
                    num += 1

        _mark_status('done')

        # Print summary of status at the end.
        if with_status:
            script.append('# Display final status of this serial queue')
            script.append('echo "Command Queue Final Status:"')
            script.append(f'cat "{self.state_fpath}"')
            pass

        if with_gaurds:
            script.append('set +e')

        text = '\n'.join(script)
        return text

    def add_header_command(self, command):
        self.header_commands.append(command)

    def print_commands(self, *args, **kwargs):
        r"""
        Print info about the commands, optionally with rich

        Args:
            *args: see :func:`cmd_queue.base_queue.Queue.print_commands`.
            **kwargs: see :func:`cmd_queue.base_queue.Queue.print_commands`.

        CommandLine:
            xdoctest -m cmd_queue.serial_queue SerialQueue.print_commands

        Example:
            >>> from cmd_queue.serial_queue import *  # NOQA
            >>> self = SerialQueue('test-serial-queue')
            >>> self.submit('echo hi 1')
            >>> self.submit('echo hi 2')
            >>> self.submit('echo boilerplate', tags='boilerplate')
            >>> self.print_commands(with_status=True)
            >>> print('\n\n---\n\n')
            >>> self.print_commands(with_status=0, exclude_tags='boilerplate')
        """
        return super().print_commands(*args, **kwargs)
        # (self, with_status=False, with_gaurds=False,
        #                with_rich=None, colors=1, with_locks=True,
        #                exclude_tags=None, style='auto'):
        # style = self._coerce_style(style, with_rich, colors)

        # exclude_tags = util_tags.Tags.coerce(exclude_tags)
        # code = self.finalize_text(with_status=with_status,
        #                           with_gaurds=with_gaurds,
        #                           with_locks=with_locks,
        #                           exclude_tags=exclude_tags)

        # if style == 'rich':
        #     from rich.panel import Panel
        #     from rich.syntax import Syntax
        #     from rich.console import Console
        #     console = Console()
        #     console.print(Panel(Syntax(code, 'bash'), title=str(self.fpath)))
        #     # console.print(Syntax(code, 'bash'))
        # elif style == 'colors':
        #     header = f'# --- {str(self.fpath)}'
        #     print(ub.highlight_code(header, 'bash'))
        #     print(ub.highlight_code(code, 'bash'))
        # elif style == 'plain':
        #     header = f'# --- {str(self.fpath)}'
        #     print(header)
        #     print(code)
        # else:
        #     raise KeyError(f'Unknown style={style}')

    rprint = print_commands

    def run(self, block=True, system=False, shell=1, capture=True, mode='bash', verbose=3, **kw):
        self.write()
        # TODO: can implement a monitor here for non-blocking mode
        detach = not block
        if mode == 'bash':
            ub.cmd(f'bash {self.fpath}', verbose=verbose, check=True,
                   capture=capture, shell=shell, system=system, detach=detach)
        elif mode == 'source':
            ub.cmd(f'source {self.fpath}', verbose=verbose, check=True,
                   capture=capture, shell=shell, system=system, detach=detach)
        else:
            ub.cmd(f'{mode} {self.fpath}', verbose=verbose, check=True,
                   capture=capture, shell=shell, system=system, detach=detach)
            # raise KeyError

    def job_details(self):
        import json
        for job in self.jobs:
            print('+--------')
            print(f'job={job}')
            job_status = json.loads(job.stat_fpath.read_text())
            print('job_status = {}'.format(ub.repr2(job_status, nl=1)))
            if job.log_fpath.exists():
                print(job.log_fpath.read_text())
            print('L________')

    def read_state(self):
        import json
        import time
        max_attempts = 100
        num_attempts = 0
        while True:
            try:
                state = json.loads(self.state_fpath.read_text())
            except FileNotFoundError:
                state = {
                    'name': self.name,
                    'status': 'unknown',
                    'total': self.num_real_jobs,
                    'passed': None,
                    'failed': None,
                    'skipped': None,
                }
            except json.JSONDecodeError:
                # we might have tried to read the file while it was being
                # written try again.
                num_attempts += 1
                if num_attempts > max_attempts:
                    raise
                time.sleep(0.01)
                continue
            break
        return state


def indent(text, prefix='    '):
    r"""
    Indents a block of text

    Args:
        text (str): text to indent
        prefix (str, default = '    '): prefix to add to each line

    Returns:
        str: indented text

        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> text = ['aaaa', 'bb', 'cc\n   dddd\n    ef\n']
        >>> text = indent(text)
        >>> print(text)
        >>> text = indent(text)
        >>> print(text)
    """
    if isinstance(text, (list, tuple)):
        return indent('\n'.join(text), prefix)
    else:
        return prefix + text.replace('\n', '\n' + prefix)


def _check_bash_text_for_syntax_errors(bash_text):
    import tempfile
    tmpdir = tempfile.TemporaryDirectory()
    with tmpdir:
        dpath = ub.Path(tmpdir.name)
        fpath = dpath / 'job_text.sh'
        fpath.write_text(bash_text)
        info = ub.cmd(['bash', '-nv', fpath])
        if info.returncode != 0:
            print(info.stderr)
            raise SyntaxError('bash syntax error')
