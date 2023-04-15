# -*- encoding: utf-8 -*-

import logging
import os
import time
from typing import Callable, List, Tuple

import numpy
import numpy.typing
import osmium
import osmium.io
import osmium.osm
import osmium.osm.mutable

import pyhgtmap.output
from pyhgtmap.hgt.tile import TileContours

logger = logging.getLogger(__name__)

BUFFER_SIZE: int = 4096 * 1024


class Output(pyhgtmap.output.Output):
    """
    PBF output class, based on official osmium.
    Interesting internals:
    - https://github.com/osmcode/pyosmium/blob/master/lib/simple_writer.cc
    - https://github.com/osmcode/libosmium/blob/master/include/osmium/io/detail/pbf_output_format.hpp
    """

    def __init__(
        self,
        filename,
        osmVersion,
        pyhgtmap_version,
        bbox: Tuple[float, float, float, float],
        elevClassifier: Callable[[int], str],
    ):
        self.bbox = bbox
        # SimpleWriter doesn't support overwriting file...
        if os.path.exists(filename):
            os.remove(filename)
        self.osm_writer = osmium.SimpleWriter(
            filename, BUFFER_SIZE, self.makeHeader(pyhgtmap_version)
        )
        # self.outf = open(filename, "wb")
        self.granularity = 100
        self.date_granularity = 1000
        self.elevClassifier = elevClassifier
        self.maxNodesPerNodeBlock = 8000
        self.maxNodesPerWayBlock = 32000
        self.timestamp = int(time.mktime(time.localtime()))
        self.timestampString: str = ""  # dummy attribute, needed by main.py

    def makeHeader(self, pyhgtmap_version) -> osmium.io.Header:
        """Prepare Header object"""
        osm_header = osmium.io.Header()
        left, bottom, right, top = self.bbox
        osm_header.add_box(
            osmium.osm.Box(
                osmium.osm.Location(left, bottom), osmium.osm.Location(right, top)
            )
        )
        osm_header.set(
            key="generator",
            value="pyhgtmap {0:s}".format(pyhgtmap_version),
        )

        return osm_header

    def writeWays(self, ways: List[pyhgtmap.output.WayType], startWayId) -> None:
        """writes ways to self.outf.  ways shall be a list of
        (<startNodeId>, <length>, <isCycle>, <elevation>) tuples.

        The waylist is split up to make sure the pbf blobs will not be too big.
        """
        for ind, way in enumerate(ways):
            closed_loop_id: list[int] = [way.first_node_id] if way.closed_loop else []
            osm_way = osmium.osm.mutable.Way(
                id=startWayId + ind,
                tags=(
                    ("ele", str(way.elevation)),
                    ("contour", "elevation"),
                    ("contour_ext", self.elevClassifier(way.elevation)),
                ),
                nodes=list(range(way.first_node_id, way.first_node_id + way.nb_nodes))
                + closed_loop_id,
            )
            self.osm_writer.add_way(osm_way)

    def flush(self) -> None:
        pass

    def done(self) -> None:
        self.osm_writer.close()

    def writeNodes(
        self,
        tile_contours: TileContours,
        timestamp_string: str,
        start_node_id: int,
        osm_version: float,
    ) -> Tuple[int, List[pyhgtmap.output.WayType]]:
        logger.debug(f"writeNodes - startId: {start_node_id}")

        ways: List[pyhgtmap.output.WayType] = []
        next_node_id: int = start_node_id

        for elevation, contour_list in tile_contours.contours.items():
            # logger.debug(f"writeNodes - elevation: {elevation}")
            # Get all the contours for a given elevation
            if not contour_list:
                continue
            for contour in contour_list:
                # Add the points corresponding to the individual contour, and prepare the way for later step
                is_closed_way: bool = bool(numpy.all(contour[0] == contour[-1]))
                if is_closed_way:
                    # Close way by re-using first node instead of a new one; last node is not needed
                    contour = contour[:-1]
                for node_id, location in zip(
                    range(next_node_id, next_node_id + len(contour)), contour
                ):
                    self.osm_writer.add_node(
                        osmium.osm.mutable.Node(
                            id=node_id,
                            location=(location[0], location[1]),
                        )
                    )

                ways.append(
                    pyhgtmap.output.WayType(
                        next_node_id, len(contour), is_closed_way, elevation
                    )
                )
                # Bump ID for next iteration
                next_node_id += len(contour)

        logger.debug(f"writeNodes - next_node_id: {next_node_id}")
        return next_node_id, ways
