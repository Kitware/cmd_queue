import numpy as np


def balanced_number_partitioning(items, num_parts):
    """
    Greedy approximation to multiway number partitioning

    Uses Greedy number partitioning method to minimize the size of the largest
    partition.


    Args:
        items (np.ndarray): list of numbers (i.e. weights) to split
            between paritions.
        num_parts (int): number of partitions

    Returns:
        List[np.ndarray]:
            A list for each parition that contains the index of the items
            assigned to it.

    References:
        https://en.wikipedia.org/wiki/Multiway_number_partitioning
        https://en.wikipedia.org/wiki/Balanced_number_partitioning

    Example:
        >>> from cmd_queue.util import *  # NOQA
        >>> items = np.array([1, 3, 29, 22, 4, 5, 9])
        >>> num_parts = 3
        >>> bin_assignments = balanced_number_partitioning(items, num_parts)
        >>> import kwarray
        >>> groups = kwarray.apply_grouping(items, bin_assignments)
        >>> bin_weights = [g.sum() for g in groups]
    """
    item_weights = np.asanyarray(items)
    sortx = np.argsort(item_weights)[::-1]

    bin_assignments = [[] for _ in range(num_parts)]
    bin_sums = np.zeros(num_parts)

    for item_index in sortx:
        # Assign item to the smallest bin
        item_weight = item_weights[item_index]
        bin_index = bin_sums.argmin()
        bin_assignments[bin_index].append(item_index)
        bin_sums[bin_index] += item_weight

    bin_assignments = [np.array(p, dtype=int) for p in bin_assignments]
    return bin_assignments


