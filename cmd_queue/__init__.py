
__mkinit__ = """
mkinit -m cmd_queue
"""
__version__ = '0.1.0'
__author__ = 'Kitware Inc., Jon Crall'
__author_email__ = 'kitware@kitware.com, jon.crall@kitware.com'
__url__ = 'https://gitlab.kitware.com/computer-vision/cmd_queue'


__submodules__ = {
    'base_queue': ['Queue'],
}
from cmd_queue import base_queue

from cmd_queue.base_queue import (Queue,)

__all__ = ['Queue', 'base_queue']
