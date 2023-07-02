import sys
from collections import defaultdict
import networkx as nx
from networkx.utils import open_file


### See: https://github.com/networkx/networkx/pull/5602


class AsciiBaseGlyphs:
    empty = "+"
    newtree_last = "+-- "
    newtree_mid = "+-- "
    endof_forest = "    "
    within_forest = ":   "
    within_tree = "|   "


class AsciiDirectedGlyphs(AsciiBaseGlyphs):
    last = "L-> "
    mid = "|-> "
    backedge = "<-"
    # vertical_edge = 'v'
    vertical_edge = '!'


class AsciiUndirectedGlyphs(AsciiBaseGlyphs):
    last = "L-- "
    mid = "|-- "
    backedge = "-"
    vertical_edge = '|'


class UtfBaseGlyphs:
    # Notes on available box and arrow characters
    # https://en.wikipedia.org/wiki/Box-drawing_character
    # https://stackoverflow.com/questions/2701192/triangle-arrow
    empty = "╙"
    newtree_last = "╙── "
    newtree_mid = "╟── "
    endof_forest = "    "
    within_forest = "╎   "
    within_tree = "│   "


class UtfDirectedGlyphs(UtfBaseGlyphs):
    last = "└─╼ "
    mid = "├─╼ "
    backedge = "╾"
    vertical_edge = '╽'


class UtfUndirectedGlyphs(UtfBaseGlyphs):
    last = "└── "
    mid = "├── "
    backedge = "─"
    vertical_edge = '│'


