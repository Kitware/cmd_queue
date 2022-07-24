from textual import events
from textual.app import App
from textual.widgets import ScrollView
from textual.driver import Driver
from typing import Type
from rich.console import Console
import asyncio


class DemoApp(InstanceRunnableApp):
    """
    A Textual App to monitor jobs
    """

    def __init__(self, myvar, **kwargs):
        super().__init__(**kwargs)
        self.myvar = myvar

    async def on_load(self, event: events.Load) -> None:
        await self.bind("q", "quit", "Quit")

    async def on_mount(self, event: events.Mount) -> None:

        self.body = body = ScrollView(auto_width=True)
        await self.view.dock(body)

        async def add_content():
            from rich.text import Text
            content = Text(self.myvar)
            await body.update(content)

        await self.call_later(add_content)


DemoApp.run(myvar='Existing classmethod way of running an App')

self = DemoApp(myvar='The instance way of running an App')
self.run()
