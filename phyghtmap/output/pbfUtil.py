# -*- encoding: utf-8 -*-

__author__ = "Adrian Dempwolff (phyghtmap@aldw.de)"
__version__ = "2.23"
__copyright__ = "Copyright (c) 2009-2021 Adrian Dempwolff"
__license__ = "GPLv2+"

import logging
import os
import time

from typing import Iterable, List, Tuple

import osmium
import osmium.osm
import osmium.io
import osmium.osm.mutable
import phyghtmap.output
from phyghtmap import contour
from phyghtmap.varint import writableString

logger = logging.getLogger(__name__)

BUFFER_SIZE = 4096 * 1024


class Output(phyghtmap.output.Output):
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
        phyghtmapVersion,
        bbox: List[float],
        elevClassifier,
    ):
        self.bbox = bbox
        # SimpleWriter doesn't support overwriting file...
        if os.path.exists(filename):
            os.remove(filename)
        self.osm_writer = osmium.SimpleWriter(
            filename, BUFFER_SIZE, self.makeHeader(phyghtmapVersion)
        )
        # self.outf = open(filename, "wb")
        self.granularity = 100
        self.date_granularity = 1000
        self.elevClassifier = elevClassifier
        self.maxNodesPerNodeBlock = 8000
        self.maxNodesPerWayBlock = 32000
        self.timestamp = int(time.mktime(time.localtime()))
        self.timestampString = writableString("")  # dummy attribute, needed by main.py

    def makeHeader(self, phyghtmapVersion) -> osmium.io.Header:
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
            value="phyghtmap {0:s}".format(phyghtmapVersion),
        )

        return osm_header

    def writeWays(self, ways: List[phyghtmap.output.WayType], startWayId) -> None:
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

    def build_osm_ways(
        self,
        contour_data: contour.ContourObject,
        elevations: Iterable[int],
        start_node_id: int,
    ) -> Tuple[
        List[List[osmium.osm.mutable.Node]], List[phyghtmap.output.WayType], int
    ]:
        ways: List[phyghtmap.output.WayType] = []
        all_nodes: List[List[osmium.osm.mutable.Node]] = []
        next_node_id: int = start_node_id
        for elevation in elevations:
            # logger.debug(f"writeNodes - elevation: {elevation}")
            contour_list = contour_data.trace(elevation)[0]
            if not contour_list:
                continue
            for contour in contour_list:
                nodes = [
                    osmium.osm.mutable.Node(
                        id=node_id,
                        location=osmium.osm.Location(location[0], location[1]),
                    )
                    for node_id, location in zip(
                        range(next_node_id, next_node_id + len(contour)), contour
                    )
                ]
                closed_way_ids: List[int] = []
                closed_way: bool = False
                assert nodes[0].id
                if nodes[0].location == nodes[-1].location:
                    # Close way by re-using first node instead of a new one
                    # closed_way_ids = [nodes[0].id]
                    closed_way = True
                    del nodes[-1]
                # way = osmium.osm.mutable.Way(id=nodes[0].id, nodes=[node.id for node in nodes if node.id]+closed_way_ids)
                ways.append(
                    phyghtmap.output.WayType(
                        nodes[0].id, len(nodes), closed_way, elevation
                    )
                )
                # Bump ID for next iteration
                next_node_id += len(nodes)
                all_nodes.append(nodes)
        return all_nodes, ways, next_node_id

    def writeNodes(
        self,
        contour_data: contour.ContourObject,
        elevations: Iterable[int],
        timestamp_string: str,
        start_node_id: int,
        osm_version: float,
    ) -> Tuple[int, List[phyghtmap.output.WayType]]:
        IDCounter = phyghtmap.output.Id(start_node_id)
        logger.debug(f"writeNodes - startId: {start_node_id}")
        all_nodes, ways, newId = self.build_osm_ways(
            contour_data, elevations, start_node_id
        )
        for nodes in all_nodes:
            for node in nodes:
                self.osm_writer.add_node(node)
        logger.debug(f"writeNodes - newId: {newId}")
        return newId, ways
