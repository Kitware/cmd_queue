from . import util_network_text


write_network_text = util_network_text.write_network_text


def is_topological_order(graph, node_order):
    """
    A topological ordering of nodes is an ordering of the nodes such that for
    every edge (u,v) in G, u appears earlier than v in the ordering

    Runtime:
        O(V * E)

    References:
        https://stackoverflow.com/questions/54174116/checking-validity-of-topological-sort

    Example:
        >>> import networkx as nx
        >>> raw = nx.erdos_renyi_graph(100, 0.5, directed=True, seed=3432)
        >>> graph = nx.DiGraph(nodes=raw.nodes())
        >>> graph.add_edges_from([(u, v) for u, v in raw.edges() if u < v])
        >>> node_order = list(nx.topological_sort(graph))
        >>> assert is_topological_order(graph, node_order)
        >>> assert not is_topological_order(graph, node_order[::-1])
    """
    # Iterate through the edges in G.
    node_to_index = {n: idx for idx, n in enumerate(node_order)}
    for u, v in graph.edges:
        try:
            # For each edge, retrieve the index of each of its vertices in the ordering.
            ux = node_to_index[u]
            vx = node_to_index[v]
            # Compared the indices. If the origin vertex isn't earlier than
            # the destination vertex, return false.
            if ux >= vx:
                return False
        except KeyError:
            # if the edge is not in or ordering, ignore it
            ...
    return True
