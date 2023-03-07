from typing import Callable, Iterable, List, Tuple

import numpy

from phyghtmap import contour

# First node ID, number of nodes, closed loop, elevation
WayType = Tuple[int, int, bool, int]

NodeType = Tuple[int, int]


def make_elev_classifier(majorDivisor: int, mediumDivisor: int) -> Callable[[int], str]:
    """returns a function taking an elevation and returning a
    category specifying whether it's a major, medium or minor contour.
    """

    def classify(height: int) -> str:
        if height % majorDivisor == 0:
            return "elevation_major"
        elif height % mediumDivisor == 0:
            return "elevation_medium"
        else:
            return "elevation_minor"

    return classify


class Output:
    """Base class for all output modules."""

    def __init__(self) -> None:
        pass

    def writeNodes(
        self,
        contour_data: contour.ContourObject,
        elevations: Iterable[int],
        timestamp_string: str,
        start_node_id: int,
        osm_version: float,
    ) -> Tuple[int, List[WayType]]:
        """
        Write nodes and prepare associated ways.
        Return (latest_node_id, [ways]) tuple.
        """
        raise NotImplementedError

    def writeWays(self, ways: List[WayType], start_way_id: int) -> None:
        """Write ways previously prepared by writeNodes."""
        raise NotImplementedError

    def done(self) -> None:
        """Finalize and close file."""
        raise NotImplementedError

    def flush(self) -> None:
        """Flush file to disk."""
        raise NotImplementedError


class Id(object):
    """a counter, constructed with the first number to return.

    Count using the getId method.
    """

    def __init__(self, offset: int) -> None:
        self.curId: int = offset

    def getId(self) -> int:
        self.curId += 1
        return self.curId - 1


# Helper functions
def _makePoints(path, IDCounter, precision: int) -> Tuple[List[NodeType], List[int]]:
    ids, nodes = [], []
    for lon, lat in path:
        IDCounter.curId += 1
        nodes.append((int(lon * precision), int(lat * precision)))
        ids.append(IDCounter.curId - 1)
    if numpy.all(path[0] == path[-1]):  # close contour
        del nodes[-1]  # remove last node
        del ids[-1]
        ids.append(ids[0])
        IDCounter.curId -= 1
    return nodes, ids


def make_nodes_ways(
    contourList: List, elevation: int, IDCounter, precision: int
) -> Tuple[List, List[WayType]]:
    ways: List[WayType] = []
    nodes: List = []
    for path in contourList:
        newNodes, nodeRefs = _makePoints(path, IDCounter, precision)
        nodes.extend(newNodes)
        if nodeRefs[0] == nodeRefs[-1]:
            ways.append((nodeRefs[0], len(nodeRefs) - 1, True, elevation))
        else:
            ways.append((nodeRefs[0], len(nodeRefs), False, elevation))
    return nodes, ways
