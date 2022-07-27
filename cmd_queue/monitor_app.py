# from __future__ import annotations

try:
    from textual import events
    from textual.widgets import ScrollView
    from textual.widget import Widget
    from textual.views import DockView
    from cmd_queue.util.textual_extensions import ExtHeader
    from cmd_queue.util.textual_extensions import InstanceRunnableApp

    # from rich.panel import Panel
    # from rich.text import Text
    from cmd_queue.util import richer as rich
    from cmd_queue.util import texter as textual
    # import ubelt as ub
except ImportError:
    rich = None
    textual = None
    events = None
    ScrollView = object
    Widget = object
    DockView = object
    InstanceRunnableApp = object
    ExtHeader = object


class JobTable(Widget):

    def __init__(self, table_fn=None, **kwargs):
        super().__init__(**kwargs)
        self.table_fn = table_fn

    def on_mount(self):
        refresh_rate = 0.5
        self.set_interval(refresh_rate, self.refresh)

    def render(self):
        table_fn = self.table_fn
        table, finished, agg_state = table_fn()
        # self.app.post_message_no_wait('quit')
        # self.app.emit_no_wait('quit')
        # if finished:
        #     await self.app.shutdown()
        if finished:
            self.app.graceful_exit = True
            self.post_message_no_wait(events.ShutdownRequest(sender=self))
        return table


class CmdQueueMonitorApp(InstanceRunnableApp):
    """
    A Textual App to monitor jobs
    """

    def __init__(self, table_fn, kill_fn=None, **kwargs):
        self.job_table = JobTable(table_fn)
        self.kill_fn = kill_fn
        self.graceful_exit = False
        super().__init__(**kwargs)
        self._title = 'Command Queue'

    @classmethod
    def demo(CmdQueueMonitorApp):
        """
        This creates an app instance that we can run

        CommandLine:
            xdoctest -m /home/joncrall/code/cmd_queue/cmd_queue/monitor_app.py CmdQueueMonitorApp.demo:0 --interact

        Example:
            >>> # xdoctest: +REQUIRES(module:textual)
            >>> # xdoctest: +REQUIRES(--interact)
            >>> from cmd_queue.monitor_app import CmdQueueMonitorApp
            >>> self = CmdQueueMonitorApp.demo()
            >>> self.run()
            >>> print(f'self.graceful_exit={self.graceful_exit}')
        """
        countdown = 10
        def demo_table_fn():
            nonlocal countdown
            import random
            r = random.random()
            columns = ['name', 'status', 'passed', 'errors', 'total']
            table = rich.table.Table()
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
            countdown = countdown - 1
            finished = countdown <= 0
            agg_state = None
            return table, finished, agg_state
        return CmdQueueMonitorApp(demo_table_fn)

    async def on_load(self, event) -> None:
        await self.bind("q", "quit", "Quit")

    async def action_quit(self) -> None:
        await self.shutdown()

    async def on_mount(self, event) -> None:
        # from textual.layouts.vertical import VerticalLayout

        view: DockView = await self.push_view(DockView())
        header = ExtHeader(tall=False)
        footer = textual.widgets.Footer()
        # panel = rich.panel.Panel()

        # text = textual.widgets.Placeholder()
        table_view = ScrollView(auto_width=True)
        # scrollview2 = ScrollView(auto_width=True)
        # vlayout = VerticalLayout()
        # vlayout.add(text)
        # vlayout.add(table_view)

        await view.dock(header, edge="top")
        await view.dock(footer, edge="bottom")
        await view.dock(table_view)
        # await view.dock(scrollview2)

        async def add_content():
            # await scrollview2.update(text)
            await table_view.update(self.job_table)

        await self.call_later(add_content)
        # await self.call_later(self.shutdown)


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/cmd_queue/monitor_app.py
    """
    # import xdoctest
    # xdoctest.doctest_callable(CmdQueueMonitorApp.demo)
    # CmdQueueMonitorApp.demo().run(log='textual.log', log_verbosity=10000)
    self = CmdQueueMonitorApp.demo()
    self.run()
    print(f'self.graceful_exit={self.graceful_exit}')
