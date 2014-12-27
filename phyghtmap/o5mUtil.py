# -*- encoding: utf-8 -*-

__author__ = "Adrian Dempwolff (adrian.dempwolff@urz.uni-heidelberg.de)"
__version__ = "1.60"
__copyright__ = "Copyright (c) 2009-2014 Adrian Dempwolff"
__license__ = "GPLv2+"

from struct import pack
import time
import numpy

from phyghtmap.varint import *
#from phyghtmap.pbfint import int2str, sint2str # same as above, C version

HUNDREDNANO = 10000000

class StringTable(object):
	def __init__(self):
		self.table = []
		self.maxStringRef = 15000

	def stringOrIndex(self, string):
		if len(string) > 250:
			return string
		if not string in self.table:
			self.table.append(string)
			if len(self.table) == self.maxStringRef+1:
				self.table.pop(0)
			return string
		else:
			stringRef = len(self.table) - self.table.index(string)
			return int2str(stringRef)

class Output(object):
	def __init__(self, filename, osmVersion, phyghtmapVersion, bbox=[],
		elevClassifier=None):
		self.outf = open(filename, "wb")
		self.bbox = bbox
		self.elevClassifier = elevClassifier
		self.stringTable = StringTable()
		self.timestamp = long(time.mktime(time.localtime()))
		self.timestampString = "" # dummy attribute, needed by main.py 
		self.makeHeader(osmVersion, phyghtmapVersion)
		self.firstNodeChunk = True
		self.lastNodeId = 0

	def makeStringPair(self, a, b=None):
		"""format a string pair according to the o5m specification.

		<a> and <b> are two strings; <b> can be None.
		"""
		string = "\x00"+a+"\x00"
		if b != None:
			string += b+"\x00"
		return string

	def makeHeader(self, osmVersion, phyghtmapVersion):
		header = []
		header.append(chr(0xff))
		header.append(chr(0xe0))
		header.append(chr(0x04))
		header.append("o5m2")
		# timestamp dataset
		timestampDataset =  self.makeTimestampDataset()
		header.append(timestampDataset)
		# bounding box dataset
		bboxDataset = self.makeBBoxDataset()
		header.append(bboxDataset)
		#write the header
		self.outf.write("".join(header))

	def makeTimestampDataset(self):
		timestampDataset = [chr(0xdc), ]
		timestampData = sint2str(self.timestamp)
		timestampDataset.append(int2str(len(timestampData)))
		timestampDataset.append(timestampData)
		return "".join(timestampDataset)

	def makeBBoxDataset(self):
		# bbox dataset, with length
		bboxDataset = [chr(0xdb), ]
		bboxData = "".join([sint2str(long(i*HUNDREDNANO))
			for i in self.bbox])
		bboxDataset.append(int2str(len(bboxData)))
		bboxDataset.append(bboxData)
		return "".join(bboxDataset)

	def makeVersionChunk(self, first=False):
		# maybe for later:
		# version = 1
		# timestamp = self.timestamp or 0
		# if timestamp:
		# changeset = 1
		# uid = 0
		data = []
		# version
		data.append(int2str(1))
		# timestamp
		if first:
			data.append(sint2str(self.timestamp))
		else:
			data.append(sint2str(0))
		return "".join(data)

	def writeNodes(self, nodes, startNodeId):
		"""writes nodes to self.outf.  nodeList shall be a list of
		(<lon>, <lat>) duples of longs in nanodegrees of longitude and latitude,
		respectively.

		The nodelist is split up to make sure the pbf blobs will not be too big.
		"""
		# because this method is possibly used multiple times per output file,
		# reset the delta counters each time
		self.outf.write(chr(0xff))
		#write the first node
		self.writeNode(nodes[0], lastNode=None, idDelta=startNodeId)
		# write all other nodes:
		for ind, node in enumerate(nodes[1:]):
			self.writeNode(node, lastNode=nodes[ind], idDelta=1)
		self.firstNodeChunk = False

	def writeNode(self, node, lastNode, idDelta):
		nodeDataset = []
		# 0x10 means node
		nodeDataset.append(chr(0x10))
		nodeData = self.makeNodeData(node, lastNode, idDelta)
		nodeDataLen = len(nodeData)
		nodeDataset.append(int2str(nodeDataLen))
		nodeDataset.append(nodeData)
		self.outf.write("".join(nodeDataset))

	def makeNodeData(self, node, lastNode, idDelta):
		data = []
		data.append(sint2str(idDelta))
		# version information
		if lastNode == None:
			data.append(self.makeVersionChunk(first=False))
		else:
			data.append(self.makeVersionChunk(first=False))
		# lon, lat
		lon, lat = node
		if lastNode != None:
			deltaLon = sint2str(lon-lastNode[0])
			deltaLat = sint2str(lat-lastNode[1])
		else:
			deltaLon = sint2str(lon)
			deltaLat = sint2str(lat)
		data.append(deltaLon)
		data.append(deltaLat)
		# no tags, so data is complete now
		return "".join(data)

	def writeWays(self, ways, startWayId):
		"""writes ways to self.outf.  ways shall be a list of
		(<startNodeId>, <length>, <isCycle>, <elevation>) tuples.
		"""
		# write a reset byte
		self.outf.write(chr(0xff))
		# write the first way
		self.writeWay(ways[0], idDelta=startWayId, first=True)
		# write all other ways
		for way in ways[1:]:
			self.writeWay(way, idDelta=1)

	def writeWay(self, way, idDelta, first=False):
		wayDataset = []
		# 0x11 means way
		wayDataset.append(chr(0x11))
		wayData = self.makeWayData(way, idDelta, first)
		wayDataLen = len(wayData)
		wayDataset.append(int2str(wayDataLen))
		wayDataset.append(wayData)
		self.outf.write("".join(wayDataset))

	def makeWayData(self, way, idDelta, first):
		startNodeId, length, isCycle, elevation = way
		data = []
		data.append(sint2str(idDelta))
		# version information
		if first:
			# first way
			data.append(self.makeVersionChunk(first=False))
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
		elevClassifierTag = self.makeStringPair("contour_ext", 
			self.elevClassifier(elevation))
		data.append(self.stringTable.stringOrIndex(eleTag))
		data.append(self.stringTable.stringOrIndex(contourTag))
		data.append(self.stringTable.stringOrIndex(elevClassifierTag))
		return "".join(data)

	def makeWayReferenceSection(self, startNodeId, length, isCycle):
		nodeIdDeltas = []
		# the first node id, delta coded
		nodeIdDeltas.append(startNodeId-self.lastNodeId)
		nodeIdDeltas.extend([1, ]*(length-1))
		if isCycle:
			nodeIdDeltas.append(-(length-1))
			self.lastNodeId = startNodeId
		else:
			self.lastNodeId = startNodeId + length - 1
		return "".join([sint2str(nodeIdDelta) for nodeIdDelta in nodeIdDeltas])

	def write(self, nodeString):
		"""wrapper imitating osmUtil.Output's write method.
		"""
		startNodeId, nodes = eval(nodeString.strip())
		self.writeNodes(nodes, startNodeId)

	def flush(self):
		self.outf.flush()

	def done(self):
		self.outf.write("\xfe")
		self.__del__()

	def __del__(self):
		self.outf.close()


