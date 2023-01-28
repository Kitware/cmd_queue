from _typeshed import Incomplete
from cmd_queue import base_queue


class AirflowJob(base_queue.Job):
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

    def finalize_text(self):
        ...


class AirflowQueue(base_queue.Queue):
    jobs: Incomplete
    name: Incomplete
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

    @classmethod
    def is_available(cls):
        ...

    def run(self, block: bool = ..., system: bool = ...) -> None:
        ...

    def finalize_text(self):
        ...

    def submit(self, command, **kwargs):
        ...

    def print_commands(self,
                       with_status: bool = ...,
                       with_gaurds: bool = ...,
                       with_rich: Incomplete | None = ...,
                       colors: int = ...,
                       style: str = ...) -> None:
        ...

    rprint: Incomplete


def demo() -> None:
    ...
