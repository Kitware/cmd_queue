import ubelt as ub
from _typeshed import Incomplete


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

    def __len__(self):
        ...

    def sync(self) -> None:
        ...

    def submit(self, command, **kwargs):
        ...

    @classmethod
    def create(cls, backend: str = ..., **kwargs):
        ...

    def print_graph(self) -> None:
        ...

    def monitor(self) -> None:
        ...


def graph_str(graph,
              with_labels: bool = ...,
              sources: Incomplete | None = ...,
              write: Incomplete | None = ...,
              ascii_only: bool = ...):
    ...
