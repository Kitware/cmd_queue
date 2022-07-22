from textual import events
from textual.app import App
from textual.widgets import ScrollView
from textual.widget import Widget
from rich.table import Table
# import ubelt as ub


class JobTable(Widget):

    # def __init__(self, **kwargs):
    #     table_fn = kwargs.pop('table_fn', None)
    #     super().__init__(**kwargs)
    #     self.table_fn = table_fn

    def on_mount(self):
        self.set_interval(0.4, self.refresh)

    def render(self):
        table_fn = getattr(self, 'table_fn', None)
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


class CmdQueueMonitorApp(App):
    """
    A Textual App to monitor jobs
    """

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     print('init self = {}'.format(ub.repr2(self, nl=1)))
    #     print('init self = {}'.format(ub.repr2(id(self), nl=1)))

    table_fn = None

    @classmethod
    def start_using(CmdQueueMonitorApp, table_fn):
        """
        It seems to be necessary to create using the class rather than
        an instance. It might be nice to have an instance-level builder, but
        for now this hack should work.
        """
        CmdQueueMonitorApp.table_fn = table_fn
        CmdQueueMonitorApp.run()

    @classmethod
    def demo_run(CmdQueueMonitorApp):
        """
        Example:
            >>> # xdoctest: +REQUIRES(--interact)
            >>> from cmd_queue.monitor_app import CmdQueueMonitorApp
            >>> CmdQueueMonitorApp.demo().run()
        """
        CmdQueueMonitorApp.start_using(demo_table_fn)

    async def on_load(self, event: events.Load) -> None:
        await self.bind("q", "quit", "Quit")

    async def on_mount(self, event: events.Mount) -> None:

        self.body = body = ScrollView(auto_width=True)

        await self.view.dock(body)

        async def add_content():
            # self.job_table = JobTable(self.table_fn)
            self.job_table = JobTable()
            self.job_table.table_fn = self.__class__.table_fn
            await body.update(self.job_table)

        await self.call_later(add_content)


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/cmd_queue/monitor_app.py
    """
    CmdQueueMonitorApp.demo_run()
