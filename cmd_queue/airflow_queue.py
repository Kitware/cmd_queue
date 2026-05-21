"""Compatibility facade for the Airflow backend.

The implementation lives in :mod:`cmd_queue.backends.airflow`.  This module
keeps the historical import path stable for external users.
"""

from cmd_queue.backends.airflow import AirflowJob, AirflowQueue, demo

__all__ = [
    'AirflowJob',
    'AirflowQueue',
    'demo',
]
