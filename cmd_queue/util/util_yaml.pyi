from typing import Any
import io
from os import PathLike


class _YamlRepresenter:

    @staticmethod
    def str_presenter(dumper, data):
        ...


class Yaml:

    @staticmethod
    def dumps(data: Any, backend: str = 'ruamel') -> str:
        ...

    @staticmethod
    def load(file: io.TextIOBase | PathLike | str,
             backend: str = 'ruamel') -> object:
        ...

    @staticmethod
    def loads(text: str, backend: str = 'ruamel') -> object:
        ...

    @staticmethod
    def coerce(data: str | PathLike | dict | list,
               backend: str = 'ruamel') -> object:
        ...

    @staticmethod
    def InlineList(items):
        ...

    @staticmethod
    def Dict(data):
        ...

    @staticmethod
    def CodeBlock(text):
        ...
