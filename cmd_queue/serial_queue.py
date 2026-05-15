"""Compatibility facade for the serial backend.

The implementation lives in :mod:`cmd_queue.backends.serial`.  This module
keeps the historical import path stable for external users.
"""

from cmd_queue.backends.serial import (
    BashJob,
    SerialQueue,
    _check_bash_text_for_syntax_errors,
    indent,
)

__all__ = [
    'BashJob',
    'SerialQueue',
    'indent',
    '_check_bash_text_for_syntax_errors',
]