class Id(object):
	"""a counter, constructed with the first number to return.

	Count using the getId method.
	"""
	def __init__(self, offset):
		self.curId = offset

	def getId(self):
		self.curId += 1
		return self.curId-1


def _makePoints(path, elevation, IDCounter):
	ids, nodes = [], []
	for lon, lat in path:
		IDCounter.curId += 1
		nodes.append((long(lon*HUNDREDNANO), long(lat*HUNDREDNANO)))
		ids.append(IDCounter.curId-1)
	if numpy.all(path[0]==path[-1]):  # close contour
		del nodes[-1]  # remove last node
		del ids[-1]
		ids.append(ids[0])
		IDCounter.curId -= 1
	return nodes, ids

def _makeNodesWays(contourList, elevation, IDCounter):
	ways = []
	nodes = []
	for path in contourList:
		newNodes, nodeRefs = _makePoints(path, elevation, IDCounter)
		nodes.extend(newNodes)
		if nodeRefs[0] == nodeRefs[-1]:
			ways.append((nodeRefs[0], len(nodeRefs)-1, True, elevation))
		else:
			ways.append((nodeRefs[0], len(nodeRefs), False, elevation))
	return nodes, ways

def writeNodes(output, contourData, elevations, timestampString, # dummy option
	opts):
	IDCounter = Id(opts.startId)
	ways = []
	nodes = []
	startId = opts.startId
	for elevation in elevations:
		contourList = contourData.trace(elevation)[0]
		if not contourList:
			continue
		newNodes, newWays = _makeNodesWays(contourList, elevation, IDCounter)
		ways.extend(newWays)
		nodes.extend(newNodes)
		if len(nodes) > 32000:
			output.write(str((startId, nodes))+"\n")
			output.flush()
			startId = IDCounter.curId
			nodes = []
	#newId = opts.startId + len(nodes)#sum([length for _, length, _, _ in ways])
	newId = IDCounter.getId()
	if len(nodes) > 0:
		output.write(str((startId, nodes))+"\n")
		output.flush()
	return newId, ways

