from typing import Dict
import scriptconfig as scfg
from _typeshed import Incomplete

import cmd_queue

__docstubs__: str


class CMDQueueConfig(scfg.DataConfig):
    run: Incomplete
    backend: Incomplete
    queue_name: Incomplete
    print_commands: Incomplete
    print_queue: Incomplete
    with_textual: Incomplete
    other_session_handler: Incomplete
    virtualenv_cmd: Incomplete
    tmux_workers: Incomplete
    slurm_options: Incomplete

    def __post_init__(self) -> None:
        ...

    def create_queue(config, **kwargs) -> cmd_queue.Queue:
        ...

    def run_queue(config,
                  queue: cmd_queue.Queue,
                  print_kwargs: None | Dict = None,
                  **kwargs) -> None:
        ...
