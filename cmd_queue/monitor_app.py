from textual import events
# from textual.app import App
from textual.widgets import ScrollView
from textual.widget import Widget
from textual.views import DockView
from rich.table import Table
from textual.widgets import Header
from textual.widgets import Footer
# import ubelt as ub
from cmd_queue.util.textual_extensions import ExtHeader
from cmd_queue.util.textual_extensions import InstanceRunnableApp


class JobTable(Widget):

    def __init__(self, table_fn=None, **kwargs):
        super().__init__(**kwargs)
        self.table_fn = table_fn

    def on_mount(self):
        self.set_interval(0.4, self.refresh)

    def render(self):
        table_fn = self.table_fn
        if table_fn is not None:
            table = table_fn()
        else:
            table = Table(title='empty table')
            table.add_column('empty-col')
            table.add_row('foo')
        return table


def demo_table_fn():
    import random
    r = random.random()
    columns = ['name', 'status', 'finished', 'errors', 'total']
    table = Table()
    for col in columns:
        table.add_column(col)

    for i in range(100):
        table.add_row(
            'Job {:0.3f}'.format(i + r),
            'demo',
            str(i + r),
            '0',
            str(i + r),
        )
    return table


class CmdQueueMonitorApp(InstanceRunnableApp):
    """
    A Textual App to monitor jobs
    """

    def __init__(self, table_fn, kill_fn=None, **kwargs):
        self.job_table = JobTable(table_fn)
        self.kill_fn = kill_fn
        super().__init__(**kwargs)
        self._title = 'Command Queue'

    @classmethod
    def demo(CmdQueueMonitorApp):
        """
        This creates an app instance that we can run

        CommandLine:
            xdoctest -m /home/joncrall/code/cmd_queue/cmd_queue/monitor_app.py CmdQueueMonitorApp.demo:0 --interact

        Example:
            >>> # xdoctest: +REQUIRES(--interact)
            >>> from cmd_queue.monitor_app import CmdQueueMonitorApp
            >>> CmdQueueMonitorApp.demo().run()
        """
        return CmdQueueMonitorApp(demo_table_fn)

    async def on_load(self, event: events.Load) -> None:
        await self.bind("q", "quit", "Quit")

    async def action_quit(self) -> None:
        await self.shutdown()

    async def on_mount(self, event: events.Mount) -> None:

        view = await self.push_view(DockView())
        header = ExtHeader(tall=False)
        footer = Footer()
        table_view = ScrollView(auto_width=True)
        await view.dock(header, edge="top")
        await view.dock(footer, edge="bottom")
        await view.dock(table_view)

        async def add_content():
            await table_view.update(self.job_table)

        await self.call_later(add_content)
        # await self.call_later(self.shutdown)


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/cmd_queue/monitor_app.py
    """
    CmdQueueMonitorApp.demo().run()
