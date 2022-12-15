"""
References:
    https://jmmv.dev/2018/03/shell-readability-strict-mode.html
    https://stackoverflow.com/questions/13195655/bash-set-x-without-it-being-printed
"""
import ubelt as ub
import uuid
from cmd_queue import base_queue
from cmd_queue.util import util_tags


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


class BashJob(base_queue.Job):
    r"""
    A job meant to run inside of a larger bash file. Analog of SlurmJob

    Attributes:
        name (str): a name for this job
        pathid (str): a unique id based on the name and a hashed uuid
        command (str): the shell command to run
        depends (List[BashJob] | None): the jobs that this job depends on
        bookkeeper (bool): flag indicating if this is a bookkeeping job or not
        info_dpath (PathLike | None): where information about this job will be stored
        log (bool): if True, output of the job will be teed and saved to a file
        tags (List[str] | str | None):
            a list of strings that can be used to group jobs or filter the
            queue or other custom purposes.

    Example:
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> # Demo full boilerplate for a job with no dependencies
        >>> self = BashJob('echo hi', 'myjob')
        >>> self.rprint(1, 1)

    Example:
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> # Demo full boilerplate for a job with dependencies
        >>> dep = BashJob('echo hi', name='job1')
        >>> conditionals = {'on_skip': ['echo "CUSTOM MESSAGE FOR WHEN WE SKIP A JOB"']}
        >>> self = BashJob('echo hi', name='job2', depends=[dep])
        >>> self.rprint(1, 1, conditionals=conditionals)
    """
    def __init__(self, command, name=None, depends=None, gpus=None, cpus=None,
                 mem=None, bookkeeper=0, info_dpath=None, log=True, tags=None,
                 **kwargs):
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

    def finalize_text(self, with_status=True, with_gaurds=True,
                      conditionals=None):
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
            dump_pre_status = _bash_json_dump(json_fmt_parts, self.stat_fpath)
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
            script = prefix_script + [indent(script)] + suffix_script
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
            dump_post_status = _bash_json_dump(json_fmt_parts, self.stat_fpath)

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

    def rprint(self, with_status=False, with_gaurds=False, with_rich=0,
               colors=1, **kwargs):
        r"""
        Print info about the commands, optionally with rich

        Example:
            >>> from cmd_queue.serial_queue import *  # NOQA
            >>> self = SerialQueue('test-rprint-serial-queue')
            >>> self.submit('echo hi 1')
            >>> self.submit('echo hi 2')
            >>> print('\n\n---\n\n')
            >>> self.rprint(with_status=1, with_gaurds=1, with_rich=1)
            >>> print('\n\n---\n\n')
            >>> self.rprint(with_status=0, with_gaurds=1, with_rich=1)
            >>> print('\n\n---\n\n')
            >>> self.rprint(with_status=0, with_gaurds=0, with_rich=1)
        """
        code = self.finalize_text(with_status=with_status,
                                  with_gaurds=with_gaurds, **kwargs)
        if with_rich:
            from rich.syntax import Syntax
            from rich.console import Console
            console = Console()
            console.print(Syntax(code, 'bash'))
        else:
            if colors:
                print(ub.highlight_code(code, 'bash'))
            else:
                print(code)


class SerialQueue(base_queue.Queue):
    r"""
    A linear job queue written to a single bash file

    Example:
        >>> from cmd_queue.serial_queue import *  # NOQA
        >>> self = SerialQueue('test-serial-queue', rootid='test-serial')
        >>> job1 = self.submit('echo "this job fails" && false')
        >>> job2 = self.submit('echo "this job works" && true')
        >>> job3 = self.submit('echo "this job wont run" && true', depends=job1)
        >>> self.rprint(1, 1)
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
        >>> self.rprint(1, 1)
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

    def finalize_text(self, with_status=True, with_gaurds=True,
                      with_locks=True, exclude_tags=None):
        """
        Create the bash script that will:

            1. Run all of the jobs in this queue.
            2. Track the results.
            3. Prevent jobs with unmet dependencies from running.

        """
        import cmd_queue
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
                dump_code = _bash_json_dump(json_fmt_parts, self.state_fpath)
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

    def rprint(self, with_status=False, with_gaurds=False, with_rich=0,
               colors=1, with_locks=True, exclude_tags=None):
        r"""
        Print info about the commands, optionally with rich

        Example:
            >>> from cmd_queue.serial_queue import *  # NOQA
            >>> self = SerialQueue('test-serial-queue')
            >>> self.submit('echo hi 1')
            >>> self.submit('echo hi 2')
            >>> self.submit('echo boilerplate', tags='boilerplate')
            >>> self.rprint(with_status=True)
            >>> print('\n\n---\n\n')
            >>> self.rprint(with_status=0, exclude_tags='boilerplate')
        """
        exclude_tags = util_tags.Tags.coerce(exclude_tags)
        code = self.finalize_text(with_status=with_status,
                                  with_gaurds=with_gaurds,
                                  with_locks=with_locks,
                                  exclude_tags=exclude_tags)
        if with_rich:
            from rich.panel import Panel
            from rich.syntax import Syntax
            from rich.console import Console
            console = Console()
            console.print(Panel(Syntax(code, 'bash'), title=str(self.fpath)))
            # console.print(Syntax(code, 'bash'))
        else:
            header = f'# --- {str(self.fpath)}'
            if colors:
                print(ub.highlight_code(header, 'bash'))
                print(ub.highlight_code(code, 'bash'))
            else:
                print(header)
                print(code)

    def run(self, block=True, system=False, shell=1, **kw):
        self.write()
        # TODO: can implement a monitor here for non-blocking mode
        detach = not block
        ub.cmd(f'bash {self.fpath}', verbose=3, check=True, shell=shell,
               system=system, detach=detach)

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


def _bash_json_dump(json_fmt_parts, fpath):
    """
    Make a printf command that dumps a json file indicating some status in a
    bash environment.

    Args:
        List[Tuple[str, str, str]]: A list of 3-tupels indicating the name of
            the json key, the printf code, and the bash expression to fill the
            printf code.

        fpath (str): where bash should write the json file

    Returns:
        str : the bash that will perform the printf

    Example:
        >>> from cmd_queue.serial_queue import _bash_json_dump
        >>> json_fmt_parts = [
        >>>     ('home', '%s', '$HOME'),
        >>>     ('const', '%s', 'MY_CONSTANT'),
        >>>     ('ps2', '"%s"', '$PS2'),
        >>> ]
        >>> fpath = 'out.json'
        >>> dump_code = _bash_json_dump(json_fmt_parts, fpath)
        >>> print(dump_code)
    """
    printf_body_parts = [
        '"{}": {}'.format(k, f) for k, f, v in json_fmt_parts
    ]
    printf_arg_parts = [
        '"{}"'.format(v) for k, f, v in json_fmt_parts
    ]
    printf_body = r"'{" + ", ".join(printf_body_parts) + r"}\n'"
    printf_args = ' '.join(printf_arg_parts)
    redirect_part = '> ' + str(fpath)
    printf_part = 'printf ' +  printf_body + ' \\\n    ' + printf_args
    dump_code = printf_part + ' \\\n    ' + redirect_part
    return dump_code
