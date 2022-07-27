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
        >>> from cmd_queue.util.util_algo import balanced_number_partitioning
        >>> items = np.array([1, 3, 29, 22, 4, 5, 9])
        >>> num_parts = 3
        >>> bin_assignments = balanced_number_partitioning(items, num_parts)
        >>> # xdoctest: +REQUIRES(module:kwarray)
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