def generate_network_text(
    graph, with_labels=True, sources=None, max_depth=None, ascii_only=False,
    vertical_chains=False,
):
    """Generate lines in the "network text" format

    This works via a depth-first traversal of the graph and writing a line for
    each unique node encountered. Non-tree edges are written to the right of
    each node, and connection to a non-tree edge is indicated with an ellipsis.
    This representation works best when the input graph is a forest, but any
    graph can be represented.

    This notation is original to networkx, although it is simple enough that it
    may be known in existing literature. See #5602 for details. The procedure
    is summarized as follows:

    1. Given a set of source nodes (which can be specified, or automatically
    discovered via finding the (strongly) connected components and choosing one
    node with minimum degree from each), we traverse the graph in depth first
    order.

    2. Each reachable node will be printed exactly once on it's own line.

    3. Edges are indicated in one of three ways:

        a. a parent "L-style" connection on the upper left. This corresponds to
        a traversal in the directed DFS tree.

        b. a backref "<-style" connection shown directly on the right. For
        directed graphs, these are drawn for any incoming edges to a node that
        is not a parent edge. For undirected graphs, these are drawn for only
        the non-parent edges that have already been represented (The edges that
        have not been represented will be handled in the recursive case).

        c. a child "L-style" connection on the lower right. Drawing of the
        children are handled recursively.

    4. The children of each node (wrt the directed DFS tree) are drawn
    underneath and to the right of it. In the case that a child node has already
    been drawn the connection is replaced with an ellipsis ("...") to indicate
    that there is one or more connections represented elsewhere.

    5. If a maximum depth is specified, an edge to nodes past this maximum
    depth will be represented by an ellipsis.

    Parameters
    ----------
    graph : nx.DiGraph | nx.Graph
        Graph to represent

    with_labels : bool | str
        If True will use the "label" attribute of a node to display if it
        exists otherwise it will use the node value itself. If given as a
        string, then that attribte name will be used instead of "label".
        Defaults to True.

    sources : List
        Specifies which nodes to start traversal from. Note: nodes that are not
        reachable from one of these sources may not be shown. If unspecified,
        the minimal set of nodes needed to reach all others will be used.

    max_depth : int | None
        The maximum depth to traverse before stopping. Defaults to None.

    ascii_only : Boolean
        If True only ASCII characters are used to construct the visualization

    vertical_chains : Boolean
        If True, chains of nodes will be drawn vertically when possible.

    Yields
    ------
    str : a line of generated text

    Example:
        >>> graph = nx.path_graph(10)
        >>> graph.add_node('A')
        >>> graph.add_node('B')
        >>> graph.add_node('C')
        >>> graph.add_node('D')
        >>> graph.add_edge(9, 'A')
        >>> graph.add_edge(9, 'B')
        >>> graph.add_edge(9, 'C')
        >>> graph.add_edge('C', 'D')
        >>> graph.add_edge('C', 'E')
        >>> graph.add_edge('C', 'F')
        >>> write_network_text(graph)
        ╙── 0
            └── 1
                └── 2
                    └── 3
                        └── 4
                            └── 5
                                └── 6
                                    └── 7
                                        └── 8
                                            └── 9
                                                ├── A
                                                ├── B
                                                └── C
                                                    ├── D
                                                    ├── E
                                                    └── F
        >>> write_network_text(graph, vertical_chains=True)
        ╙── 0
            │
            1
            │
            2
            │
            3
            │
            4
            │
            5
            │
            6
            │
            7
            │
            8
            │
            9
            ├── A
            ├── B
            └── C
                ├── D
                ├── E
                └── F
    """
    from typing import Any
    from typing import NamedTuple

    class StackFrame(NamedTuple):
        parent: Any
        node: Any
        indents: list
        this_islast: bool
        this_vertical: bool

    collapse_attr = "collapse"

    is_directed = graph.is_directed()

    if is_directed:
        glyphs = AsciiDirectedGlyphs if ascii_only else UtfDirectedGlyphs
        succ = graph.succ
        pred = graph.pred
    else:
        glyphs = AsciiUndirectedGlyphs if ascii_only else UtfUndirectedGlyphs
        succ = graph.adj
        pred = graph.adj

    if isinstance(with_labels, str):
        label_attr = with_labels
    elif with_labels:
        label_attr = "label"
    else:
        label_attr = None

    if max_depth == 0:
        yield glyphs.empty + " ..."
    elif len(graph.nodes) == 0:
        yield glyphs.empty
    else:

        # If the nodes to traverse are unspecified, find the minimal set of
        # nodes that will reach the entire graph
        if sources is None:
            sources = _find_sources(graph)

        # Populate the stack with each:
        # 1. parent node in the DFS tree (or None for root nodes),
        # 2. the current node in the DFS tree
        # 2. a list of indentations indicating depth
        # 3. a flag indicating if the node is the final one to be written.
        # Reverse the stack so sources are popped in the correct order.
        last_idx = len(sources) - 1
        stack = [
            StackFrame(None, node, [], (idx == last_idx), False)
            for idx, node in enumerate(sources)
        ][::-1]

        num_skipped_children = defaultdict(lambda: 0)
        seen_nodes = set()
        while stack:
            parent, node, indents, this_islast, this_vertical = stack.pop()

            if node is not Ellipsis:
                skip = node in seen_nodes
                if skip:
                    # Mark that we skipped a parent's child
                    num_skipped_children[parent] += 1

                if this_islast:
                    # If we reached the last child of a parent, and we skipped
                    # any of that parents children, then we should emit an
                    # ellipsis at the end after this.
                    if num_skipped_children[parent] and parent is not None:

                        # Append the ellipsis to be emitted last
                        next_islast = True
                        try_frame = StackFrame(node, Ellipsis, indents, next_islast, False)
                        stack.append(try_frame)

                        # Redo this frame, but not as a last object
                        next_islast = False
                        try_frame = StackFrame(parent, node, indents, next_islast, this_vertical)
                        stack.append(try_frame)
                        continue

                if skip:
                    continue
                seen_nodes.add(node)

            if not indents:
                # Top level items (i.e. trees in the forest) get different
                # glyphs to indicate they are not actually connected
                if this_islast:
                    this_vertical = False
                    this_prefix = indents + [glyphs.newtree_last]
                    next_prefix = indents + [glyphs.endof_forest]
                else:
                    this_prefix = indents + [glyphs.newtree_mid]
                    next_prefix = indents + [glyphs.within_forest]

            else:
                # Non-top-level items
                if this_vertical:
                    this_prefix = indents
                    next_prefix = indents
                else:
                    if this_islast:
                        this_prefix = indents + [glyphs.last]
                        next_prefix = indents + [glyphs.endof_forest]
                    else:
                        this_prefix = indents + [glyphs.mid]
                        next_prefix = indents + [glyphs.within_tree]

            if node is Ellipsis:
                label = " ..."
                suffix = ""
                children = []
            else:
                if label_attr is not None:
                    label = str(graph.nodes[node].get(label_attr, node))
                else:
                    label = str(node)

                # Determine if we want to show the children of this node.
                if collapse_attr is not None:
                    collapse = graph.nodes[node].get(collapse_attr, False)
                else:
                    collapse = False

                # Determine:
                # (1) children to traverse into after showing this node.
                # (2) parents to immediately show to the right of this node.
                if is_directed:
                    # In the directed case we must show every successor node
                    # note: it may be skipped later, but we don't have that
                    # information here.
                    children = list(succ[node])
                    # In the directed case we must show every predecessor
                    # except for parent we directly traversed from.
                    handled_parents = {parent}
                else:
                    # Showing only the unseen children results in a more
                    # concise representation for the undirected case.
                    children = [
                        child for child in succ[node] if child not in seen_nodes
                    ]

                    # In the undirected case, parents are also children, so we
                    # only need to immediately show the ones we can no longer
                    # traverse
                    handled_parents = {*children, parent}

                if max_depth is not None and len(indents) == max_depth - 1:
                    # Use ellipsis to indicate we have reached maximum depth
                    if children:
                        children = [Ellipsis]
                    handled_parents = {parent}

                if collapse:
                    # Collapsing a node is the same as reaching maximum depth
                    if children:
                        children = [Ellipsis]
                    handled_parents = {parent}

                # The other parents are other predecessors of this node that
                # are not handled elsewhere.
                other_parents = [p for p in pred[node] if p not in handled_parents]
                if other_parents:
                    if label_attr is not None:
                        other_parents_labels = ", ".join(
                            [
                                str(graph.nodes[p].get(label_attr, p))
                                for p in other_parents
                            ]
                        )
                    else:
                        other_parents_labels = ", ".join(
                            [str(p) for p in other_parents]
                        )
                    suffix = " ".join(["", glyphs.backedge, other_parents_labels])
                else:
                    suffix = ""

            # Emit the line for this node, this will be called for each node
            # exactly once.
            # print(f'this_prefix={this_prefix}')
            # print(f'this_islast={this_islast}')
            if this_vertical:
                yield "".join(this_prefix + [glyphs.vertical_edge])

            yield "".join(this_prefix + [label, suffix])

            # TODO: Can we determine if we are an only child?
            if vertical_chains:
                if is_directed:
                    num_children = len(set(children))
                else:
                    num_children = len(set(children) - {parent})
                # Only can draw the next node vertically if it is the only
                # remaining child of this node.
                next_is_vertical = num_children == 1
            else:
                next_is_vertical = False

            # Push children on the stack in reverse order so they are popped in
            # the original order.
            for idx, child in enumerate(children[::-1]):
                next_islast = idx == 0
                try_frame = StackFrame(node, child, next_prefix, next_islast, next_is_vertical)
                stack.append(try_frame)


