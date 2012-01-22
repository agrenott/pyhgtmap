import numpy
from matplotlib import __version__ as mplversion
import time
import datetime

def makeElevClassifier(majorDivisor, mediumDivisor):
	"""returns a function taking an elevation and returning a
	category specifying whether it's a major, medium or minor contour.
	"""
	def classify(height):
		if height%majorDivisor==0:
			return "elevation_major"
		elif height%mediumDivisor==0:
			return "elevation_medium"
		else:
			return "elevation_minor"
	return classify

def makeUtcTimestamp():
	return datetime.datetime.utcfromtimestamp(
		time.mktime(time.localtime())).isoformat()+"Z"


class Id(object):
	"""a counter, constructed with the first number to return.

	Count using the getId method.
	"""
	def __init__(self, offset):
		self.curId = offset

	def getId(self):
		self.curId += 1
		return self.curId-1


class Output(object):
	"""An OSM output.

	It is constructed with a destination name, the desired OSM API version,
	the version of phyghtmap as string, an already formatted OSM XML bounds tag
	as output by the hgt.makeBoundsString() function,	an integer representing
	the gzip compressionlevel (or 0 if no gzip compression is desired),
	an elevation classifying function as returned by makeElevClassifier()
	and a hint weather to write timestamps to output or not.
	"""
	def __init__(self, fName, osmVersion, phyghtmapVersion, boundsTag, gzip=0,
		elevClassifier=None, timestamp=False):
		if 0 < gzip < 10:
			import gzip as Gzip
			self.outF = Gzip.open(fName, "w", gzip)
		else:
			self.outF = open(fName, "w")
		self.osmVersion = "%.1f"%osmVersion
		if osmVersion > 0.5:
			self.versionString = ' version="1"'
		else:
			self.versionString = ""
		if timestamp:
			self.timestampString = ' timestamp="%s"'%makeUtcTimestamp()
		else:
			self.timestampString = ""
		self.elevClassifier = elevClassifier
		self.phyghtmapVersion= phyghtmapVersion
		self.boundsTag = boundsTag
		self._writePreamble()

	def _writePreamble(self):
		self.outF.write('<?xml version="1.0" encoding="utf-8"?>\n')
		self.outF.write('<osm version="%s" generator="phyghtmap %s">\n'%(
			self.osmVersion, self.phyghtmapVersion))
		self.outF.write(self.boundsTag+"\n")
	
	def done(self):
		self.outF.write("</osm>\n")
		self.outF.close()
		return 0

	def write(self, output):
		self.outF.write(output)

	def flush(self):
		self.outF.flush()

	def writeWays(self, ways, startWayId):
		IDCounter = Id(startWayId)
		for startNodeId, length, isCycle, elevation in ways:
			IDCounter.curId += 1
			nodeIds = range(startNodeId, startNodeId+length)
			if isCycle:
				nodeIds.append(nodeIds[0])
			nodeRefs = ('<nd ref="%d"/>'*len(nodeIds))%tuple(nodeIds)
			self.write('<way id="%d"%s%s>%s'
				'<tag k="ele" v="%d"/>'
				'<tag k="contour" v="elevation"/>'
				'<tag k="contour_ext" v="%s"/>'
				'</way>\n'%(
					IDCounter.curId-1,
					self.versionString,
					self.timestampString,
					nodeRefs,
					elevation,
					self.elevClassifier(elevation)))

def _makePoints(output, path, ele, IDCounter, versionString, timestampString):
	"""writes OSM representations of the points making up a path to
	output.

	It returns a list of the node ids included in this path. 
	"""
	ids, content = [], []
	for lon, lat in path:
		IDCounter.curId += 1
		content.append('<node id="%d" lat="%.7f" lon="%.7f"%s%s/>'%(
			IDCounter.curId-1,
			lat,
			lon,
			versionString,
			timestampString,)
		)
		ids.append(IDCounter.curId-1)
	if numpy.all(path[0]==path[-1]):  # close contour
		del content[-1]  # remove last node
		del ids[-1]
		ids.append(ids[0])
		IDCounter.curId -= 1
	output.write("".join(content)+"\n")
	return ids

def _writeContourNodes(output, contourList, elevation, osmCat, IDCounter,
	versionString, timestampString, maxNodesPerWay):
	"""calls _makePoints() to write nodes to <output> and collects information
	about the paths in contourList, namely the node ids for each path, which is
	the returned.
	"""
	ways = []
	for path in contourList:
		nodeRefs = _makePoints(output, path, elevation, IDCounter, versionString,
			timestampString)
		if nodeRefs[0] == nodeRefs[-1]:
			ways.append((nodeRefs[0], len(nodeRefs)-1, True, elevation))
		else:
			ways.append((nodeRefs[0], len(nodeRefs), False, elevation))
	return ways


def writeXML(output, classifier, contourData, elevations, timestampString, opts):
	"""emits node OSM XML to <output> and collects path information.

	<output> may be anything having a write method.  For now, its used with
	Output instance or an open pipe to the parent process, if running in parallel.

	<classifier> is a function returning an osm contour class for a given
	height.  You probably want to generate it using makeElevClassifier.

	<contourData> is a phyghtmap.hgt.ContourObject instance, <elevations> a list
	of elevations to generate contour lines for.

	<opts> are the options coming from phyghtmap.
	"""
	IDCounter = Id(opts.startId)
	if opts.osmVersion > 0.5:
		versionString = ' version="1"'
	else:
		versionString = ""
	ways = []
	for elevation in elevations:
		contourList = contourData.trace(elevation)[0]
		if not contourList:
			continue
		ways.extend(_writeContourNodes(output, contourList, elevation,
			classifier(elevation), IDCounter, versionString, timestampString,
			opts.maxNodesPerWay))
		#output.flush()
	newId = IDCounter.getId()
	return newId, ways
