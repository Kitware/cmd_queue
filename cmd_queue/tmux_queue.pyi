from _typeshed import Incomplete
from cmd_queue import base_queue
from textual import App, events as events


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

    def __init__(self,
                 size: int = ...,
                 name: Incomplete | None = ...,
                 dpath: Incomplete | None = ...,
                 rootid: Incomplete | None = ...,
                 environ: Incomplete | None = ...,
                 gres: Incomplete | None = ...) -> None:
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

    def write(self):
        ...

    def run(self, block: bool = ..., onfail: str = ..., onexit: str = ...):
        ...

    def serial_run(self) -> None:
        ...

    def monitor(self, refresh_rate: float = ...):
        ...

    def rprint(self,
               with_status: bool = ...,
               with_gaurds: bool = ...,
               with_rich: int = ...) -> None:
        ...

    def current_output(self) -> None:
        ...

    def capture(self) -> None:
        ...

    def kill(self) -> None:
        ...


MonitorApp: Incomplete


class MonitorApp(App):

    def on_key(self) -> None:
        ...

    async def on_load(self, event: events.Load) -> None:
        ...

    body: Incomplete

    async def on_mount(self, event: events.Mount) -> None:
        ...


__tmux_notes__: str
