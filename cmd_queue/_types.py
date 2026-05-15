"""Internal typing helpers for cmd_queue.

This module is intentionally private.  It gives refactors a shared place for
small typed data containers without changing the public API.
"""
from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from typing import Any, Dict, Iterable, Optional, Protocol, TypeAlias, Union, runtime_checkable


Pathish: TypeAlias = Union[str, PathLike[str]]
JobName: TypeAlias = str
DependencyRef: TypeAlias = Union[JobName, "JobProtocol"]
DependencyRefs: TypeAlias = Optional[Union[DependencyRef, Iterable[DependencyRef]]]
BackendName: TypeAlias = str


@runtime_checkable
class JobProtocol(Protocol):
    """Small protocol shared by internal queue graph helpers."""

    name: Optional[str]
    command: Optional[str]
    depends: Any
    bookkeeper: int

    def finalize_text(self, *args: Any, **kwargs: Any) -> str: ...


@runtime_checkable
class QueueProtocol(Protocol):
    """Small protocol shared by internal backend contract tests."""

    name: str
    jobs: list[JobProtocol]
    named_jobs: Dict[str, JobProtocol]

    @classmethod
    def is_available(cls) -> bool: ...

    def submit(self, command: Any, **kwargs: Any) -> JobProtocol: ...

    def finalize_text(self, **kwargs: Any) -> str: ...

    def print_commands(self, **kwargs: Any) -> None: ...

    def read_state(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class QueuePaths:
    """Internal path bundle used by future backend refactors."""

    dpath: Optional[Pathish] = None
    fpath: Optional[Pathish] = None
    job_info_dpath: Optional[Pathish] = None


@dataclass(frozen=True)
class StatusPaths:
    """Internal status path bundle used by bash-like backends."""

    pass_fpath: Optional[Pathish] = None
    fail_fpath: Optional[Pathish] = None
    skip_fpath: Optional[Pathish] = None
    stat_fpath: Optional[Pathish] = None
    log_fpath: Optional[Pathish] = None


@dataclass(frozen=True)
class RenderOptions:
    """Internal common render options for bash-like backends."""

    with_status: bool = False
    with_gaurds: bool = False
    with_locks: bool = True
    style: str = 'colors'
