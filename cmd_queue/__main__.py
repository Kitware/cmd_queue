from __future__ import annotations

from typing import Any, Callable

from . import main as main_mod

main: Callable[..., Any] = main_mod.main

if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/cmd_queue/__main__.py
    """
    main()
