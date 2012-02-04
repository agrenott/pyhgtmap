import zlib
from struct import pack
import time
import numpy

from phyghtmap import osmformat_pb2 as osmf
from phyghtmap import fileformat_pb2 as ff

NANO = 1000000000L

class Output(object):
	def __init__(self, filename, osmVersion, phyghtmapVersion, bbox=[],
		elevClassifier=None):
		self.outf = open(filename, "wb")
		self.bbox = bbox
		self.granularity = 100
		self.date_granularity = 1000
		self.elevClassifier = elevClassifier
		self.maxNodesPerNodeBlock = 8000
		self.maxNodesPerWayBlock = 32000
		self.timestamp = long(time.mktime(time.localtime()))
		self.timestampString = "" # dummy attribute
		self.makeHeader(osmVersion, phyghtmapVersion)

	def makeHeader(self, osmVersion, phyghtmapVersion):
		blobHeader = ff.BlobHeader()
		blobHeader.type = 'OSMHeader'
		blob = self.makeHeaderBlob(osmVersion, phyghtmapVersion).SerializeToString()
		blobHeader.datasize = len(blob)
		blobHeader = blobHeader.SerializeToString()
		size = pack('!L', len(blobHeader))
		self.outf.write(size)
		self.outf.write(blobHeader)
		self.outf.write(blob)

	def makeHeaderBlob(self, osmVersion, phyghtmapVersion):
		blob = ff.Blob()
		headerBlock = self.makeHeaderBlock(osmVersion,
			phyghtmapVersion).SerializeToString()
		#blob.raw = ''
		blob.raw_size = len(headerBlock)
		blob.zlib_data = zlib.compress(headerBlock)
		return blob

	def makeHeaderBlock(self, osmVersion, phyghtmapVersion):
		headerBlock = osmf.HeaderBlock()
		headerBlock.writingprogram = (
			u"phyghtmap %s (http://wiki.openstreetmap.org/wiki/phyghtmap)"%(
			phyghtmapVersion))
		headerBlock.required_features.append(u"OsmSchema-V%.1f"%osmVersion)
		headerBlock.required_features.append(u"DenseNodes")
		#headerBlock.optional_features = []
		if len(self.bbox) == 4:
			headerBBox = self.makeHeaderBBox()
			for b in ["left", "bottom", "right", "top"]:
				setattr(headerBlock.bbox, b, getattr(headerBBox, b))
		#headerBlock.source = u""
		return headerBlock

	def makeHeaderBBox(self):
		left, bottom, right, top = [long(i*NANO) for i in self.bbox]
		headerBBox = osmf.HeaderBBox()
		headerBBox.left = left
		headerBBox.right = right
		headerBBox.top = top
		headerBBox.bottom = bottom
		return headerBBox

	def writeNodes(self, nodes, startNodeId):
		"""writes nodes to self.outf.  nodeList shall be a list of
		(<lon>, <lat>) duples of longs in nanodegrees of longitude and latitude,
		respectively.

		The nodelist is split up to make sure the pbf blobs will not be too big.
		"""
		for i in range(0, len(nodes), self.maxNodesPerNodeBlock):
			self.writeNodesChunk(nodes[i:i+self.maxNodesPerNodeBlock], startNodeId+i)

	def writeNodesChunk(self, nodes, startNodeId):
		nodeBlobHeader = ff.BlobHeader()
		nodeBlobHeader.type = u"OSMData"
		nodeBlob = self.makeNodeBlob(startNodeId, nodes).SerializeToString()
		nodeBlobHeader.datasize = len(nodeBlob)
		nodeBlobHeader = nodeBlobHeader.SerializeToString()
		size = pack('!L', len(nodeBlobHeader))
		self.outf.write(size)
		self.outf.write(nodeBlobHeader)
		self.outf.write(nodeBlob)

	def makeNodeBlob(self, startNodeId, nodeList):
		nodeBlob = ff.Blob()
		nodePrimitiveBlock = self.makeNodePrimitiveBlock(
			startNodeId, nodeList).SerializeToString()
		nodeBlob.raw_size = len(nodePrimitiveBlock)
		nodeBlob.zlib_data = zlib.compress(nodePrimitiveBlock)
		return nodeBlob

	def makeNodePrimitiveBlock(self, startNodeId, nodeList):
		nodePrimitiveBlock = osmf.PrimitiveBlock()
		nodePrimitiveBlock.stringtable.s.append("")
		nodePrimitiveBlock.granularity = self.granularity
		nodePrimitiveBlock.lon_offset = nodeList[0][0]
		nodePrimitiveBlock.lat_offset = nodeList[0][1]
		nodePrimitiveBlock.date_granularity = self.date_granularity
		nodePrimitiveGroup = nodePrimitiveBlock.primitivegroup.add()
		self.makeDenseNodes(nodePrimitiveGroup.dense, startNodeId, nodeList)
		return nodePrimitiveBlock

	def makeDenseNodes(self, dense, startNodeId, nodeList):
		lon_offset = long(nodeList[0][0]/self.granularity)
		lat_offset = long(nodeList[0][1]/self.granularity)
		dense.lon.append(0)
		dense.lat.append(0)
		dense.id.append(startNodeId)
		# denseinfo
		dense.denseinfo.timestamp.append(self.timestamp)
		dense.denseinfo.version.append(1)
		dense.denseinfo.changeset.append(0)
		dense.denseinfo.uid.append(0)
		dense.denseinfo.user_sid.append(0)
		last_lon = 0
		last_lat = 0
		for lon, lat in nodeList[1:]:
			lon = long(lon/self.granularity)-lon_offset
			lat = long(lat/self.granularity)-lat_offset
			lon_diff = lon - last_lon
			lat_diff = lat - last_lat
			last_lon = lon
			last_lat = lat
			dense.lon.append(lon_diff)
			dense.lat.append(lat_diff)
			dense.id.append(1)
			# denseinfo
			dense.denseinfo.timestamp.append(0)
			dense.denseinfo.version.append(1)
			dense.denseinfo.changeset.append(0)
			dense.denseinfo.uid.append(0)
			dense.denseinfo.user_sid.append(0)

	def writeWays(self, ways, startWayId):
		"""writes ways to self.outf.  ways shall be a list of
		(<startNodeId>, <length>, <isCycle>, <elevation>) tuples.

		The waylist is split up to make sure the pbf blobs will not be too big.
		"""
		curWays = []
		curNumOfNodes = 0
		for ind, way in enumerate(ways):
			length = way[1]
			if curNumOfNodes+length > self.maxNodesPerWayBlock:
				self.writeWaysChunk(curWays, startWayId+ind-len(curWays))
				curNumOfNodes = length
				curWays = [way, ]
			else:
				curWays.append(way)
				curNumOfNodes += length
		else:
			if len(curWays) > 0:
				self.writeWaysChunk(curWays, startWayId+len(ways)-len(curWays))

	def writeWaysChunk(self, ways, startWayId):
		wayBlobHeader = ff.BlobHeader()
		wayBlobHeader.type = u"OSMData"
		wayBlob = self.makeWayBlob(startWayId, ways).SerializeToString()
		wayBlobHeader.datasize = len(wayBlob)
		wayBlobHeader = wayBlobHeader.SerializeToString()
		size = pack('!L', len(wayBlobHeader))
		self.outf.write(size)
		self.outf.write(wayBlobHeader)
		self.outf.write(wayBlob)

	def makeWayBlob(self, startWayId, wayList):
		wayBlob = ff.Blob()
		wayPrimitiveBlock = self.makeWayPrimitiveBlock(
			startWayId, wayList).SerializeToString()
		wayBlob.raw_size = len(wayPrimitiveBlock)
		wayBlob.zlib_data = zlib.compress(wayPrimitiveBlock)
		return wayBlob

	def makeWayPrimitiveBlock(self, startWayId, wayList):
		wayPrimitiveBlock = osmf.PrimitiveBlock()
		wayPrimitiveBlock.stringtable.s.append("")
		wayPrimitiveBlock.granularity = self.granularity
		wayPrimitiveBlock.lon_offset = 0
		wayPrimitiveBlock.lat_offset = 0
		wayPrimitiveBlock.date_granularity = self.date_granularity
		wayPrimitiveGroup = wayPrimitiveBlock.primitivegroup.add()
		strings = self.makeWays(wayPrimitiveGroup.ways, startWayId, wayList)
		wayPrimitiveBlock.stringtable.s.extend(strings)
		return wayPrimitiveBlock

	def makeWays(self, ways, startWayId, wayList):
		strings = ["", ]
		strings.append("ele")              # 1
		strings.append("contour")          # 2
		strings.append("elevation")        # 3
		strings.append("contour_ext")      # 4
		strings.append("elevation_minor")  # 5
		strings.append("elevation_medium") # 6
		strings.append("elevation_major")  # 7
		for ind, (startNodeId, length, isCycle, elevation) in enumerate(wayList):
			way = ways.add()
			way.id = startWayId+ind
			way.refs.append(startNodeId)
			way.refs.extend([1]*(length-1))
			if isCycle:
				way.refs.append(-(length-1))
			if not str(elevation) in strings:
				strings.append(str(elevation))
			way.keys.append(1)
			way.vals.append(strings.index(str(elevation)))
			way.keys.append(2)
			way.vals.append(3)
			way.keys.append(4)
			way.vals.append(strings.index(self.elevClassifier(elevation)))
			way.info.version = 1
			way.info.timestamp = self.timestamp
			way.info.uid = 0
			way.info.user_sid = 0
		return strings[1:]

	def write(self, nodeString):
		"""wrapper imitating osmUtil.Output's write method.
		"""
		startNodeId, nodes = eval(nodeString.strip())
		self.writeNodes(nodes, startNodeId)

	def flush(self):
		self.outf.flush()

	def done(self):
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
		nodes.append((long(lon*NANO), long(lat*NANO)))
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

