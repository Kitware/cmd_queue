"""Airflow backend.

This backend materializes the queue as an Airflow DAG and can execute it
locally via ``dag.test``.  A minimal Airflow environment is constructed under
``AIRFLOW_HOME`` (which defaults to a subdirectory of the queue path) so users
do not need a running scheduler for simple single-machine runs.

Requirements:
    pip install "apache-airflow[core]==3.1.3" \
        --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.1.3/constraints-3.12.txt
"""
import contextlib
import os
import time
import uuid

import ubelt as ub
from cmd_queue import base_queue  # NOQA


class AirflowJob(base_queue.Job):
    """
    Represents a airflow job that hasn't been executed yet
    """
    def __init__(self, command, name=None, output_fpath=None, depends=None,
                 partition=None, cpus=None, gpus=None, mem=None, begin=None,
                 shell=None, **kwargs):
        super().__init__()
        if name is None:
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

    def __nice__(self):
        return repr(self.command)

    def finalize_text(self):
        dagvar = 'dag'
        return f'jobs[{self.name!r}] = BashOperator(task_id={self.name!r}, bash_command={self.command!r}, dag={dagvar})'


class AirflowQueue(base_queue.Queue):
    """
    Example:
        >>> # xdoctest: +REQUIRES(module:airflow)
        >>> # xdoctest: +SKIP
        >>> from cmd_queue.airflow_queue import *  # NOQA
        >>> self = AirflowQueue('zzz_mydemo')
        >>> job1 = self.submit('echo hi 1 && true')
        >>> job2 = self.submit('echo hi 2 && true')
        >>> job3 = self.submit('echo hi 3 && true', depends=job1)
        >>> self.print_commands()
        >>> self.write()
        >>> self.run()
        >>> #self.run()
        >>> # self.read_state()

    Ignore:
        airflow users create --role Admin --username admin --email admin --firstname admin --lastname admin --password admin

        https://airflow.apache.org/docs/apache-airflow/stable/tutorial.html
        https://airflow.apache.org/docs/apache-airflow/stable/start/local.html

        AIRFLOW__CORE__DAGS_FOLDER="." airflow standalone
        AIRFLOW__CORE__DAGS_FOLDER="." airflow scheduler
        AIRFLOW__CORE__DAGS_FOLDER="." airflow webserver

        AIRFLOW__CORE__DAGS_FOLDER="." airflow dags test zzz_cmd_queue_demo_dag $(date +"%Y-%m-%d")

        AIRFLOW__CORE__DAGS_FOLDER="." airflow dags list
        AIRFLOW__CORE__DAGS_FOLDER="." airflow tasks list zzz_cmd_queue_demo_dag
        AIRFLOW__CORE__DAGS_FOLDER="." airflow tasks clear zzz_cmd_queue_demo_dag
        AIRFLOW__CORE__DAGS_FOLDER="." airflow dags backfill zzz_cmd_queue_demo_dag --start-date $(date +"%Y-%m-%d")
        cd /home/joncrall/.cache/cmd_queue/SQ-20220711T180827-12f2905e
    """

    def __init__(self, name=None, shell=None, dpath=None, airflow_home=None,
                 **kwargs):
        super().__init__()
        self.jobs = []
        if name is None:
            name = 'SQ'
        self.name = name
        stamp = time.strftime('%Y%m%dT%H%M%S')
        self.unused_kwargs = kwargs
        self.queue_id = name + '-' + stamp + '-' + ub.hash_data(uuid.uuid4())[0:8]
        base_dpath = ub.Path(dpath) if dpath is not None else ub.Path.appdir('cmd_queue') / 'airflow'
        self.dpath = (base_dpath / self.queue_id).ensuredir()
        self.dags_dpath = (self.dpath / 'dags').ensuredir()
        self.log_dpath = (self.dpath / 'logs').ensuredir()
        self.fpath = self.dags_dpath / (self.name + '.py')
        self.shell = shell
        self.header_commands = []
        self.all_depends = None
        self.job_info_dpath = self.dpath / 'job_info'
        home = ub.Path(airflow_home) if airflow_home is not None else (self.dpath / 'airflow_home')
        self.airflow_home = home.ensuredir()

        # from airflow import DAG
        # from datetime import timedelta
        # self.dag = DAG(
        #     # dag_id=self.queue_id,
        #     dag_id=ub.hash_data(self.queue_id)[0:8],
        #     # These args will get passed on to each operator
        #     # You can override them on a per-task basis during operator initialization
        #     default_args={
        #         # 'depends_on_past': False,
        #         # 'retries': 1,
        #         'retries': 0,
        #         # 'retry_delay': timedelta(minutes=5),
        #     },
        #     # description='A simple tutorial DAG',
        #     max_active_runs=1,
        #     schedule_interval=timedelta(days=1),
        #     start_date=ub.timeparse(ub.timestamp()),
        #     catchup=False,
        #     # tags=['example'],
        #     tags=[self.queue_id],
        # )

    @classmethod
    def is_available(cls):
        """
        Determines if the airflow queue can run.
        """
        try:
            import airflow  # NOQA
        except Exception:
            return False
        else:
            return True

    def _airflow_env(self):
        env = os.environ.copy()
        env['AIRFLOW_HOME'] = os.fspath(self.airflow_home)
        env['AIRFLOW__CORE__DAGS_FOLDER'] = os.fspath(self.dags_dpath)
        env['AIRFLOW__CORE__LOAD_EXAMPLES'] = 'False'
        return env

    @contextlib.contextmanager
    def _patched_env(self, env):
        original = {}
        try:
            for key, value in env.items():
                original[key] = os.environ.get(key)
                os.environ[key] = value
            yield
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def run(self, block=True, system=False):
        del system  # unused, kept for API parity
        self.write()
        env = self._airflow_env()
        detach = not block
        if detach:
            raise NotImplementedError('Non-blocking airflow runs are not implemented yet')
        with self._patched_env(env):
            from airflow.utils import db
            from airflow.models.dagbag import DagBag
            from airflow.models.serialized_dag import DagVersion
            from airflow.models.dagbundle import DagBundleModel
            from airflow.models.dag import DagModel
            from airflow.utils.session import create_session
            if hasattr(db, 'check_and_run_migrations'):
                db.check_and_run_migrations()
            elif hasattr(db, 'upgradedb'):
                db.upgradedb()
            else:
                db.initdb()
            dag_bag = DagBag(dag_folder=os.fspath(self.dags_dpath), include_examples=False, safe_mode=False)
            dag = dag_bag.get_dag(self.name)
            if dag is None:
                raise RuntimeError(f'Could not load DAG {self.name} from {self.dags_dpath}')
            # Airflow 3 requires DAG bundle versioning unless explicitly disabled.
            if not getattr(dag, 'disable_bundle_versioning', False):
                dag.disable_bundle_versioning = True
            bundle_name = 'cmd_queue'
            with create_session() as session:
                dag_model = session.get(DagModel, dag.dag_id)
                if dag_model is None:
                    dag_model = DagModel(dag_id=dag.dag_id, fileloc=dag.fileloc, bundle_name=bundle_name)
                else:
                    dag_model.fileloc = dag.fileloc
                    dag_model.bundle_name = bundle_name
                session.merge(dag_model)
                if session.get(DagBundleModel, bundle_name) is None:
                    session.add(DagBundleModel(name=bundle_name))
                session.commit()
            DagVersion.write_dag(dag_id=dag.dag_id, bundle_name=bundle_name)
            dag.test()

    def finalize_text(self):
        import networkx as nx

        graph = self._dependency_graph()
        topo_jobs = [self.named_jobs[n] for n in nx.topological_sort(graph)]

        header = ub.codeblock(
            f'''
            from airflow import DAG
            from datetime import timezone
            from datetime import datetime as datetime_cls
            from airflow.providers.standard.operators.bash import BashOperator
            now = datetime_cls.now(timezone.utc)
            dag = DAG(
                '{self.name}',
                start_date=now,
                catchup=False,
                tags=['cmd_queue'],
            )
            jobs = dict()
            '''
        )
        parts = [header]
        for job in topo_jobs:
            parts.append(job.finalize_text())

        for job in topo_jobs:
            for dep in job.depends or []:
                if dep is not None:
                    parts.append(f'jobs[{job.name!r}].set_upstream(jobs[{dep.name!r}])')

        # if depends:
        #     for dep in depends:
        #         if dep is not None:
        #             self.operator.set_upstream(dep.operator)
        # parts.append('dag.run(verbose=True, local=True)')
        # t1 = BashOperator(task_id='task1', bash_command='date', dag=dag)
        # t2 = BashOperator(task_id='task2', bash_command='echo hi 1 && true', dag=dag)
        # t2.set_upstream(t1)
        text = '\n'.join(parts)
        return text
        # pass

    def submit(self, command, **kwargs):
        name = kwargs.get('name', None)
        if name is None:
            name = kwargs['name'] = f'J{len(self.jobs):04d}-{self.queue_id}'
        if 'output_fpath' not in kwargs:
            kwargs['output_fpath'] = self.log_dpath / (name + '.log')
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

        depends = kwargs.pop('depends', None)
        if depends is not None:
            # Resolve any strings to job objects
            if isinstance(depends, str) or not ub.iterable(depends):
                depends = [depends]
            depends = [
                self.named_jobs[dep] if isinstance(dep, str) else dep
                for dep in depends]
        job = AirflowJob(command, depends=depends, **kwargs)
        self.jobs.append(job)
        self.num_real_jobs += 1
        self.named_jobs[job.name] = job
        return job

    def print_commands(self, with_status=False, with_gaurds=False,
                       with_locks=1, exclude_tags=None, style='auto',
                       with_rich=None, colors=1, **kwargs):
        r"""
        Print info about the commands, optionally with rich

        Example:
            >>> # xdoctest: +SKIP
            >>> from cmd_queue.airflow_queue import *  # NOQA
            >>> self = AirflowQueue()
            >>> self.submit('date')
            >>> self.print_commands()
            >>> self.run()
        """
        style = self._coerce_style(style, with_rich, colors)

        code = self.finalize_text()

        if style == 'rich':
            from rich.panel import Panel
            from rich.syntax import Syntax
            from rich.console import Console
            console = Console()
            console.print(Panel(Syntax(code, 'python'), title=str(self.fpath)))
            # console.print(Syntax(code, 'bash'))
        elif style == 'colors':
            header = f'# --- {str(self.fpath)}'
            print(ub.highlight_code(header, 'python'))
            print(ub.highlight_code(code, 'python'))
        elif style == 'plain':
            header = f'# --- {str(self.fpath)}'
            print(header)
            print(code)
        else:
            raise KeyError(f'Unknown style={style}')

    rprint = print_commands  # backwards compat


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
