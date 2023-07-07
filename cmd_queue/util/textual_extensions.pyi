from _typeshed import Incomplete
from rich.console import RenderableType
from rich.repr import Result
from textual.app import App
from textual.reactive import Reactive
from textual.widget import Widget


class class_or_instancemethod(classmethod):

    def __get__(self, instance, type_):
        ...


class InstanceRunnableApp(App):

    def run(cls_or_self,
            console: Incomplete | None = ...,
            screen: bool = True,
            driver: Incomplete | None = ...,
            **kwargs):
        ...


class ExtHeader(Widget):
    tall: Incomplete
    style: Incomplete
    clock: Incomplete

    def __init__(self,
                 *,
                 tall: bool = True,
                 style: str = ...,
                 clock: bool = True) -> None:
        ...

    title: Reactive[str]
    sub_title: Reactive[str]

    @property
    def full_title(self) -> str:
        ...

    def __rich_repr__(self) -> Result:
        ...

    layout_size: Incomplete

    async def watch_tall(self, tall: bool) -> None:
        ...

    def get_clock(self) -> str:
        ...

    def render(self) -> RenderableType:
        ...

    async def on_mount(self, event) -> None:
        ...

    async def on_click(self, event) -> None:
        ...
