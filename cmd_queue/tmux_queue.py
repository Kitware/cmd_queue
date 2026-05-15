"""Compatibility facade for the tmux backend.

The implementation lives in :mod:`cmd_queue.backends.tmux`.  This module
keeps the historical import path stable for external users.
"""

from cmd_queue.backends.tmux import (
    TMUXMultiQueue,
    _attach_hint_renderable,
    _attach_or_switch,
    _run_live_with_attach,
    has_stdin,
)

__all__ = [
    'TMUXMultiQueue',
    '_attach_hint_renderable',
    '_attach_or_switch',
    '_run_live_with_attach',
    'has_stdin',
]
