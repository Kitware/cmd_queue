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

    def write(self):
        ...

    def submit(self, command, **kwargs):
        ...

    def add_header_command(self, command) -> None:
        ...

    def order_jobs(self):
        ...

    def finalize_text(self):
        ...

    def run(self, block: bool = ...):
        ...

    def monitor(self, refresh_rate: float = ...):
        ...

    def rprint(self, with_status: bool = ..., with_rich: int = ...) -> None:
        ...


SLURM_NOTES: str
