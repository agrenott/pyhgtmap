import logging
from typing import Any, Callable, List, NamedTuple, Tuple

import numpy
from nptyping import NDArray, Structure

from pyhgtmap.hgt.tile import TileContours

logger = logging.getLogger(__name__)

# First node ID, number of nodes, closed loop, elevation
WayType = NamedTuple(
    "WayType",
    [
        ("first_node_id", int),
        ("nb_nodes", int),
        ("closed_loop", bool),
        ("elevation", int),
    ],
)

# Efficient representation of many ways (array of 4-tuple, similar to a list of WayType)
WaysType = NDArray[
    Any,
    Structure["first_node_id: Int, nb_nodes: Int, closed_loop: Bool, elevation: Int"],
]

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
        self.timestampString: str
        self.ways_pending_write: List[Tuple[WaysType, int]] = []

    def write_nodes(
        self,
        tile_contours: TileContours,
        timestamp_string: str,
        start_node_id: int,
        osm_version: float,
    ) -> Tuple[int, WaysType]:
        """
        Write nodes and prepare associated ways.
        Return (latest_node_id, [ways]) tuple.
        """
        raise NotImplementedError

    def write_ways(self, ways: WaysType, start_way_id: int) -> None:
        """
        Add ways previously prepared by write_nodes to be written later
        (as ways should ideally be written after all nodes).
        """
        self.ways_pending_write.append((ways, start_way_id))

    def _write_ways(self, ways: WaysType, start_way_id: int) -> None:
        """Actually write ways, upon output finalization via done()."""
        raise NotImplementedError

    def done(self) -> None:
        """Finalize and close file."""
        logger.debug(
            "done() - Writing %s pending ways",
            sum([len(x[0]) for x in self.ways_pending_write]),
        )
        for ways, start_way_id in self.ways_pending_write:
            self._write_ways(ways, start_way_id)
        logger.debug("done() - done!")

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
            ways.append(WayType(nodeRefs[0], len(nodeRefs) - 1, True, elevation))
        else:
            ways.append(WayType(nodeRefs[0], len(nodeRefs), False, elevation))
    return nodes, ways


def build_efficient_ways(ways: List[WayType]) -> WaysType:
    """Convert a list of ways (tuples) into a more efficient numpy array."""
    return numpy.array(
        ways,
        dtype=numpy.dtype(
            [
                ("first_node_id", int),
                ("nb_nodes", int),
                ("closed_loop", bool),
                ("elevation", int),
            ]
        ),
    )  # type: ignore  # not supported by pylance
