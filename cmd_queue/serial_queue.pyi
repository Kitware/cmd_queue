from typing import Union
from typing import List
from os import PathLike
from _typeshed import Incomplete
from cmd_queue import base_queue


def indent(text: str, prefix: str = '    '):
    ...


class BashJob(base_queue.Job):
    name: str
    pathid: str
    command: str
    depends: Union[List[BashJob], None]
    bookkeeper: bool
    info_dpath: Union[PathLike, None]
    log: bool
    tags: Union[List[str], str, None]
    allow_indent: bool
    kwargs: Incomplete
    pass_fpath: Incomplete
    fail_fpath: Incomplete
    stat_fpath: Incomplete
    log_fpath: Incomplete

    def __init__(self,
                 command,
                 name: Incomplete | None = ...,
                 depends: Incomplete | None = ...,
                 gpus: Incomplete | None = ...,
                 cpus: Incomplete | None = ...,
                 mem: Incomplete | None = ...,
                 bookkeeper: int = ...,
                 info_dpath: Incomplete | None = ...,
                 log: bool = ...,
                 tags: Incomplete | None = ...,
                 allow_indent: bool = ...,
                 **kwargs) -> None:
        ...

    def finalize_text(self,
                      with_status: bool = ...,
                      with_gaurds: bool = ...,
                      conditionals: Incomplete | None = ...):
        ...

    def print_commands(self,
                       with_status: bool = ...,
                       with_gaurds: bool = ...,
                       with_rich: Incomplete | None = ...,
                       colors: int = ...,
                       style: str = ...,
                       **kwargs) -> None:
        ...

    rprint: Incomplete


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

    @classmethod
    def is_available(cls):
        ...

    def finalize_text(self,
                      with_status: bool = ...,
                      with_gaurds: bool = ...,
                      with_locks: bool = ...,
                      exclude_tags: Incomplete | None = ...):
        ...

    def add_header_command(self, command) -> None:
        ...

    def print_commands(self,
                       with_status: bool = ...,
                       with_gaurds: bool = ...,
                       with_rich: Incomplete | None = ...,
                       colors: int = ...,
                       with_locks: bool = ...,
                       exclude_tags: Incomplete | None = ...,
                       style: str = ...) -> None:
        ...

    rprint: Incomplete

    def run(self,
            block: bool = ...,
            system: bool = ...,
            shell: int = ...,
            **kw) -> None:
        ...

    def job_details(self) -> None:
        ...

    def read_state(self):
        ...
