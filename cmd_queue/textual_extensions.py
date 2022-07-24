from textual.app import App
from textual.driver import Driver
from typing import Type
from rich.console import Console
import asyncio


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

    CommandLine:
        xdoctest -m /home/joncrall/code/cmd_queue/cmd_queue/textual_extensions.py InstanceRunnableApp:0 --interact

    Example:
        >>> # xdoctest: +REQUIRES(--interact)
        >>> from textual import events
        >>> from textual.widgets import ScrollView
        >>> class DemoApp(InstanceRunnableApp):
        >>>     def __init__(self, myvar, **kwargs):
        >>>         super().__init__(**kwargs)
        >>>         self.myvar = myvar
        >>>     async def on_load(self, event: events.Load) -> None:
        >>>         await self.bind("q", "quit", "Quit")
        >>>     async def on_mount(self, event: events.Mount) -> None:
        >>>         self.body = body = ScrollView(auto_width=True)
        >>>         await self.view.dock(body)
        >>>         async def add_content():
        >>>             from rich.text import Text
        >>>             content = Text(self.myvar)
        >>>             await body.update(content)
        >>>         await self.call_later(add_content)
        >>> DemoApp.run(myvar='Existing classmethod way of running an App')
        >>> self = DemoApp(myvar='The instance way of running an App')
        >>> self.run()
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