@open_file(1, "w")
def write_network_text(
    graph,
    path=None,
    with_labels=True,
    sources=None,
    max_depth=None,
    ascii_only=False,
    end="\n",
    vertical_chains=False
):
    """Creates a nice text representation of a graph

    This works via a depth-first traversal of the graph and writing a line for
    each unique node encountered. Non-tree edges are written to the right of
    each node, and connection to a non-tree edge is indicated with an ellipsis.
    This representation works best when the input graph is a forest, but any
    graph can be represented.

    Parameters
    ----------
    graph : nx.DiGraph | nx.Graph
        Graph to represent

    path : string or file or callable or None
       Filename or file handle for data output.
       if a function, then it will be called for each generated line.
       if None, this will default to "sys.stdout.write"

    with_labels : bool | str
        If True will use the "label" attribute of a node to display if it
        exists otherwise it will use the node value itself. If given as a
        string, then that attribte name will be used instead of "label".
        Defaults to True.

    sources : List
        Specifies which nodes to start traversal from. Note: nodes that are not
        reachable from one of these sources may not be shown. If unspecified,
        the minimal set of nodes needed to reach all others will be used.

    max_depth : int | None
        The maximum depth to traverse before stopping. Defaults to None.

    ascii_only : Boolean
        If True only ASCII characters are used to construct the visualization

    end : string
        The line ending characater

    vertical_chains : Boolean
        If True, chains of nodes will be drawn vertically when possible.

    Example
    -------
    >>> graph = nx.balanced_tree(r=2, h=2, create_using=nx.DiGraph)
    >>> write_network_text(graph)
    ╙── 0
        ├─╼ 1
        │   ├─╼ 3
        │   └─╼ 4
        └─╼ 2
            ├─╼ 5
            └─╼ 6

    >>> # A near tree with one non-tree edge
    >>> graph.add_edge(5, 1)
    >>> write_network_text(graph)
    ╙── 0
        ├─╼ 1 ╾ 5
        │   ├─╼ 3
        │   └─╼ 4
        └─╼ 2
            ├─╼ 5
            │   └─╼  ...
            └─╼ 6

    >>> graph = nx.cycle_graph(5)
    >>> write_network_text(graph)
    ╙── 0
        ├── 1
        │   └── 2
        │       └── 3
        │           └── 4 ─ 0
        └──  ...

    >>> graph = nx.cycle_graph(5, nx.DiGraph)
    >>> write_network_text(graph, vertical_chains=True)
    ╙── 0 ╾ 4
        ╽
        1
        ╽
        2
        ╽
        3
        ╽
        4
        └─╼  ...

    >>> write_network_text(graph, vertical_chains=True, ascii_only=True)
    +-- 0 <- 4
        v
        1
        v
        2
        v
        3
        v
        4
        L->  ...

    >>> graph = nx.generators.barbell_graph(4, 2)
    >>> write_network_text(graph, vertical_chains=False)
    ╙── 4
        ├── 5
        │   └── 6
        │       ├── 7
        │       │   ├── 8 ─ 6
        │       │   │   └── 9 ─ 6, 7
        │       │   └──  ...
        │       └──  ...
        └── 3
            ├── 0
            │   ├── 1 ─ 3
            │   │   └── 2 ─ 0, 3
            │   └──  ...
            └──  ...
    >>> write_network_text(graph, vertical_chains=True)
    ╙── 4
        ├── 5
        │   │
        │   6
        │   ├── 7
        │   │   ├── 8 ─ 6
        │   │   │   │
        │   │   │   9 ─ 6, 7
        │   │   └──  ...
        │   └──  ...
        └── 3
            ├── 0
            │   ├── 1 ─ 3
            │   │   │
            │   │   2 ─ 0, 3
            │   └──  ...
            └──  ...

    >>> graph = nx.complete_graph(5, create_using=nx.Graph)
    >>> write_network_text(graph)
    ╙── 0
        ├── 1
        │   ├── 2 ─ 0
        │   │   ├── 3 ─ 0, 1
        │   │   │   └── 4 ─ 0, 1, 2
        │   │   └──  ...
        │   └──  ...
        └──  ...

    >>> graph = nx.complete_graph(3, create_using=nx.DiGraph)
    >>> write_network_text(graph)
    ╙── 0 ╾ 1, 2
        ├─╼ 1 ╾ 2
        │   ├─╼ 2 ╾ 0
        │   │   └─╼  ...
        │   └─╼  ...
        └─╼  ...
    """
    if path is None:
        # The path is unspecified, write to stdout
        _write = sys.stdout.write
    elif hasattr(path, "write"):
        # The path is already an open file
        _write = path.write
    elif callable(path):
        # The path is a custom callable
        _write = path
    else:
        raise TypeError(type(path))

    for line in generate_network_text(
        graph,
        with_labels=with_labels,
        sources=sources,
        max_depth=max_depth,
        ascii_only=ascii_only,
        vertical_chains=vertical_chains,
    ):
        _write(line + end)


