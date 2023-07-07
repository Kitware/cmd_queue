import scriptconfig as scfg
from _typeshed import Incomplete


class CommonConfig(scfg.DataConfig):
    qname: Incomplete
    dpath: Incomplete

    def __post_init__(config) -> None:
        ...

    @classmethod
    def main(cls, cmdline: int = ..., **kwargs) -> None:
        ...


class CommonShowRun(CommonConfig):
    workers: Incomplete
    backend: Incomplete


class CmdQueueCLI(scfg.ModalCLI):

    class cleanup(CommonConfig):
        yes: Incomplete
        __command__: str

        def run(config) -> None:
            ...

    class run(CommonShowRun):
        __command__: str

        def run(config) -> None:
            ...

    class show(CommonShowRun):
        __command__: str

        def run(config) -> None:
            ...

    class submit(CommonConfig):
        jobname: Incomplete
        depends: Incomplete
        command: Incomplete
        __command__: str

        def run(config) -> None:
            ...

    class new(CommonConfig):
        __command__: str
        header: Incomplete

        def run(config) -> None:
            ...

    class list(CommonConfig):
        __command__: str

        def run(config) -> None:
            ...


main: Incomplete
