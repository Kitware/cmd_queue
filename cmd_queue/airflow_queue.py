"""
UNFINISHED - NOT FUNCTIONAL

Airflow backend

Requires:
    pip install apache-airflow
    pip install apache-airflow[cncf.kubernetes]
"""
import ubelt as ub
from cmd_queue import base_queue  # NOQA


class AirflowJob(base_queue.Job):
    """
    Represents a airflow job that hasn't been executed yet
    """
    def __init__(self, command, dag, name=None, output_fpath=None, depends=None,
                 partition=None, cpus=None, gpus=None, mem=None, begin=None,
                 shell=None, **kwargs):
        super().__init__()
        from airflow.operators.bash import BashOperator
        if name is None:
            import uuid
            name = 'job-' + str(uuid.uuid4())
        if depends is not None and not ub.iterable(depends):
            depends = [depends]
        self.unused_kwargs = kwargs
        self.command = command
        self.name = name
        self.output_fpath = output_fpath
        self.depends = depends
        self.cpus = cpus
        self.gpus = gpus
        self.mem = mem
        self.begin = begin
        self.shell = shell
        # if shell not in {None, 'bash'}:
        #     raise NotImplementedError(shell)

        # TODO:
        # Unfortunately, we need to write out a python file that actually
        # contains this code.

        self.operator = BashOperator(
            task_id=self.name,
            bash_command=command,
            dag=dag,
        )
        # cwd
        # env
        if depends:
            for dep in depends:
                if dep is not None:
                    self.operator.set_upstream(dep.operator)
        # self.jobid = None  # only set once this is run (maybe)
        # --partition=community --cpus-per-task=5 --mem=30602 --gres=gpu:1

    def __nice__(self):
        return repr(self.command)


class AirflowQueue(base_queue.Queue):
    """
    Example:
        >>> # xdoctest: +REQUIRES(module:airflow)
        >>> # xdoctest: +SKIP
        >>> from cmd_queue.airflow_queue import *  # NOQA
        >>> self = AirflowQueue()
        >>> job1 = self.submit('echo hi 1 && true')
        >>> job2 = self.submit('echo hi 2 && true')
        >>> job3 = self.submit('echo hi 3 && true', depends=job1)
        >>> #self.rprint(1, 1)
        >>> self.run()
        >>> # self.read_state()
    """

    def __init__(self, name=None, shell=None, **kwargs):
        super().__init__()
        import uuid
        import time
        self.jobs = []
        if name is None:
            name = 'SQ'
        stamp = time.strftime('%Y%m%dT%H%M%S')
        self.unused_kwargs = kwargs
        self.queue_id = name + '-' + stamp + '-' + ub.hash_data(uuid.uuid4())[0:8]
        self.dpath = ub.Path.appdir('cmd_queue') / self.queue_id
        self.log_dpath = self.dpath / 'logs'
        self.fpath = self.dpath / (self.queue_id + '.sh')
        self.shell = shell
        self.header_commands = []
        self.all_depends = None

        from airflow import DAG
        from datetime import timedelta
        self.dag = DAG(
            # dag_id=self.queue_id,
            dag_id=ub.hash_data(self.queue_id)[0:8],
            # These args will get passed on to each operator
            # You can override them on a per-task basis during operator initialization
            default_args={
                # 'depends_on_past': False,
                # 'retries': 1,
                'retries': 0,
                # 'retry_delay': timedelta(minutes=5),
            },
            # description='A simple tutorial DAG',
            max_active_runs=1,
            schedule_interval=timedelta(days=1),
            start_date=ub.timeparse(ub.timestamp()),
            catchup=False,
            # tags=['example'],
            tags=[self.queue_id],
        )

    def submit(self, command, **kwargs):
        name = kwargs.get('name', None)
        if name is None:
            name = kwargs['name'] = f'J{len(self.jobs):04d}-{self.queue_id}'
            # + '-job-{}'.format(len(self.jobs))
        if 'output_fpath' not in kwargs:
            kwargs['output_fpath'] = self.log_dpath / (name + '.sh')
        if self.shell is not None:
            kwargs['shell'] = kwargs.get('shell', self.shell)
        if self.all_depends:
            depends = kwargs.get('depends', None)
            if depends is None:
                depends = self.all_depends
            else:
                if not ub.iterable(depends):
                    depends = [depends]
                depends = self.all_depends + depends
            kwargs['depends'] = depends

        dag = self.dag
        job = AirflowJob(command, dag, **kwargs)
        self.jobs.append(job)
        self.num_real_jobs += 1
        return job

    def rprint(self, with_status=False, with_gaurds=False, with_rich=0):
        r"""
        Print info about the commands, optionally with rich

        Example:
            >>> # xdoctest: +SKIP
            >>> from cmd_queue.airflow_queue import *  # NOQA
            >>> self = AirflowQueue()
            >>> self.submit('date')
            >>> #self.rprint()
            >>> self.run()
        """
        if with_rich:
            from rich.syntax import Syntax
            from rich.console import Console
            console = Console()
            for op in self.dag.topological_sort():
                msg = ('# op = {}'.format(ub.repr2(op, nl=1)))
                console.print(Syntax(msg, 'bash'))
                console.print(Syntax(op.bash_command, 'bash'))
        else:
            for op in self.dag.topological_sort():
                msg = ('# op = {}'.format(ub.repr2(op, nl=1)))
                print(msg)
                print(op.bash_command)

    def run(self):
        self.dag.run()


def demo():
    """
    Airflow requires initialization:
        airflow db init

    Ignore:
        from cmd_queue.airflow_queue import *  # NOQA
        demo()
    """
    from airflow import DAG
    from datetime import timezone
    from datetime import datetime as datetime_cls
    from airflow.operators.bash import BashOperator
    now = datetime_cls.utcnow().replace(tzinfo=timezone.utc)
    dag = DAG(
        'mycustomdag',
        start_date=now,
        catchup=False,
        tags=['example'],
    )
    t1 = BashOperator(task_id='task1', bash_command='date', dag=dag)
    t2 = BashOperator(task_id='task2', bash_command='echo hi 1 && true', dag=dag)
    t2.set_upstream(t1)
    dag.run(verbose=True, local=True)


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/cmd_queue/airflow_queue.py
    """
    demo()
