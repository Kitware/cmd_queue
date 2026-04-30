from __future__ import annotations
# mypy: ignore-errors

"""
Persistent metadata describing a queue at run-time so that a monitor process
can reattach to it without holding a live queue object.

A monitor manifest is a small JSON file written by ``Queue.run()`` (or its
subclass overrides). It captures everything the monitor needs to:

    * read worker state files (tmux backend) or job ids (slurm backend)
    * cleanup the queue (kill tmux sessions, scancel slurm jobs)

The :func:`load_queue_for_monitoring` factory rebuilds a queue object
that is sufficient for ``monitor()`` and ``kill()`` to work, without
re-submitting jobs or re-running the workload.

An "active queue" index in ``~/.cache/cmd_queue/active/<name>.json`` maps
a human queue name to the most recent manifest path so that
``cmd_queue monitor <qname>`` can find it.
"""
import json
from typing import Any, Dict, Optional

import ubelt as ub


SCHEMA_VERSION = 1


def manifest_path_for_dpath(dpath: Any) -> ub.Path:
    """Canonical location of the manifest file inside a queue's dpath."""
    return ub.Path(dpath) / 'monitor_manifest.json'


def _active_index_dpath() -> ub.Path:
    return ub.Path.appdir('cmd_queue/active').ensuredir()


def active_index_path(name: str) -> ub.Path:
    """Path to the active-queue index entry for the given queue name."""
    return _active_index_dpath() / f'{name}.json'


def write_manifest(manifest: Dict[str, Any], path: Any) -> ub.Path:
    """Atomically write a manifest dict to ``path``."""
    path = ub.Path(path)
    path.parent.ensuredir()
    payload = dict(manifest)
    payload.setdefault('schema_version', SCHEMA_VERSION)
    payload['manifest_path'] = str(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp.replace(path)
    return path


def read_manifest(path: Any) -> Dict[str, Any]:
    return json.loads(ub.Path(path).read_text())


def update_active_index(name: str, manifest_path: Any) -> Optional[ub.Path]:
    """Record ``name -> manifest_path`` so ``cmd_queue monitor <name>`` works.

    Returns the active index entry path on success, ``None`` if no name was
    provided (e.g. the queue was unnamed).
    """
    if not name:
        return None
    entry = active_index_path(name)
    payload = {
        'name': name,
        'manifest_path': str(manifest_path),
        'updated_at': ub.timestamp(),
    }
    entry.parent.ensuredir()
    tmp = entry.with_suffix(entry.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp.replace(entry)
    return entry


def resolve_manifest(name_or_path: str) -> ub.Path:
    """Resolve a name or path argument to an absolute manifest path.

    Accepts:
        * an absolute or relative path to a manifest file
        * a path to a queue dpath (containing ``monitor_manifest.json``)
        * a queue name registered in the active-queue index
    """
    candidate = ub.Path(name_or_path).expand()
    if candidate.is_file():
        return candidate.absolute()
    if candidate.is_dir():
        nested = manifest_path_for_dpath(candidate)
        if nested.exists():
            return nested.absolute()
    entry = active_index_path(name_or_path)
    if entry.exists():
        info = json.loads(entry.read_text())
        path = ub.Path(info['manifest_path'])
        if path.exists():
            return path.absolute()
        raise FileNotFoundError(
            f'Active-index entry for {name_or_path!r} points to '
            f'{path}, which no longer exists.'
        )
    raise FileNotFoundError(
        f'Could not resolve {name_or_path!r} to a queue manifest. '
        f'Tried as path, dpath, and active-index name.'
    )


def load_queue_for_monitoring(manifest_path: Any) -> Any:
    """Construct a queue object from a manifest, suitable for monitor/kill.

    The returned queue has no submitted jobs. Its ``monitor()`` and
    ``kill()`` methods operate on the persisted state files / job ids that
    the original ``run()`` invocation produced.
    """
    manifest = read_manifest(manifest_path)
    backend = manifest['backend']
    if backend == 'tmux':
        from cmd_queue import tmux_queue

        return tmux_queue.TMUXMultiQueue._from_manifest(manifest)
    elif backend == 'slurm':
        from cmd_queue import slurm_queue

        return slurm_queue.SlurmQueue._from_manifest(manifest)
    else:
        raise NotImplementedError(
            f'Monitor reattach is not implemented for backend {backend!r}'
        )
