from _typeshed import Incomplete
from cmd_queue import base_queue


def indent(text: str, prefix: str = '    '):
    ...


class BashJob(base_queue.Job):
    name: Incomplete
    pathid: Incomplete
    kwargs: Incomplete
    command: Incomplete
    depends: Incomplete
    bookkeeper: Incomplete
    info_dpath: Incomplete
    pass_fpath: Incomplete
    fail_fpath: Incomplete
    stat_fpath: Incomplete

    def __init__(self,
                 command,
                 name: Incomplete | None = ...,
                 depends: Incomplete | None = ...,
                 gpus: Incomplete | None = ...,
                 cpus: Incomplete | None = ...,
                 mem: Incomplete | None = ...,
                 bookkeeper: int = ...,
                 info_dpath: Incomplete | None = ...,
                 **kwargs) -> None:
        ...

    def finalize_text(self,
                      with_status: bool = ...,
                      with_gaurds: bool = ...,
                      conditionals: Incomplete | None = ...):
        ...

    def rprint(self,
               with_status: bool = ...,
               with_gaurds: bool = ...,
               with_rich: int = ...) -> None:
        ...


class SerialQueue(base_queue.Queue):
    name: Incomplete
    rootid: Incomplete
    dpath: Incomplete
    unused_kwargs: Incomplete
    fpath: Incomplete
    state_fpath: Incomplete
    environ: Incomplete
    header: str
    header_commands: Incomplete
    jobs: Incomplete
    cwd: Incomplete
    job_info_dpath: Incomplete

    def __init__(self,
                 name: str = ...,
                 dpath: Incomplete | None = ...,
                 rootid: Incomplete | None = ...,
                 environ: Incomplete | None = ...,
                 cwd: Incomplete | None = ...,
                 **kwargs) -> None:
        ...

    @property
    def pathid(self):
        ...

    def __nice__(self):
        ...

    def finalize_text(self, with_status: bool = ..., with_gaurds: bool = ...):
        ...

    def add_header_command(self, command) -> None:
        ...

    def write(self):
        ...

    def rprint(self,
               with_status: bool = ...,
               with_gaurds: bool = ...,
               with_rich: int = ...) -> None:
        ...

    def run(self, block: Incomplete | None = ...) -> None:
        ...

    def read_state(self):
        ...
