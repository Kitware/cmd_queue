"""Compatibility facade for the Airflow backend.

The implementation lives in :mod:`cmd_queue.backends.airflow`.  This historical
module remains part of the public API, including explicit imports of private
helpers that downstream tests or scripts may have used.
"""

from cmd_queue.backends import airflow as _impl

globals().update({
    name: value for name, value in vars(_impl).items()
    if not (name.startswith('__') and name.endswith('__'))
})
