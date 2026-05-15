"""Private backend registry.

The public API remains ``Queue.create`` and the historical backend modules.
This registry only centralizes the backend lookup so future refactors can move
backend internals without changing user-facing imports.
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, Tuple, Type


_BACKEND_SPECS: Dict[str, Tuple[str, str]] = {
    'serial': ('cmd_queue.backends.serial', 'SerialQueue'),
    'tmux': ('cmd_queue.backends.tmux', 'TMUXMultiQueue'),
    'slurm': ('cmd_queue.backends.slurm', 'SlurmQueue'),
    'airflow': ('cmd_queue.backends.airflow', 'AirflowQueue'),
}

# Historically ``Queue.create(..., size=...)`` silently ignored size for every
# backend except tmux.  Preserve that behavior here.
_IGNORE_SIZE_FOR_BACKENDS = {'serial', 'slurm', 'airflow'}


class UnknownBackendName(KeyError):
    """Raised when the private registry does not know a backend name."""


def backend_names() -> list[str]:
    """Return backend names in the historical order."""

    return list(_BACKEND_SPECS)


def load_backend_class(backend: str) -> Type[Any]:
    """Load one backend class by name without importing every backend."""

    try:
        module_name, class_name = _BACKEND_SPECS[backend]
    except KeyError:
        raise UnknownBackendName(backend) from None
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def backend_classes() -> Dict[str, Type[Any]]:
    """Return a name-to-class mapping in the historical order."""

    return {name: load_backend_class(name) for name in backend_names()}


def create_backend(backend: str, **kwargs: Any) -> Any:
    """Instantiate one backend while preserving ``Queue.create`` quirks."""

    qcls = load_backend_class(backend)
    if backend in _IGNORE_SIZE_FOR_BACKENDS:
        kwargs.pop('size', None)
    return qcls(**kwargs)
