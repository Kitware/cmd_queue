from _typeshed import Incomplete
from cmd_queue import base_queue


class TMUXMultiQueue(base_queue.Queue):
    name: Incomplete
    rootid: Incomplete
    pathid: Incomplete
    dpath: Incomplete
    size: Incomplete
    environ: Incomplete
    fpath: Incomplete
    gres: Incomplete
    cmd_verbose: int
    jobs: Incomplete
    header_commands: Incomplete
    job_info_dpath: Incomplete

    def __init__(self,
                 size: int = ...,
                 name: Incomplete | None = ...,
                 dpath: Incomplete | None = ...,
                 rootid: Incomplete | None = ...,
                 environ: Incomplete | None = ...,
                 gres: Incomplete | None = ...) -> None:
        ...

    @classmethod
    def is_available(cls):
        ...

    def __nice__(self):
        ...

    workers: Incomplete

    def order_jobs(self) -> None:
        ...

    def add_header_command(self, command) -> None:
        ...

    def finalize_text(self):
        ...

    def write(self) -> None:
        ...

    def kill_other_queues(self, ask_first: bool = ...) -> None:
        ...

    def handle_other_sessions(self, other_session_handler) -> None:
        ...

    def run(self,
            block: bool = ...,
            onfail: str = ...,
            onexit: str = ...,
            system: bool = ...,
            with_textual: str = ...,
            check_other_sessions: Incomplete | None = ...,
            other_session_handler: str = 'auto',
            **kw):
        ...

    def read_state(self):
        ...

    def serial_run(self) -> None:
        ...

    def monitor(self, refresh_rate: float = ..., with_textual: str = ...):
        ...

    def print_commands(self,
                       with_status: bool = ...,
                       with_gaurds: bool = ...,
                       with_rich: Incomplete | None = ...,
                       with_locks: int = ...,
                       colors: int = ...,
                       exclude_tags: Incomplete | None = ...,
                       style: str = ...) -> None:
        ...

    rprint: Incomplete

    def current_output(self) -> None:
        ...

    def capture(self) -> None:
        ...

    def kill(self) -> None:
        ...


def has_stdin():
    ...


__tmux_notes__: str
