from __future__ import annotations

import datetime
import time
from typing import TYPE_CHECKING, Callable

import numpy

import pyhgtmap.output
from pyhgtmap.varint import writableString

if TYPE_CHECKING:
    from io import IOBase

    from pyhgtmap.hgt.tile import TileContours


def makeUtcTimestamp():
    return (
        datetime.datetime.utcfromtimestamp(time.mktime(time.localtime())).isoformat()
        + "Z"
    )


class Output(pyhgtmap.output.Output):
    """An OSM output.

    It is constructed with a destination name, the desired OSM API version,
    the version of pyhgtmap as string, an already formatted OSM XML bounds tag
    as output by the hgt.makeBoundsString() function,	an integer representing
    the gzip compressionlevel (or 0 if no gzip compression is desired),
    an elevation classifying function as returned by makeElevClassifier()
    and a hint weather to write timestamps to output or not.
    """

    def __init__(
        self,
        fName: str,
        osmVersion: float,
        pyhgtmap_version: str,
        boundsTag: str,
        gzip: int,
        elevClassifier: Callable[[int], str],
        timestamp=False,
    ) -> None:
        super().__init__()
        self.outF: IOBase
        if 0 < gzip < 10:
            import gzip as Gzip

            self.outF = Gzip.open(fName, "wb", gzip)
        else:
            self.outF = open(fName, "wb")  # noqa: SIM115 # TODO: use context handler
        self.osmVersion = f"{osmVersion:.1f}"
        if osmVersion > 0.5:
            self.versionString = ' version="1"'
        else:
            self.versionString = ""
        if timestamp:
            self.timestampString = f' timestamp="{makeUtcTimestamp():s}"'
        else:
            self.timestampString = ""
        self.elevClassifier = elevClassifier
        self.pyhgtmap_version = pyhgtmap_version
        self.boundsTag = boundsTag
        self._writePreamble()

    def _writePreamble(self):
        self.write('<?xml version="1.0" encoding="utf-8"?>\n')
        self.write(
            f'<osm version="{self.osmVersion:s}" generator="pyhgtmap {self.pyhgtmap_version:s}">\n',
        )
        self.write(self.boundsTag + "\n")

    def done(self) -> None:
        super().done()
        self.write("</osm>\n")
        self.outF.close()

    def write(self, output):
        self.outF.write(writableString(output))

    def flush(self) -> None:
        self.outF.flush()

    def _write_ways(self, ways: pyhgtmap.output.WaysType, startWayId):
        IDCounter = pyhgtmap.output.Id(startWayId)
        for startNodeId, length, isCycle, elevation in ways:
            IDCounter.curId += 1
            nodeIds = list(range(startNodeId, startNodeId + length))
            if isCycle:
                nodeIds.append(nodeIds[0])
            nodeRefs = ('<nd ref="{:d}"/>\n' * len(nodeIds)).format(*nodeIds)
            self.write(
                f'<way id="{IDCounter.curId - 1:d}"{self.versionString:s}{self.timestampString:s}>{nodeRefs:s}'
                f'<tag k="ele" v="{elevation:d}"/>'
                '<tag k="contour" v="elevation"/>'
                f'<tag k="contour_ext" v="{self.elevClassifier(elevation):s}"/>'
                "</way>\n",
            )

    def write_nodes(
        self,
        tile_contours: TileContours,
        timestamp_string: str,
        start_node_id: int,
        osm_version: float,
    ) -> tuple[int, pyhgtmap.output.WaysType]:
        return writeXML(
            self,
            tile_contours,
            timestamp_string,
            start_node_id,
            osm_version,
        )


def _makePoints(output, path, IDCounter, versionString, timestampString):
    """writes OSM representations of the points making up a path to
    output.

    It returns a list of the node ids included in this path.
    """
    ids, content = [], []
    for lon, lat in path:
        IDCounter.curId += 1
        content.append(
            f'<node id="{IDCounter.curId - 1:d}" lat="{lat:.7f}" lon="{lon:.7f}"{versionString:s}{timestampString:s}/>',
        )
        ids.append(IDCounter.curId - 1)
    if numpy.all(path[0] == path[-1]):  # close contour
        del content[-1]  # remove last node
        del ids[-1]
        ids.append(ids[0])
        IDCounter.curId -= 1
    # output is eventually a pipe, so we must pass a string
    output.write("\n".join(content) + "\n")
    return ids


def _writeContourNodes(
    output,
    contourList,
    elevation,
    IDCounter,
    versionString,
    timestampString,
):
    """calls _makePoints() to write nodes to <output> and collects information
    about the paths in contourList, namely the node ids for each path, which is
    the returned.
    """
    ways = []
    for path in contourList:
        nodeRefs = _makePoints(output, path, IDCounter, versionString, timestampString)
        if nodeRefs[0] == nodeRefs[-1]:
            ways.append((nodeRefs[0], len(nodeRefs) - 1, True, elevation))
        else:
            ways.append((nodeRefs[0], len(nodeRefs), False, elevation))
    return ways


def writeXML(
    output,
    tile_contours: TileContours,
    timestampString,
    start_node_id,
    osm_version,
) -> tuple[int, pyhgtmap.output.WaysType]:
    """emits node OSM XML to <output> and collects path information.

    <output> may be anything having a write method.  For now, its used with
    Output instance or an open pipe to the parent process, if running in parallel.

    <contourData> is a pyhgtmap.hgt.ContourObject instance, <elevations> a list
    of elevations to generate contour lines for.

    <opts> are the options coming from pyhgtmap.
    """
    IDCounter = pyhgtmap.output.Id(start_node_id)
    versionString = ' version="1"' if osm_version > 0.5 else ""
    ways = []
    for elevation, contour_list in tile_contours.contours.items():
        if not contour_list:
            continue
        ways.extend(
            _writeContourNodes(
                output,
                contour_list,
                elevation,
                IDCounter,
                versionString,
                timestampString,
            ),
        )
        # output.flush()
    newId = IDCounter.getId()
    return newId, pyhgtmap.output.build_efficient_ways(ways)