def graph_str(graph, with_labels=True, sources=None, write=None, ascii_only=False):
    """
    Creates a nice utf8 representation of a graph

    Parameters
    ----------
    graph : nx.DiGraph | nx.Graph
        Graph to represent

    with_labels : bool
        If True will use the "label" attribute of a node to display if it
        exists otherwise it will use the node value itself. Defaults to True.

    sources : List
        Mainly relevant for undirected forests, specifies which nodes to list
        first. If unspecified the root nodes of each tree will be used for
        directed forests; for undirected forests this defaults to the nodes
        with the smallest degree.

    write : callable
        Function to use to write to, if None new lines are appended to
        a list and returned. If set to the `print` function, lines will
        be written to stdout as they are generated. If specified,
        this function will return None. Defaults to None.

    ascii_only : Boolean
        If True only ASCII characters are used to construct the visualization

    Returns
    -------
    str | None :
        utf8 representation of the tree / forest

    Example
    -------
    >>> import networkx as nx
    >>> graph = nx.DiGraph()
    >>> graph.add_nodes_from(['a', 'b', 'c', 'd', 'e'])
    >>> graph.add_edges_from([
    >>>     ('a', 'd'),
    >>>     ('b', 'd'),
    >>>     ('c', 'd'),
    >>>     ('d', 'e'),
    >>>     ('f1', 'g'),
    >>>     ('f2', 'g'),
    >>> ])
    >>> graph_str(graph, write=print)
    ...

    >>> graph = nx.balanced_tree(r=2, h=3, create_using=nx.DiGraph)
    >>> # A simple forest
    >>> print(graph_str(graph))
    ╙── 0
        ├─╼ 1
        │   ├─╼ 3
        │   │   ├─╼ 7
        │   │   └─╼ 8
        │   └─╼ 4
        │       ├─╼ 9
        │       └─╼ 10
        └─╼ 2
            ├─╼ 5
            │   ├─╼ 11
            │   └─╼ 12
            └─╼ 6
                ├─╼ 13
                └─╼ 14

    >>> # Add a non-forest edge
    >>> graph.add_edges_from([
    >>>     (7, 1)
    >>> ])
    >>> print(graph_str(graph))
    ╙── 0
        ├─╼ 1 ╾ 7
        │   ├─╼ 3
        │   │   ├─╼ 7
        │   │   │   └─╼  ...
        │   │   └─╼ 8
        │   └─╼ 4
        │       ├─╼ 9
        │       └─╼ 10
        └─╼ 2
            ├─╼ 5
            │   ├─╼ 11
            │   └─╼ 12
            └─╼ 6
                ├─╼ 13
                └─╼ 14

    >>> # A clique graph
    >>> graph = nx.erdos_renyi_graph(5, 1.0)
    >>> print(graph_str(graph))
    ╙── 0
        ├── 1
        │   ├── 2 ─ 0
        │   │   ├── 3 ─ 0, 1
        │   │   │   └── 4 ─ 0, 1, 2
        │   │   └──  ...
        │   └──  ...
        └──  ...

    """
    import networkx as nx

    printbuf = []
    if write is None:
        _write = printbuf.append
    else:
        _write = write

    # Define glphys
    # Notes on available box and arrow characters
    # https://en.wikipedia.org/wiki/Box-drawing_character
    # https://stackoverflow.com/questions/2701192/triangle-arrow
    if ascii_only:
        glyph_empty = "+"
        glyph_newtree_last = "+-- "
        glyph_newtree_mid = "+-- "
        glyph_endof_forest = "    "
        glyph_within_forest = ":   "
        glyph_within_tree = "|   "

        glyph_directed_last = "L-> "
        glyph_directed_mid = "|-> "
        glyph_directed_backedge = "<-"

        glyph_undirected_last = "L-- "
        glyph_undirected_mid = "|-- "
        glyph_undirected_backedge = "-"
    else:
        glyph_empty = "╙"
        glyph_newtree_last = "╙── "
        glyph_newtree_mid = "╟── "
        glyph_endof_forest = "    "
        glyph_within_forest = "╎   "
        glyph_within_tree = "│   "

        glyph_directed_last = "└─╼ "
        glyph_directed_mid = "├─╼ "
        glyph_directed_backedge = "╾"

        glyph_undirected_last = "└── "
        glyph_undirected_mid = "├── "
        glyph_undirected_backedge = "─"

    if len(graph.nodes) == 0:
        _write(glyph_empty)
    else:
        is_directed = graph.is_directed()
        if is_directed:
            glyph_last = glyph_directed_last
            glyph_mid = glyph_directed_mid
            glyph_backedge = glyph_directed_backedge
            succ = graph.succ
            pred = graph.pred
        else:
            glyph_last = glyph_undirected_last
            glyph_mid = glyph_undirected_mid
            glyph_backedge = glyph_undirected_backedge
            succ = graph.adj
            pred = graph.adj

        if sources is None:
            # For each connected part of the graph, choose at least
            # one node as a starting point, preferably without a parent
            if is_directed:
                # Choose one node from each SCC with minimum in_degree
                sccs = list(nx.strongly_connected_components(graph))
                # condensing the SCCs forms a dag, the nodes in this graph with
                # 0 in-degree correspond to the SCCs from which the minimum set
                # of nodes from which all other nodes can be reached.
                scc_graph = nx.condensation(graph, sccs)
                supernode_to_nodes = {sn: [] for sn in scc_graph.nodes()}
                for n, sn in scc_graph.graph['mapping'].items():
                    supernode_to_nodes[sn].append(n)
                sources = []
                for sn in scc_graph.nodes():
                    if scc_graph.in_degree[sn] == 0:
                        scc = supernode_to_nodes[sn]
                        node = min(scc, key=lambda n: graph.in_degree[n])
                        sources.append(node)
            else:
                # For undirected graph, the entire graph will be reachable as
                # long as we consider one node from every connected component
                sources = [
                    min(cc, key=lambda n: graph.degree[n])
                    for cc in nx.connected_components(graph)
                ]
                sources = sorted(sources, key=lambda n: graph.degree[n])

        # Populate the stack with each source node, empty indentation, and mark
        # the final node. Reverse the stack so sources are popped in the
        # correct order.
        last_idx = len(sources) - 1
        stack = [
            (None, node, "", (idx == last_idx)) for idx, node in enumerate(sources)
        ][::-1]

        from collections import defaultdict
        num_skipped_children = defaultdict(lambda: 0)
        seen_nodes = set()
        while stack:
            parent, node, indent, this_islast = stack.pop()

            if node is not Ellipsis:
                skip = node in seen_nodes
                if skip:
                    num_skipped_children[parent] += 1

                if this_islast:
                    # If we reached the last child of a parent, and we skipped
                    # any of that parents children, then we should emit an
                    # ellipsis at the end after this.
                    if num_skipped_children[parent] and parent is not None:

                        # Append the ellipsis to be emitted last
                        next_islast = True
                        try_frame = (node, Ellipsis, indent, next_islast)
                        stack.append(try_frame)

                        # Redo this frame, but not as a last object
                        next_islast = False
                        try_frame = (parent, node, indent, next_islast)
                        stack.append(try_frame)
                        continue

                if skip:
                    # Mark that we skipped a parent's child
                    continue
                seen_nodes.add(node)

            if not indent:
                # Top level items (i.e. trees in the forest) get different
                # glyphs to indicate they are not actually connected
                if this_islast:
                    this_prefix = indent + glyph_newtree_last
                    next_prefix = indent + glyph_endof_forest
                else:
                    this_prefix = indent + glyph_newtree_mid
                    next_prefix = indent + glyph_within_forest

            else:
                # For individual tree edges distinguish between directed and
                # undirected cases
                if this_islast:
                    this_prefix = indent + glyph_last
                    next_prefix = indent + glyph_endof_forest
                else:
                    this_prefix = indent + glyph_mid
                    next_prefix = indent + glyph_within_tree

            if node is Ellipsis:
                label = " ..."
                suffix = ""
                children = []
            else:
                if with_labels:
                    label = graph.nodes[node].get("label", node)
                else:
                    label = node

                # What can we do to minimize the difference between
                # directed / undirected logic here?
                if is_directed:
                    other_parents = set(pred[node]) - {parent}
                    children = sorted(succ[node])
                else:
                    new_children = [child for child in succ[node] if child not in seen_nodes]
                    neighbors = set(pred[node])
                    other_parents = (neighbors - set(new_children)) - {parent}
                    # Not sure which one to use here:
                    if 0:
                        # The parent was already shown and we are undirected so
                        # exclude the parent from the children (this helps make
                        # graphs for forests nicer)
                        children = sorted(set(succ[node]) - {parent})
                    else:
                        children = new_children

                other_parents_str = ", ".join([str(p) for p in sorted(other_parents)])
                if other_parents:
                    suffix = " ".join(["", glyph_backedge, other_parents_str])
                else:
                    suffix = ""

            # Emit the line for this node
            _write(this_prefix + str(label) + suffix)

            # Push children on the stack in reverse order so they are popped in
            # the original order.
            for idx, child in enumerate(children[::-1]):
                next_islast = idx == 0
                try_frame = (node, child, next_prefix, next_islast)
                stack.append(try_frame)

    if write is None:
        # Only return a string if the custom write function was not specified
        return "\n".join(printbuf)
