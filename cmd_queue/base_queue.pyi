from typing import List
import ubelt as ub
from _typeshed import Incomplete


class DuplicateJobError(KeyError):
    ...


class UnknownBackendError(KeyError):
    ...


class Job(ub.NiceRepr):
    name: Incomplete
    command: Incomplete
    depends: Incomplete
    kwargs: Incomplete

    def __init__(self,
                 command: Incomplete | None = ...,
                 name: Incomplete | None = ...,
                 depends: Incomplete | None = ...,
                 **kwargs) -> None:
        ...

    def __nice__(self):
        ...


class Queue(ub.NiceRepr):
    num_real_jobs: int
    all_depends: Incomplete
    named_jobs: Incomplete

    def __init__(self) -> None:
        ...

    def change_backend(self, backend, **kwargs):
        ...

    def __len__(self):
        ...

    def sync(self) -> Queue:
        ...

    def write(self):
        ...

    def submit(self, command, **kwargs):
        ...

    @classmethod
    def available_backends(cls):
        ...

    @classmethod
    def create(cls, backend: str = ..., **kwargs):
        ...

    def write_network_text(self,
                           reduced: bool = ...,
                           rich: str = ...,
                           vertical_chains: bool = ...) -> None:
        ...

    def print_commands(self,
                       with_status: bool = False,
                       with_gaurds: bool = False,
                       with_locks: bool | int = 1,
                       exclude_tags: List[str] | None = None,
                       style: str = 'colors',
                       **kwargs) -> None:
        ...

    def rprint(self, **kwargs) -> None:
        ...

    def print_graph(self,
                    reduced: bool = True,
                    vertical_chains: bool = ...) -> None:
        ...

    def monitor(self) -> None:
        ...