def _find_sources(graph):
    """
    Determine a minimal set of nodes such that the entire graph is reachable
    """
    # For each connected part of the graph, choose at least
    # one node as a starting point, preferably without a parent
    if graph.is_directed():
        # Choose one node from each SCC with minimum in_degree
        sccs = list(nx.strongly_connected_components(graph))
        # condensing the SCCs forms a dag, the nodes in this graph with
        # 0 in-degree correspond to the SCCs from which the minimum set
        # of nodes from which all other nodes can be reached.
        scc_graph = nx.condensation(graph, sccs)
        supernode_to_nodes = {sn: [] for sn in scc_graph.nodes()}
        # Note: the order of mapping differs between pypy and cpython
        # so we have to loop over graph nodes for consistency
        mapping = scc_graph.graph["mapping"]
        for n in graph.nodes:
            sn = mapping[n]
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
    return sources


def graph_str(graph, with_labels=True, sources=None, write=None, ascii_only=False):
    """Creates a nice utf8 representation of a forest

    This function has been superseded by
    :func:`nx.readwrite.text.generate_network_text`, which should be used
    instead.

    Parameters
    ----------
    graph : nx.DiGraph | nx.Graph
        Graph to represent (must be a tree, forest, or the empty graph)

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
    >>> graph = nx.balanced_tree(r=2, h=3, create_using=nx.DiGraph)
    >>> print(graph_str(graph))
    ╙── 0
        ├─╼ 1
        │   ├─╼ 3
        │   │   ├─╼ 7
        │   │   └─╼ 8
        │   └─╼ 4
        │       ├─╼ 9
        │       └─╼ 10
        └─╼ 2
            ├─╼ 5
            │   ├─╼ 11
            │   └─╼ 12
            └─╼ 6
                ├─╼ 13
                └─╼ 14


    >>> graph = nx.balanced_tree(r=1, h=2, create_using=nx.Graph)
    >>> print(graph_str(graph))
    ╙── 0
        └── 1
            └── 2

    >>> print(graph_str(graph, ascii_only=True))
    +-- 0
        L-- 1
            L-- 2
    """
    printbuf = []
    if write is None:
        _write = printbuf.append
    else:
        _write = write

    write_network_text(
        graph,
        _write,
        with_labels=with_labels,
        sources=sources,
        ascii_only=ascii_only,
        end="",
    )

    if write is None:
        # Only return a string if the custom write function was not specified
        return "\n".join(printbuf)


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


