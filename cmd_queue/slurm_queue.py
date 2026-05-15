"""Compatibility facade for the Slurm backend.

The implementation lives in :mod:`cmd_queue.backends.slurm`.  This module
keeps the historical import path stable for external users.
"""

from cmd_queue.backends.slurm import (
    SLURM_NOTES,
    SLURM_SBATCH_FLAGS,
    SLURM_SBATCH_KVARGS,
    SlurmJob,
    SlurmQueue,
    _coerce_mem_megabytes,
    _unit_registery,
    parse_scontrol_output,
)

__all__ = [
    'SLURM_NOTES',
    'SLURM_SBATCH_FLAGS',
    'SLURM_SBATCH_KVARGS',
    'SlurmJob',
    'SlurmQueue',
    '_coerce_mem_megabytes',
    '_unit_registery',
    'parse_scontrol_output',
]
