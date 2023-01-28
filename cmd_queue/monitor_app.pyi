from _typeshed import Incomplete
from cmd_queue.util.textual_extensions import InstanceRunnableApp
from textual.widget import Widget


class JobTable(Widget):
    table_fn: Incomplete

    def __init__(self, table_fn: Incomplete | None = ..., **kwargs) -> None:
        ...

    def on_mount(self) -> None:
        ...

    def render(self):
        ...


class CmdQueueMonitorApp(InstanceRunnableApp):
    job_table: Incomplete
    kill_fn: Incomplete
    graceful_exit: bool

    def __init__(self,
                 table_fn,
                 kill_fn: Incomplete | None = ...,
                 **kwargs) -> None:
        ...

    @classmethod
    def demo(CmdQueueMonitorApp):
        ...

    async def on_load(self, event) -> None:
        ...

    async def action_quit(self) -> None:
        ...

    async def on_mount(self, event) -> None:
        ...
