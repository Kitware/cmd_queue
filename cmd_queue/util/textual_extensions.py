from textual.app import App
from textual.driver import Driver
from typing import Type
from rich.console import Console
import asyncio


from textual import events
from textual.widget import Widget
from textual.reactive import watch, Reactive
from datetime import datetime
from rich.panel import Panel
from rich.style import StyleType
from rich.table import Table
from rich.console import RenderableType
from rich.repr import Result


class class_or_instancemethod(classmethod):
    """
    References:
        https://stackoverflow.com/questions/28237955/same-name-for-classmethod-and-instancemethod
    """
    def __get__(self, instance, type_):
        descr_get = super().__get__ if instance is None else self.__func__.__get__
        return descr_get(instance, type_)


class InstanceRunnableApp(App):
    """
    Extension of App that allows for running an instance
    """

    @classmethod
    def _run_as_cls(
        cls,
        console: Console = None,
        screen: bool = True,
        driver: Type[Driver] = None,
        **kwargs,
    ):
        """
        Original classmethod logic
        """
        async def run_app() -> None:
            app = cls(screen=screen, driver_class=driver, **kwargs)
            await app.process_messages()

        asyncio.run(run_app())

    def _run_as_instance(
        self,
        console: Console = None,
        screen: bool = True,
        driver: Type[Driver] = None,
        **kwargs,
    ):
        """
        New instancemethod logic
        """
        if len(kwargs):
            raise ValueError(
                'Cannot pass kwargs when running as an instance method. '
                'Assuming that instance variables are already setup.')
        async def run_app() -> None:
            self.console = console or self.console
            self.screen = screen or self._screen
            self.driver = driver or self._driver
            await self.process_messages()
        asyncio.run(run_app())

    # Allow for use of run as a instance or classmethod
    @class_or_instancemethod
    def run(
        cls_or_self,
        console: Console = None,
        screen: bool = True,
        driver: Type[Driver] = None,
        **kwargs,
    ):
        """Run the app.
        Args:
            console (Console, optional): Console object. Defaults to None.
            screen (bool, optional): Enable application mode. Defaults to True.
            driver (Type[Driver], optional): Driver class or None for default. Defaults to None.
        """
        if isinstance(cls_or_self, type):
            # Running as a class method
            cls_or_self._run_as_cls(
                screen=screen, driver=driver, **kwargs)
        else:
            # Running as an instance method
            cls_or_self._run_as_instance(
                screen=screen, driver=driver, **kwargs)


class ExtHeader(Widget):
    """
    """
    def __init__(
        self,
        *,
        tall: bool = True,
        style: StyleType = "white on dark_green",
        clock: bool = True,
    ) -> None:
        super().__init__()
        self.tall = tall
        self.style = style
        self.clock = clock

    tall: Reactive[bool] = Reactive(True, layout=True)
    style: Reactive[StyleType] = Reactive("white on blue")
    clock: Reactive[bool] = Reactive(True)
    title: Reactive[str] = Reactive("")
    sub_title: Reactive[str] = Reactive("")

    @property
    def full_title(self) -> str:
        return f"{self.title} - {self.sub_title}" if self.sub_title else self.title

    def __rich_repr__(self) -> Result:
        yield self.title

    async def watch_tall(self, tall: bool) -> None:
        self.layout_size = 3 if tall else 1

    def get_clock(self) -> str:
        return datetime.now().time().strftime("%X")

    def render(self) -> RenderableType:
        header_table = Table.grid(padding=(0, 1), expand=True)
        header_table.style = self.style
        header_table.add_column(justify="left", ratio=0, width=8)
        header_table.add_column("title", justify="center", ratio=1)
        header_table.add_column("clock", justify="right", width=8)
        header_table.add_row(
            "⚡", self.full_title, self.get_clock() if self.clock else ""
        )
        header: RenderableType
        header = Panel(header_table, style=self.style) if self.tall else header_table
        return header

    async def on_mount(self, event: events.Mount) -> None:
        self.set_interval(1.0, callback=self.refresh)

        async def set_title(title: str) -> None:
            self.title = title

        async def set_sub_title(sub_title: str) -> None:
            self.sub_title = sub_title

        watch(self.app, "title", set_title)
        watch(self.app, "sub_title", set_sub_title)

    async def on_click(self, event: events.Click) -> None:
        self.tall = not self.tall
