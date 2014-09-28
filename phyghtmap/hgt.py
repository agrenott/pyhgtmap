__author__ = "Adrian Dempwolff (adrian.dempwolff@urz.uni-heidelberg.de)"
__version__ = "1.50"
__copyright__ = "Copyright (c) 2009-2014 Adrian Dempwolff"
__license__ = "GPLv2+"

import os
from matplotlib import _cntr
from matplotlib import __version__ as mplversion
if mplversion < "1.3.0":
	from matplotlib.nxutils import points_inside_poly
else:
	from matplotlib.path import Path as PolygonPath
import numpy


class hgtError(Exception):
	"""is the main class of visible exceptions from this file.
	"""

class filenameError(hgtError):
	"""is raised when parsing bad filenames.
	"""

class elevationError(hgtError):
	"""is raised when trying to deal with elevations out of range.
	"""

def halfOf(seq):
	"""returns the first half of a sequence
	"""
	return seq[:len(seq)//2]

def makeBBoxString(bbox):
	return "%%slon%.2f_%.2flat%.2f_%.2f"%(
		bbox[0], bbox[2],
		bbox[1], bbox[3]
	)

def parsePolygon(filename):
	"""reads polygons from a file like one included in
	http://download.geofabrik.de/clipbounds/clipbounds.tgz
	and returns it as list of (<lon>, <lat>) tuples.
	"""
	lines = [line.strip().lower() for line in
		open(filename).read().split("\n") if line.strip()]
	polygons = []
	curPolygon = []
	for l in lines:
		if l in [str(i) for i in range(1, lines.count("end"))]:
			# new polygon begins
			curPolygon = []
		elif l == "end" and len(curPolygon)>0:
			# polygon ends
			polygons.append(curPolygon)
			curPolygon = []
		elif l == "end":
			# file ends
			break
		elif len(l.split()) == 2:
			lon, lat = l.split()
			try:
				curPolygon.append((float(lon), float(lat)))
			except ValueError:
				continue
		else:
			continue
	lonLatList = []
	for p in polygons:
		lonLatList.extend(p)
	lonList = sorted([lon for lon, lat in lonLatList])
	latList = sorted([lat for lon, lat in lonLatList])
	minLon = lonList[0]
	maxLon = lonList[-1]
	minLat = latList[0]
	maxLat = latList[-1]
	return "%.7f:%.7f:%.7f:%.7f"%(minLon, minLat, maxLon, maxLat), polygons

def makeBoundsString(bbox):
	"""returns an OSM XML bounds tag.

	The input <bbox> may be a list or tuple of floats or an area string as passed
	to the --area option of phyghtmap in the following order:
	minlon, minlat, maxlon, maxlat.
	"""
	if type(bbox) in [type(str()), type(unicode())] and bbox.count(":")==3:
		bbox = bbox.split(":")
	minlon, minlat, maxlon, maxlat = [float(i) for i in bbox]
	return '<bounds minlat="%.7f" minlon="%.7f" maxlat="%.7f" maxlon="%.7f"/>'%(
		minlat, minlon, maxlat, maxlon)

def parseHgtFilename(filename, corrx, corry):
	"""tries to extract borders from filename and returns them as a tuple
	of floats:
	(<min longitude>, <min latitude>, <max longitude>, <max latitude>)

	Longitudes of west as well as latitudes of south are given as negative
	values.

	Eventually specified longitude (<corrx>) and latitude (<corry>)
	corrections are added here.
	"""
	latSwitch = filename[0:1].upper()
	latValue  = filename[1:3]
	lonSwitch = filename[3:4].upper()
	lonValue  = filename[4:7]		
	if latSwitch == 'N' and latValue.isdigit():
		minLat = int(latValue)
	elif latSwitch == 'S' and latValue.isdigit():
		minLat = -1 * int(latValue)
	else:
		raise filenameError("something wrong with latitude coding in"
			" filename %s"%filename)
	maxLat = minLat + 1
	if lonSwitch == 'E' and lonValue.isdigit():
		minLon = int(lonValue)
	elif lonSwitch == 'W' and lonValue.isdigit():
		minLon = -1 * int(lonValue)
	else:
		raise filenameError("something wrong with longitude coding in"
			" filename %s"%filename)
	maxLon = minLon + 1
	return minLon+corrx, minLat+corry, maxLon+corrx, maxLat+corry

def calcHgtArea(filenames, corrx, corry):
	filenames = [os.path.split(f[0])[1] for f in filenames]
	bboxes = [parseHgtFilename(f, corrx, corry) for f in filenames]
	minLon = sorted([b[0] for b in bboxes])[0]
	minLat = sorted([b[1] for b in bboxes])[0]
	maxLon = sorted([b[2] for b in bboxes])[-1]
	maxLat = sorted([b[3] for b in bboxes])[-1]
	return minLon, minLat, maxLon, maxLat


class ContourObject(object):
	def __init__(self, Cntr, maxNodesPerWay, polygon=None):
		self.Cntr = Cntr
		self.maxNodesPerWay = maxNodesPerWay
		self.polygon = polygon

	def _cutBeginning(self, p):
		"""is recursively called to cut off a path's first element
		if it equals the second one.

		This is needed for beauty only.  Such a path makes no sense, but
		matplotlib.Cntr.cntr's trace method sometimes returns this.

		If the path gets too short, an empty list is returned.
		"""
		if len(p)<2:
			return []
		elif not numpy.all(p[0]==p[1]):
			return p
		else:
			return self._cutBeginning(p[1:])

	def clipPath(self, path):
		"""clips a path with self.polygon and returns a list of
		clipped paths.  This method also removes consecutive identical nodes.
		"""
		if numpy.where(path!=path, 1, 0).sum() != 0:
			pathContainsNans = True
		else:
			pathContainsNans = False
		if not pathContainsNans:
			tmpList = []
			for ind, p in enumerate(path):
				if ind != 0:
					op = path[ind-1]
					if numpy.all(p==op):
						continue
				tmpList.append(p)
			return [tmpList, ]
		# path contains nans (from a polygon or void area or both)
		pathList = []
		tmpList = []
		for ind, p in enumerate(path):
			if ind != 0:
				op = path[ind-1]
				if numpy.all(p==op):
					# skip the rest if there are two consecutive identical nodes
					continue
			x, y = p
			if not False in [x==x, y==y]:
				# (x, y) inside polygon.  We know this because x or y would else be
				# nan since data outside the polygon is masked and filled with nans
				# and the resulting nodes' coordinates are (nan, nan).
				tmpList.append((x, y))
			elif len(tmpList) > 0:
				# (x, y) outside polygon, non-empty tmpList
				pathList.append(tmpList)
				tmpList = []
			else:
				# (x, y) outside polygon, previous (x, y) dto.
				continue
		else:
			if len(tmpList) > 0:
				pathList.append(tmpList)
		return pathList

	def splitList(self, l):
		"""splits a path to contain not more than self.maxNodesPerWay nodes.

		A list of paths containing at least 2 (or, with closed paths, 3) nodes
		is returned, along with the number of nodes and paths as written later to
		the OSM XML output.
		"""
		length = self.maxNodesPerWay
		#l = self._cutBeginning(l)
		if len(l) < 2:
			return [], 0, 0
		if length == 0 or len(l) <= length:
			tmpList = [l, ]
		else:
			if len(l)%(length-1) == 1:
				# the last piece of a path should contain at least 2 nodes
				l, endPiece = l[:-1], l[-2:]
			else:
				endPiece = None
			tmpList = [l[i:i+length] for i in range(0, len(l), length-1)]
			if endPiece != None:
				tmpList.append(endPiece)
		pathList = []
		numOfClosedPaths = 0
		for path in tmpList:
			#path = self._cutBeginning(path)
			if len(path) == 0:
				# self._cutBeginning() returned an empty list for this path
				continue
			if numpy.all(path[0]==path[-1]):
				# a closed path with at least 3 nodes
				numOfClosedPaths += 1
			pathList.append(path)
		numOfPaths = len(pathList)
		numOfNodes = sum([len(p) for p in pathList])-numOfClosedPaths
		return pathList, numOfNodes, numOfPaths

	def trace(self, elevation, **kwargs):
		"""this emulates matplotlib.cntr.Cntr's trace method.
		The difference is that this method returns already split paths,
		along with the number of nodes and paths as expected in the OSM
		XML output.  Also, consecutive identical nodes are removed.
		"""
		if mplversion >= "1.0.0":
			# matplotlib 1.0.0 and above returns vertices and segments, but we only need vertices
			rawPaths = halfOf(self.Cntr.trace(elevation, **kwargs))
		else:
			rawPaths = self.Cntr.trace(elevation, **kwargs)
		numOfPaths, numOfNodes = 0, 0
		resultPaths = []
		for path in rawPaths:
			for clippedPath in self.clipPath(path):
				splitPaths, numOfNodesAdd, numOfPathsAdd = self.splitList(clippedPath)
				resultPaths.extend(splitPaths)
				numOfPaths += numOfPathsAdd
				numOfNodes += numOfNodesAdd
		return resultPaths, numOfNodes, numOfPaths

def polygonMask(xData, yData, polygon):
	"""return a mask on self.zData corresponding to all polygons in self.polygon.
	<xData> is meant to be a 1-D array of longitude values, <yData> a 1-D array of
	latitude values.  An array usable as mask for the corresponding zData
	2-D array is returned.
	"""
	X, Y = numpy.meshgrid(xData, yData)
	xyPoints = numpy.vstack(([X.T],
		[Y.T])).T.reshape(len(xData)*len(yData), 2)
	maskArray = numpy.ma.array(numpy.empty((len(xData)*len(yData), 1)))
	for p in polygon:
		# run through all polygons and combine masks
		if mplversion < "1.3.0":
			mask = points_inside_poly(xyPoints, p)
		else:
			mask = PolygonPath(p).contains_points(xyPoints)
		maskArray = numpy.ma.array(maskArray,
			mask=mask, keep_mask=True)
	return numpy.invert(maskArray.mask.reshape(len(yData), len(xData)))


class hgtFile:
	"""is a handle for SRTM data files
	"""

	def __init__(self, filename, corrx, corry, polygon=None, checkPoly=False,
		voidMax=None):
		"""tries to open <filename> and extracts content to self.zData.

		<corrx> and <corry> are longitude and latitude corrections (floats)
		as passed to phyghtmap on the commandline.
		"""
		self.fullFilename = filename
		self.filename = os.path.split(filename)[-1]
		# SRTM3 hgt files contain 1201x1201 points;
		# however, we try to determine the real number of points.
		# Height data are stored as 2-byte signed integers, the byte order is
		# big-endian standard. The data are stored in a row major order.
		# All height data are in meters referenced to the WGS84/EGM96 geoid as
		# documented at http://www.nga.mil/GandG/wgsegm/.
		try:
			numOfDataPoints = os.path.getsize(self.fullFilename) / 2
			self.numOfRows = self.numOfCols = int(numOfDataPoints ** 0.5)
			self.zData = numpy.fromfile(self.fullFilename,
				dtype=">i2").reshape(self.numOfRows, self.numOfCols).astype("float32")
			if voidMax != None:
				voidMask = numpy.asarray(numpy.where(self.zData<=voidMax, True, False))
				self.zData = numpy.ma.array(self.zData, mask=voidMask, fill_value=float("NaN"))
		finally:
			self.lonIncrement = 1.0/(self.numOfCols-1)
			self.latIncrement = 1.0/(self.numOfRows-1)
			self.minLon, self.minLat, self.maxLon, self.maxLat = self.borders(corrx,
				corry)
			if checkPoly:
				self.polygon = polygon
			else:
				self.polygon = None
			xData = numpy.arange(self.numOfCols) * self.lonIncrement + self.minLon
			yData = numpy.arange(self.numOfRows) * self.latIncrement * -1 + self.maxLat
		# some statistics
		print 'hgt file %s: %i x %i points, bbox: (%.5f, %.5f, %.5f, %.5f)%s'%(self.fullFilename,
			self.numOfCols, self.numOfRows, self.minLon, self.minLat, self.maxLon,
			self.maxLat, {True: ", checking polygon borders", False: ""}[checkPoly])

	def borders(self, corrx=0.0, corry=0.0):
		"""determines the bounding box of self.filename using parseHgtFilename().
		"""
		return parseHgtFilename(self.filename, corrx, corry)

	def makeTiles(self, opts):
		"""generate tiles from self.zData according to the given <opts>.area and
		return them as list of hgtTile objects.
		"""
		area = opts.area or None
		maxNodes = opts.maxNodesPerTile
		step = int(opts.contourStepSize) or 20

		def truncateData(area, inputData):
			"""truncates a numpy array.
			returns (<min lon>, <min lat>, <max lon>, <max lat>) and an array of the
			truncated height data.
			"""
			if area:
				bboxMinLon, bboxMinLat, bboxMaxLon, bboxMaxLat = (float(bound)
					for bound in area.split(":"))
				if bboxMinLon > bboxMaxLon:
					# bbox covers the W180/E180 longitude
					if self.minLon < 0 or self.minLon < bboxMaxLon:
						# we are right of W180
						bboxMinLon = self.minLon
						if bboxMaxLon >= self.maxLon:
							bboxMaxLon = self.maxLon
					else:
						# we are left of E180
						bboxMaxLon = self.maxLon
						if bboxMinLon <= self.minLon:
							bboxMinLon = self.minLon
				else:
					if bboxMinLon <= self.minLon:
						bboxMinLon = self.minLon
					if bboxMaxLon >= self.maxLon:
						bboxMaxLon = self.maxLon
				if bboxMinLat <= self.minLat:
					bboxMinLat = self.minLat
				if bboxMaxLat >= self.maxLat:
					bboxMaxLat = self.maxLat
				minLonTruncIndex = int((bboxMinLon-self.minLon) /
					(self.maxLon-self.minLon) / self.lonIncrement)
				minLatTruncIndex = -1*int((bboxMinLat-self.minLat) /
					(self.maxLat-self.minLat) / self.latIncrement)
				maxLonTruncIndex = int((bboxMaxLon-self.maxLon) /
					(self.maxLon-self.minLon) / self.lonIncrement)
				maxLatTruncIndex = -1*int((bboxMaxLat-self.maxLat) /
					(self.maxLat-self.minLat) / self.latIncrement)
				realMinLon = self.minLon + minLonTruncIndex*self.lonIncrement
				realMinLat = self.minLat - minLatTruncIndex*self.latIncrement
				realMaxLon = self.maxLon + maxLonTruncIndex*self.lonIncrement
				realMaxLat = self.maxLat - maxLatTruncIndex*self.latIncrement
				if maxLonTruncIndex == 0:
					maxLonTruncIndex = None
				if minLatTruncIndex == 0:
					minLatTruncIndex = None
				zData = inputData[maxLatTruncIndex:minLatTruncIndex,
					minLonTruncIndex:maxLonTruncIndex]
				return (realMinLon, realMinLat, realMaxLon, realMaxLat), zData
			else:
				return (self.minLon, self.minLat, self.maxLon, self.maxLat), inputData

		def chopData(inputBbox, inputData):
			"""chops data and appends chops to tiles if small enough.
			"""

			def estimNumOfNodes(data):
				"""simple estimation of the number of nodes. The number of nodes is
				estimated by summing over all absolute differences of contiguous
				points in the zData matrix which is previously divided by the step
				size.

				This method works pretty well in areas with no voids (e. g. points
				tagged with the value -32768 (-0x8000)), but overestimates the number of points
				in areas with voids by approximately 0 ... 50 % although the
				corresponding differences are explicitly set to 0.
				"""
				# get rid of the void mask values
				# the next line is obsolete since voids are now generally masked by nans
				helpData = numpy.where(data==-0x8000, float("NaN"), data) / step
				xHelpData = numpy.abs(helpData[:,1:]-helpData[:,:-1])
				yHelpData = numpy.abs(helpData[1:,:]-helpData[:-1,:])
				xHelpData = numpy.where(xHelpData!=xHelpData, 0, xHelpData).sum()
				yHelpData = numpy.where(yHelpData!=yHelpData, 0, yHelpData).sum()
				estimatedNumOfNodes = xHelpData + yHelpData
				return estimatedNumOfNodes

			def tooManyNodes(data):
				"""returns True if the estimated number of nodes is greater than
				<maxNodes> and False otherwise.  <maxNodes> defaults to 1000000,
				which is an approximate limit for correct handling of osm files
				in mkgmap.  A value of 0 means no tiling.
				"""
				if maxNodes == 0:
					return False
				if estimNumOfNodes(data) > maxNodes:
					return True
				else:
					return False

			def getChops(unchoppedData, unchoppedBbox):
				"""returns a data chop and the according bbox. This function is
				recursively called until all tiles are estimated to be small enough.

				One could cut the input data either horizonally or vertically depending
				on the shape of the input data in order to achieve more quadratic tiles.
				However, generating contour lines from horizontally cut data appears to be
				significantly faster.
				"""
				"""
				if unchoppedData.shape[0] > unchoppedData.shape[1]:
					# number of rows > number of cols, horizontal cutting
				"""
				(unchoppedBboxMinLon, unchoppedBboxMinLat, unchoppedBboxMaxLon,
					unchoppedBboxMaxLat) = unchoppedBbox
				unchoppedNumOfRows = unchoppedData.shape[0]
				chopLatIndex = int(unchoppedNumOfRows/2.0)
				chopLat = unchoppedBboxMaxLat - (chopLatIndex*self.latIncrement)
				lowerChopBbox = (unchoppedBboxMinLon, unchoppedBboxMinLat,
					unchoppedBboxMaxLon, chopLat)
				upperChopBbox = (unchoppedBboxMinLon, chopLat,
					unchoppedBboxMaxLon, unchoppedBboxMaxLat)
				lowerChopData = unchoppedData[chopLatIndex:,:]
				upperChopData = unchoppedData[:chopLatIndex+1,:]
				return (lowerChopBbox, lowerChopData), (upperChopBbox,
					upperChopData)
				"""
				else:
					# number of cols > number of rows, vertical cutting
					unchoppedNumOfCols = unchoppedData.shape[1]
					chopLonIndex = int(unchoppedNumOfCols/2.0)
					chopLon = unchoppedBboxMinLon + (chopLonIndex*self.lonIncrement)
					leftChopBbox = (unchoppedBboxMinLon, unchoppedBboxMinLat,
						chopLon, unchoppedBboxMaxLat)
					rightChopBbox = (chopLon, unchoppedBboxMinLat,
						unchoppedBboxMaxLon, unchoppedBboxMaxLat)
					leftChopData = unchoppedData[:,:chopLonIndex+1]
					rightChopData = unchoppedData[:,chopLonIndex:]
					return (leftChopBbox, leftChopData), (rightChopBbox,
						rightChopData)
				"""

			if tooManyNodes(inputData):
				chops = getChops(inputData, inputBbox)
				for choppedBbox, choppedData  in chops:
					chopData(choppedBbox, choppedData)
			else:
				if self.polygon:
					tileXData = numpy.arange(inputBbox[0],
						inputBbox[2]+self.lonIncrement/2.0, self.lonIncrement)
					tileYData = numpy.arange(inputBbox[3],
						inputBbox[1]-self.latIncrement/2.0, -self.latIncrement)
					tileMask = polygonMask(tileXData, tileYData, self.polygon)
					tilePolygon = self.polygon
					if not numpy.any(tileMask):
						# all points are inside the polygon
						tilePolygon = None
					elif numpy.all(tileMask):
						# all elements are masked -> tile is outside of self.polygon
						return
				else:
					tilePolygon = None
					tileMask = None
				voidMaskValues = numpy.unique(inputData.mask)
				if len(voidMaskValues)==1 and voidMaskValues[0]==True:
					# this tile is full of void values, so discard this tile
					return
				else:
					tiles.append(hgtTile({"bbox": inputBbox, "data": inputData,
						"increments": (self.lonIncrement, self.latIncrement),
						"polygon": tilePolygon, "mask": tileMask}))
					
		tiles = []
		bbox, truncatedData = truncateData(area, self.zData)
		chopData(bbox, truncatedData)
		return tiles


class hgtTile:
	"""is a handle for hgt data tiles as generated by hgtFile.makeTiles().
	"""

	def __init__(self, tile):
		"""initializes tile-specific variables. The minimum elevation is stored in
		self.minEle, the maximum elevation in self.maxEle.
		"""
		self.minLon, self.minLat, self.maxLon, self.maxLat = tile["bbox"]
		self.zData = tile["data"]
		# initialize lists for longitude and latitude data
		self.numOfRows = self.zData.shape[0]
		self.numOfCols = self.zData.shape[1]
		self.lonIncrement, self.latIncrement = tile["increments"]
		self.polygon = tile["polygon"]
		self.mask = tile["mask"]
		self.xData = numpy.arange(self.numOfCols) * self.lonIncrement + self.minLon
		self.yData = numpy.arange(self.numOfRows) * self.latIncrement * -1 + self.maxLat
		self.minEle, self.maxEle = self.getElevRange()

	def printStats(self):
		"""prints some statistics about the tile.
		"""
		print "\ntile with %i x %i points, bbox: (%.2f, %.2f, %.2f, %.2f)"%(
			self.numOfRows, self.numOfCols, self.minLon, self.minLat, self.maxLon,
			self.maxLat)
		print "minimum elevation: %i"%self.minEle
		print "maximum elevation: %i"%self.maxEle

	def getElevRange(self):
		"""returns minEle, maxEle of the current tile.
		"""
		maxEle = self.zData.max()
		helpData = self.zData.flatten()
		helpData.sort()
		for zValue in helpData:
			if zValue != -0x8000:
				minEle = zValue
				break
		else:
			minEle = maxEle
		return minEle, maxEle

	def bbox(self):
		"""returns the bounding box of the current tile.
		"""
		return  self.minLon, self.minLat, self.maxLon, self.maxLat

	def contourLines(self, stepCont=20, maxNodesPerWay=0, noZero=False,
		minCont=None, maxCont=None):
		"""generates contour lines using matplotlib.

		<stepCont> is height difference of contiguous contour lines in meters
		<maxNodesPerWay>:  the maximum number of nodes contained in each way
		<noZero>:  if True, the 0 m contour line is discarded
		<minCont>:  lower limit of the range to generate contour lines for
		<maxCont>:  upper limit of the range to generate contour lines for

		A list of elevations and a ContourObject is returned.
		"""
		def getContLimit(ele, step):
			"""returns a proper value for the lower or upper limit to generate contour
			lines for.
			"""
			if ele%step == 0:
				return ele
			corrEle = ele + step - ele % step
			return corrEle

		minCont = minCont or getContLimit(self.minEle, stepCont)
		maxCont = maxCont or getContLimit(self.maxEle, stepCont)
		contourSet = []
		if noZero:
			levels = [l for l in range(int(minCont), int(maxCont), stepCont) if l!=0]
		else:
			levels = range(int(minCont), int(maxCont), stepCont)
		x, y = numpy.meshgrid(self.xData, self.yData)
		# z data is a masked array filled with nan.
		z = numpy.ma.array(self.zData, mask=self.mask, fill_value=float("NaN"),
			keep_mask=True)
		Contours = ContourObject(_cntr.Cntr(x, y, z.filled(), None), maxNodesPerWay,
			self.polygon)
		return levels, Contours

	def countNodes(self, maxNodesPerWay=0, stepCont=20, minCont=None,
		maxCont=None):
		"""counts the total number of nodes and paths in the current tile
		as written to output.

		<maxNodesPerWay> is the maximal number of nodes per way or 0 for uncut ways
		<stepCont> is height difference of contiguous contour lines in meters
		<minCont>:  lower limit of the range to generate contour lines for
		<maxCont>:  upper limit of the range to generate contour lines for
		"""
		if not (self.elevations and self.contourData):
			elevations, contourData = self.contourLines(stepCont, maxNodesPerWay,
				minCont, maxCont)
		else:
			elevations, contourData = self.elevations, self.contourData
		numOfNodesWays = [contourData.trace(e)[1:] for e in elevations]
		numOfNodes = sum([n for n, w in numOfNodesWays])
		numOfWays = sum([w for n, w in numOfNodesWays])
		return numOfNodes, numOfWays

	def plotData(self, plotPrefix='heightPlot'):
		"""generates plot data in the file specified by <plotFilename>.
		"""
		filename = makeBBoxString(self.bbox())%(plotPrefix+"_") + ".xyz"
		try:
			plotFile = open(filename, 'w')
		except:
			raise IOError("could not open plot file %s for writing"%plotFilename)
		for latIndex, row in enumerate(self.zData):
			lat = self.maxLat - latIndex*self.latIncrement
			for lonIndex, height in enumerate(row):
				lon = self.minLon + lonIndex*self.lonIncrement
				plotFile.write("%.7f %.7f %i\n"%(lon, lat, height))

