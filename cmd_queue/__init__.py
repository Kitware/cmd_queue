"""
mkinit -m cmd_queue
"""
__version__ = '0.0.1'


__submodules__ = {
    'base_queue': ['Queue'],
}
from cmd_queue import base_queue

from cmd_queue.base_queue import (Queue,)

__all__ = ['Queue', 'base_queue']