def parse_network_text(lines):
    """
    Simple tool to reconstruct a graph from a network text representation.
    This is mainly used for testing. Network text is for display, not
    serialization... but if you're in a pinch...

    Example:
        >>> import sys, ubelt
        >>> sys.path.append(ubelt.expandpath('~/code/cmd_queue'))
        >>> from cmd_queue.util.util_networkx import *  # NOQA
        >>> import networkx as nx
        >>> graph = nx.erdos_renyi_graph(10, 0.3, directed=0, seed=3433)
        >>> graph = nx.relabel_nodes(graph, {n: str(n) for n in graph.nodes})
        >>> lines = list(generate_network_text(graph, vertical_chains=False))
        >>> print(chr(10).join(lines))
        >>> write_network_text(graph)
        >>> new = parse_network_text(lines)
        >>> write_network_text(new)
        >>> #write_network_text(new, vertical_chains=False)
        >>> assert new.nodes == graph.nodes
        >>> assert new.edges == graph.edges
        graph = nx.erdos_renyi_graph(10, 0.3, directed=True, seed=3433)

    Ignore:

        def test_round_trip(graph):
            graph = nx.relabel_nodes(graph, {n: str(n) for n in graph.nodes})
            lines = list(generate_network_text(graph, vertical_chains=False))
            print(chr(10).join(lines))
            new = parse_network_text(lines)
            assert new.nodes == graph.nodes
            assert new.edges == graph.edges

        for directed in [0, 1]:
            cls = nx.DiGraph if directed else nx.Graph

            num_randomized = 3

            # Disconnected graphs
            for num_nodes in range(0, 20):
                # 1-Node
                graph = cls()
                graph.add_nodes_from(range(1, num_nodes + 1))
                test_round_trip(graph)

                for p in [0.1, 0.2, 0.3, 0.6, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:

                    for seed in range(num_randomized):
                        graph = nx.erdos_renyi_graph(num_nodes, p, directed=directed, seed=seed + int(1000 * p))
                        test_round_trip(graph)
    """
    from collections import deque
    from itertools import chain
    import ubelt as ub
    lines = list(lines)
    initial_line_iter = iter(lines)

    is_ascii = None
    is_directed = None

    ##############
    # Initial Pass
    ##############

    # Do an initial pass over the lines to determine what type of graph it is.
    # Remember what these lines were, so we can reiterate over them in the
    # parsing pass.
    initial_lines = []
    try:
        first_line = next(initial_line_iter)
    except StopIteration:
        ...
    else:
        # The first character indicates if it is an ASCII or UTF graph
        initial_lines.append(first_line)
        first_char = first_line[0]
        if first_char in {UtfBaseGlyphs.empty, UtfBaseGlyphs.newtree_mid[0], UtfBaseGlyphs.newtree_last[0]}:
            is_ascii = False
        elif first_char in {AsciiBaseGlyphs.empty, AsciiBaseGlyphs.newtree_mid[0], AsciiBaseGlyphs.newtree_last[0]}:
            is_ascii = True
        else:
            raise AssertionError(f'Unexpected first character: {first_char}')

    if is_ascii:
        directed_glyphs = AsciiDirectedGlyphs
        undirected_glyphs = AsciiUndirectedGlyphs
    else:
        directed_glyphs = UtfDirectedGlyphs
        undirected_glyphs = UtfUndirectedGlyphs

    directed_glphys_lut = {a: getattr(directed_glyphs, a) for a in dir(directed_glyphs) if not a.startswith('_')}
    undirected_glphys_lut = {a: getattr(undirected_glyphs, a) for a in dir(undirected_glyphs) if not a.startswith('_')}

    directed_symbols = set.union(*map(set, directed_glphys_lut.values()))
    undirected_symbols = set.union(*map(set, undirected_glphys_lut.values()))
    directed_only_symbols = directed_symbols - undirected_symbols
    undirected_only_symbols = undirected_symbols - directed_symbols

    for line in initial_line_iter:
        initial_lines.append(line)
        if set(line) & directed_only_symbols:
            is_directed = True
            break
        elif set(line) & undirected_only_symbols:
            is_directed = False
            break

    if is_directed is None:
        # Not enough information to determine, choose undirected by default
        is_directed = False

    if is_directed:
        glyphs_lut = directed_glphys_lut
    else:
        glyphs_lut = undirected_glphys_lut

    # backedge_delimiters = [f' {c} ' for c in possibglyphs['backedge']]
    edges = []
    nodes = []

    print_ = ub.identity

    # TODO: keep a stack of the parents to parse things out
    noparent = object()
    stack = deque([{'node': noparent, 'indent': -1}])

    ##############
    # Parsing Pass
    ##############

    parsing_line_iter = chain(initial_lines, initial_line_iter)

    backedge = ' ' + glyphs_lut['backedge'] + ' '

    is_empty = None

    for line in parsing_line_iter:
        print_('------------')
        print_(f'line={line!r}')

        # Determine if there is a backedge
        has_backedge = backedge in line

        if line == glyphs_lut['empty']:
            is_empty = True
            continue
        # Parse which node this line is referring to.
        elif has_backedge:
            lhs, rhs = line.split(backedge)
            rhs_incoming = rhs.split(', ')
            lhs = lhs.rstrip()
            prenode, node = lhs.rsplit(' ', 1)
            node = node.strip()
            edges.extend([(u.strip(), node) for u in rhs_incoming])
        else:
            prenode, node = line.rsplit(' ', 1)
            node = node.strip()
        prenode = prenode.rstrip()

        indent = len(prenode.rstrip())
        # prenode.count(glyphs.within_tree.strip()) + prenode.count(glyphs.mid.strip()) + prenode.count(glyphs.last.strip())

        prev = stack.pop()
        while indent <= prev['indent']:
            print_('popping')
            prev = stack.pop()

        curr = {
            'node': node,
            'indent': indent,
        }
        print_(f'node={node!r}')
        print_('prenode = {}'.format(ub.urepr(prenode, nl=1)))
        print_(f'prev={prev!r}')
        print_(f'curr={curr!r}')

        if node in glyphs_lut['vertical_edge']:
            # Previous node is still the previous node, just skip this line
            # TODO: change indent state
            stack.append(prev)
        elif node == '...':
            # The current previous node is no longer a valid parent,
            # keep it popped from the stack.
            stack.append(prev)
        else:
            stack.append(prev)
            stack.append(curr)

            # New node
            nodes.append(node)

            if prev['node'] is not noparent:
                edges.append((prev['node'], curr['node']))
        print_('------------')

    if is_empty:
        # Double check that if we parsed the empty symbol
        # we are actually empty.
        assert len(nodes) == 0

    cls = nx.DiGraph if is_directed else nx.Graph

    print_('nodes = {}'.format(ub.urepr(nodes, nl=1)))
    print_('edges = {}'.format(ub.urepr(edges, nl=1)))
    new = cls()
    new.add_nodes_from(nodes)
    new.add_edges_from(edges)
    return new
