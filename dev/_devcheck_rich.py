"""
SeeAlso:
    https://github.com/Textualize/rich/blob/master/examples/top_lite_simulator.py

Cant do this with pure rich
    https://github.com/Textualize/rich/issues/2120
"""
from rich.table import Table
from rich.live import Live
import time


def random_rich_table():
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


def simple_update_no_pager():
    table = random_rich_table()
    refresh_rate = 0.4
    live_context = Live(table, refresh_per_second=4)
    with live_context as live:
        while True:
            time.sleep(refresh_rate)
            table = random_rich_table()
            live.update(table)


def simple_pager_no_update():
    from rich.console import Console
    console = Console()
    table = random_rich_table()
    with console.pager():
        console.print(table)


def combined_scrolling_table():
    from textual import events
    from textual.app import App
    from textual.widgets import ScrollView
    from textual.widget import Widget

    class JobTable(Widget):
        def on_mount(self):
            self.set_interval(0.4, self.refresh)

        def render(self):
            table = random_rich_table()
            return table

    class MyApp(App):
        """An example of a very simple Textual App"""

        async def on_load(self, event: events.Load) -> None:
            await self.bind("q", "quit", "Quit")

        async def on_mount(self, event: events.Mount) -> None:

            self.body = body = ScrollView(auto_width=True)

            await self.view.dock(body)

            async def add_content():
                table = JobTable()
                await body.update(table)

            await self.call_later(add_content)

    MyApp.run(title="Simple App", log="textual.log")


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/dev/_devcheck_rich.py
    """
    combined_scrolling_table()
