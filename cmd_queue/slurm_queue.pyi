from _typeshed import Incomplete
from cmd_queue import base_queue


class SlurmJob(base_queue.Job):
    unused_kwargs: Incomplete
    command: Incomplete
    name: Incomplete
    output_fpath: Incomplete
    depends: Incomplete
    cpus: Incomplete
    gpus: Incomplete
    mem: Incomplete
    begin: Incomplete
    shell: Incomplete
    tags: Incomplete
    jobid: Incomplete

    def __init__(self,
                 command,
                 name: Incomplete | None = ...,
                 output_fpath: Incomplete | None = ...,
                 depends: Incomplete | None = ...,
                 partition: Incomplete | None = ...,
                 cpus: Incomplete | None = ...,
                 gpus: Incomplete | None = ...,
                 mem: Incomplete | None = ...,
                 begin: Incomplete | None = ...,
                 shell: Incomplete | None = ...,
                 tags: Incomplete | None = ...,
                 **kwargs) -> None:
        ...

    def __nice__(self):
        ...


class SlurmQueue(base_queue.Queue):
    jobs: Incomplete
    unused_kwargs: Incomplete
    queue_id: Incomplete
    dpath: Incomplete
    log_dpath: Incomplete
    fpath: Incomplete
    shell: Incomplete
    header_commands: Incomplete
    all_depends: Incomplete

    def __init__(self,
                 name: Incomplete | None = ...,
                 shell: Incomplete | None = ...,
                 **kwargs) -> None:
        ...

    def __nice__(self):
        ...

    @classmethod
    def is_available(cls):
        ...

    def submit(self, command, **kwargs):
        ...

    def add_header_command(self, command) -> None:
        ...

    def order_jobs(self):
        ...

    jobname_to_varname: Incomplete

    def finalize_text(self, exclude_tags: Incomplete | None = ...):
        ...

    def run(self, block: bool = ..., system: bool = ..., **kw):
        ...

    def monitor(self, refresh_rate: float = ...):
        ...

    def kill(self) -> None:
        ...

    def read_state(self):
        ...

    def print_commands(self,
                       with_status: bool = ...,
                       with_rich: Incomplete | None = ...,
                       colors: int = ...,
                       exclude_tags: Incomplete | None = ...,
                       style: str = ...) -> None:
        ...

    rprint: Incomplete


SLURM_NOTES: str
