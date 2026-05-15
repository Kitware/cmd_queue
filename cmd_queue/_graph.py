"""Private dependency graph helpers.

These helpers are deliberately small and behavior-preserving.  They centralize
logic that was historically implemented directly on ``Queue`` so later backend
refactors can share one dependency model.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import ubelt as ub


def coerce_depends(depends: Any) -> Optional[List[Any]]:
    """Normalize dependency input to ``None`` or a list.

    This preserves the historical ``ubelt.iterable`` behavior used by
    ``Queue.submit`` and ``Job.__init__``.
    """

    if depends is None:
        return None
    if not ub.iterable(depends):
        depends = [depends]
    return list(depends)


def merge_sync_depends(all_depends: Optional[List[Any]], depends: Any) -> Any:
    """Apply queue-level ``sync`` dependencies to a submit-time dependency."""

    if all_depends:
        coerced = coerce_depends(depends)
        if coerced is None:
            return list(all_depends)
        return list(all_depends) + coerced
    return depends


def resolve_dependency_refs(depends: Any, named_jobs: Dict[str, Any]) -> Optional[List[Any]]:
    """Resolve string dependency references against a queue's named jobs."""

    coerced = coerce_depends(depends)
    if coerced is None:
        return None
    return [named_jobs[dep] if isinstance(dep, str) else dep for dep in coerced]


def build_dependency_graph(jobs: Iterable[Any]) -> Any:
    """Build the networkx dependency graph for a queue's jobs."""

    import networkx as nx

    jobs = list(jobs)
    graph = nx.DiGraph()
    duplicate_names = ub.find_duplicates(jobs, key=lambda x: x.name)
    if duplicate_names:
        print('duplicate_names = {}'.format(ub.urepr(duplicate_names, nl=1)))
        raise Exception('Job names must be unique')

    for index, job in enumerate(jobs):
        graph.add_node(job.name, job=job, index=index)
    for index, job in enumerate(jobs):
        if job.depends:
            for dep in job.depends:
                if dep is not None:
                    graph.add_edge(dep.name, job.name)
    return graph


def sink_jobs(jobs: Iterable[Any]) -> List[Any]:
    """Return jobs that no other job depends on."""

    graph = build_dependency_graph(jobs)
    return [graph.nodes[n]['job'] for n, d in graph.out_degree if d == 0]
