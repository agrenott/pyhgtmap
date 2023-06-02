# -*- encoding: utf-8 -*-


import time
from typing import Callable, Tuple

import pyhgtmap.output
from pyhgtmap import output
from pyhgtmap.hgt.tile import TileContours
from pyhgtmap.varint import int2str, join, sint2str, writableInt, writableString

HUNDREDNANO = 10000000


class StringTable(object):
    def __init__(self):
        self.table = []
        self.maxStringRef = 15000

    def stringOrIndex(self, string):
        if len(string) > 250:
            return string
        if string not in self.table:
            self.table.append(string)
            if len(self.table) == self.maxStringRef + 1:
                self.table.pop(0)
            return string
        else:
            stringRef = len(self.table) - self.table.index(string)
            return int2str(stringRef)

    def reset(self):
        self.table = []


class Output(output.Output):
    def __init__(
        self,
        filename,
        osmVersion,
        pyhgtmap_version,
        bbox: Tuple[float, float, float, float],
        elevClassifier: Callable[[int], str],
        writeTimestamp=False,
    ) -> None:
        super().__init__()
        self.outf = open(filename, "wb")
        self.bbox = bbox
        self.elevClassifier = elevClassifier
        self.stringTable = StringTable()
        self.writeTimestamp = writeTimestamp
        self.timestamp = int(time.mktime(time.localtime()))
        self.timestampString = ""  # dummy attribute, needed by main.py
        self.writeHeader(osmVersion, pyhgtmap_version)

    def makeStringPair(self, a, b=None):
        """format a string pair according to the o5m specification.

        <a> and <b> are two strings; <b> can be None.
        """
        string = chr(0) + a + chr(0)
        if b is not None:
            string += b + chr(0)
        return writableString(string)

    def writeReset(self):
        self.outf.write(writableInt(0xFF))
        self.lastNodeId = 0
        self.stringTable.reset()

    def writeHeader(self, osmVersion, pyhgtmap_version):
        # write reset
        self.writeReset()
        header = []
        # file format dataset (0xe0), length (0x04), format (o5m2)
        header.extend([writableInt(0xE0), writableInt(0x04), writableString("o5m2")])
        # timestamp dataset
        timestampDataset = self.makeTimestampDataset()
        header.append(timestampDataset)
        # bounding box dataset
        bboxDataset = self.makeBBoxDataset()
        header.append(bboxDataset)
        # write the header
        self.outf.write(join(header))

    def makeTimestampDataset(self):
        timestampDataset = [
            writableInt(0xDC),
        ]
        timestampData = sint2str(self.timestamp)
        timestampDataset.append(int2str(len(timestampData)))
        timestampDataset.append(timestampData)
        return join(timestampDataset)

    def makeBBoxDataset(self):
        # bbox dataset, with length
        bboxDataset = [
            writableInt(0xDB),
        ]
        bboxData = join([sint2str(int(i * HUNDREDNANO)) for i in self.bbox])
        bboxDataset.append(int2str(len(bboxData)))
        bboxDataset.append(bboxData)
        return join(bboxDataset)

    def makeVersionChunk(self, first=False):
        data = []
        # version
        data.append(int2str(1))
        # timestamp = self.timestamp or 0, if self.timestamp, write changeset and
        # uid
        # timestamp is delta coded
        if first and self.writeTimestamp:
            data.append(sint2str(self.timestamp))
        else:
            data.append(sint2str(0))
        if self.writeTimestamp:
            # changeset, delta coded
            if first:
                data.append(sint2str(1))
            else:
                data.append(sint2str(0))
            # userid, username = ("", ""), string pair -> 0x00,0x00,0x00
            data.append(self.stringTable.stringOrIndex(writableInt(0x00) * 3))
        return join(data)

    def writeNodesO5m(self, nodes, startNodeId):
        """writes nodes to self.outf.  nodeList shall be a list of
        (<lon>, <lat>) duples of ints in nanodegrees of longitude and latitude,
        respectively.

        The nodelist is split up to make sure the pbf blobs will not be too big.
        """
        if len(nodes) == 0:
            return
        # because this method is possibly used multiple times per output file,
        # reset the delta counters each time
        self.writeReset()
        # write the first node
        self.writeNode(nodes[0], lastNode=None, idDelta=startNodeId)
        # write all other nodes:
        for ind, node in enumerate(nodes[1:]):
            self.writeNode(node, lastNode=nodes[ind], idDelta=1)

    def writeNode(self, node, lastNode, idDelta):
        nodeDataset = []
        # 0x10 means node
        nodeDataset.append(writableInt(0x10))
        nodeData = self.makeNodeData(node, lastNode, idDelta)
        nodeDataLen = len(nodeData)
        nodeDataset.append(int2str(nodeDataLen))
        nodeDataset.append(nodeData)
        self.outf.write(join(nodeDataset))

    def makeNodeData(self, node, lastNode, idDelta):
        data = []
        data.append(sint2str(idDelta))
        # version information
        if lastNode is None:
            # first node since reset
            data.append(self.makeVersionChunk(first=True))
        else:
            data.append(self.makeVersionChunk(first=False))
        # lon, lat
        lon, lat = node
        if lastNode is not None:
            deltaLon = sint2str(lon - lastNode[0])
            deltaLat = sint2str(lat - lastNode[1])
        else:
            deltaLon = sint2str(lon)
            deltaLat = sint2str(lat)
        data.append(deltaLon)
        data.append(deltaLat)
        # no tags, so data is complete now
        return join(data)

    def _write_ways(self, ways: pyhgtmap.output.WaysType, startWayId):
        """writes ways to self.outf.  ways shall be a list of
        (<startNodeId>, <length>, <isCycle>, <elevation>) tuples.
        """
        if len(ways) == 0:
            return
        # write a reset byte
        self.writeReset()
        # write the first way
        self.writeWay(ways[0], idDelta=startWayId, first=True)
        # write all other ways
        for way in ways[1:]:
            self.writeWay(way, idDelta=1)

    def writeWay(self, way: pyhgtmap.output.WayType, idDelta, first=False):
        wayDataset = []
        # 0x11 means way
        wayDataset.append(writableInt(0x11))
        wayData = self.makeWayData(way, idDelta, first)
        wayDataLen = len(wayData)
        wayDataset.append(int2str(wayDataLen))
        wayDataset.append(wayData)
        self.outf.write(join(wayDataset))

    def makeWayData(self, way: pyhgtmap.output.WayType, idDelta, first):
        startNodeId, length, isCycle, elevation = way
        data = []
        data.append(sint2str(idDelta))
        # version information
        if first:
            # first way
            data.append(self.makeVersionChunk(first=True))
        else:
            data.append(self.makeVersionChunk(first=False))
        # node references
        wayRefSection = self.makeWayReferenceSection(startNodeId, length, isCycle)
        wayRefSectionLen = len(wayRefSection)
        data.append(int2str(wayRefSectionLen))
        data.append(wayRefSection)
        # tags
        # ele = <elevation>
        eleTag = self.makeStringPair("ele", str(elevation))
        contourTag = self.makeStringPair("contour", "elevation")
        elevClassifierTag = self.makeStringPair(
            "contour_ext", self.elevClassifier(elevation)
        )
        data.append(self.stringTable.stringOrIndex(eleTag))
        data.append(self.stringTable.stringOrIndex(contourTag))
        data.append(self.stringTable.stringOrIndex(elevClassifierTag))
        return join(data)

    def makeWayReferenceSection(self, startNodeId, length, isCycle):
        nodeIdDeltas = []
        # the first node id, delta coded
        nodeIdDeltas.append(startNodeId - self.lastNodeId)
        nodeIdDeltas.extend(
            [
                1,
            ]
            * (length - 1)
        )
        if isCycle:
            nodeIdDeltas.append(-(length - 1))
            self.lastNodeId = startNodeId
        else:
            self.lastNodeId = startNodeId + length - 1
        return join([sint2str(nodeIdDelta) for nodeIdDelta in nodeIdDeltas])

    def write(self, nodeString):
        """wrapper imitating osmUtil.Output's write method."""
        startNodeId, nodes = eval(nodeString.strip())
        self.writeNodesO5m(nodes, startNodeId)

    def flush(self) -> None:
        self.outf.flush()

    def done(self) -> None:
        super().done()
        self.outf.write(writableInt(0xFE))
        self.__del__()

    def __del__(self):
        self.outf.close()

    def write_nodes(
        self,
        tile_contours: TileContours,
        timestamp_string: str,
        start_node_id: int,
        osm_version: float,
    ) -> Tuple[int, output.WaysType]:
        return writeNodes(self, tile_contours, timestamp_string, start_node_id)


def writeNodes(
    output: Output,
    tile_contours: TileContours,
    timestampString,  # dummy option
    start_node_id,
) -> Tuple[int, output.WaysType]:
    IDCounter = pyhgtmap.output.Id(start_node_id)
    ways = []
    nodes = []
    startId = start_node_id
    for elevation, contourList in tile_contours.contours.items():
        if not contourList:
            continue
        newNodes, newWays = pyhgtmap.output.make_nodes_ways(
            contourList, elevation, IDCounter, HUNDREDNANO
        )
        ways.extend(newWays)
        nodes.extend(newNodes)
        if len(nodes) > 32000:
            output.write(str((startId, nodes)) + "\n")
            output.flush()
            startId = IDCounter.curId
            nodes = []
    newId = IDCounter.getId()
    if len(nodes) > 0:
        output.write(str((startId, nodes)) + "\n")
        output.flush()
    return newId, pyhgtmap.output.build_efficient_ways(ways)
