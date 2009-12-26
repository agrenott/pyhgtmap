import os
import matplotlib
matplotlib.use("AGG")  # don't require a display.
import matplotlib.pyplot as plt
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

class hgtFile:
	"""is a handle for SRTM data files
	"""

	def __init__(self, filename):
		"""tries to open <filename> and extracts content to self.zData.
		
		An area as passed as option to phyghtmap.py may be passed as <area>.
		"""
		self.fullFilename = filename
		self.filename = os.path.split(filename)[-1]
		# SRTM hgt files seem to contain 1201x1201 points;
		# however, we try to determine the real number of points.
		# Height data are stored as 2-byte signed integers, the byte order is
		# big-endian standard. The data are stored in a row major order.
		# All height data are in meters referenced to the WGS84/EGM96 geoid as
		# documented at http://www.nga.mil/GandG/wgsegm/.
		try:
			numOfDataPoints = os.path.getsize(self.fullFilename) / 2
			self.numOfRows = self.numOfCols = int(numOfDataPoints ** 0.5)
			self.zData = numpy.fromfile(self.fullFilename,
				dtype=">i2").reshape(self.numOfRows, self.numOfCols)
		finally:
			self.lonIncrement = 1.0/(self.numOfCols-1)
			self.latIncrement = 1.0/(self.numOfRows-1)
			self.minLon, self.minLat, self.maxLon, self.maxLat = self.borders()
		# some statistics
		print 'hgt file %s: %i x %i points, bbox: (%i, %i, %i, %i)'%(self.fullFilename,
			self.numOfCols, self.numOfRows, self.minLon, self.minLat, self.maxLon,
			self.maxLat)

	def borders(self):
		"""tries to extract borders from self.filename and returns them as a tuple
		of integers:
		(<min longitude>, <min latitude>, <max longitude>, <max latitude>)

		Longitudes of west as well as latitudes of south are given as negative
		values.
		"""
		latSwitch = self.filename[0:1]
		latValue  = self.filename[1:3]
		lonSwitch = self.filename[3:4]
		lonValue  = self.filename[4:7]		

		if latSwitch == 'N':
			minLat = int(latValue)
		elif latSwitch == 'S':
			minLat = -1 * int(latValue)
		else:
			raise IOError("something wrong with latSwitch %s"%latSwitch)
		maxLat = minLat + 1

		if lonSwitch == 'E':
			minLon = int(lonValue)
		elif lonSwitch == 'W':
			minLon = -1 * int(lonValue)
		else:
			raise filenameError("something wrong with lonSwitch %s"%lonSwitch)
		maxLon = minLon + 1
		return minLon, minLat, maxLon, maxLat


	def makeTiles(self, opts):
		"""generate tiles from self.zData according to the given <area> and
		return them as list of hgtTile objects.
		"""
		area = opts.area or None
		step = int(opts.contourStepSize) or 20

		def truncateData(area, inputData):
			"""truncates a numpy array.
			returns (<min lon>, <min lat>, <max lon>, <max lat>) and an array of the
			truncated height data.
			"""
			if area:
				bboxMinLon, bboxMinLat, bboxMaxLon, bboxMaxLat = (float(bound)
					for bound in area.split(":"))
				if bboxMinLon <= self.minLon:
					bboxMinLon = self.minLon
				if bboxMinLat <= self.minLat:
					bboxMinLat = self.minLat
				if bboxMaxLon >= self.maxLon:
					bboxMaxLon = self.maxLon
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
				tagged with the value -32768), but overestimates the number of points
				in areas with voids by approximately 0 ... 50 % although the
				corresponding differences are explicitly set to 0.
				"""
				helpData = numpy.where(data==-32768, 0, data) / step
				xHelpData = numpy.abs(helpData[:,1:]-helpData[:,:-1])
				yHelpData = numpy.abs(helpData[1:,:]-helpData[:-1,:])
				xHelpData = numpy.where(xHelpData > 30000/step, 0, xHelpData).sum()
				yHelpData = numpy.where(yHelpData > 30000/step, 0, yHelpData).sum()
				estimatedNumOfNodes = xHelpData + yHelpData
				return estimatedNumOfNodes

			def tooManyNodes(data):
				"""returns True if the estimated number of nodes is greater than
				1000000, which is an approximate limit for correct handling of osm files
				in mkgmap, and False otherwise.
				"""
				if estimNumOfNodes(data) > 1000000:
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
				tiles.append(hgtTile({"bbox": inputBbox, "data": inputData,
					"increments": (self.lonIncrement, self.latIncrement)}))
					
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
		self.xData = numpy.array(range(self.numOfCols)) * self.lonIncrement + self.minLon
		self.yData = numpy.array(range(self.numOfRows)) * self.latIncrement * -1 + self.maxLat
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
			if zValue != -32768:
				minEle = zValue
				break
		return minEle, maxEle

	def bbox(self):
		"""returns the bounding box of the current tile.
		"""
		return  self.minLon, self.minLat, self.maxLon, self.maxLat

	def contourLines(self, stepCont=20, minCont=None, maxCont=None):
		"""generates contour lines using matplotlib.

		<stepCont> is height difference of contiguous contour lines in meters
		<minCont>:  lower limit of the range to generate contour lines for
		<maxCont>:  upper limit of the range to generate contour lines for

		A list of matplotlib.contour.ContourSet objects is returned.
		"""
		def getContLimit(ele, step):
			"""returns a proper value for the lower or upper limit to generate contour
			lines for.
			"""
			corrEle = ele + step - ele % step
			return corrEle

		minCont = minCont or getContLimit(self.minEle, stepCont)
		maxCont = maxCont or getContLimit(self.maxEle, stepCont)
		#self.printStats()
		contourSet = plt.contour(self.xData, self.yData, self.zData,
			range(minCont, maxCont, stepCont))
		plt.close('all')
		return contourSet

	def countNodes(self, stepCont=20, minCont=None, maxCont=None):
		"""returns the total number of nodes and paths in the current tile.

		<stepCont> is height difference of contiguous contour lines in meters
		<minCont>:  lower limit of the range to generate contour lines for
		<maxCont>:  upper limit of the range to generate contour lines for
		"""
		numOfNodes = 0
		numOfPaths = 0
		contourData = self.contourLines(stepCont, minCont, maxCont)
		for level in contourData.collections:
			for path in level.get_paths():
				numOfPaths += 1
				numOfNodes += len(path)
				if numpy.all(path.vertices[0]==path.vertices[-1]):
					numOfNodes -= 1
		return numOfNodes, numOfPaths

	def plotData(self, plotFilename='heightPlot.xyz'):
		"""generates plot data in the file specified by <plotFilename>.
		"""
		try:
			plotFile = open(plotFilename, 'w')
		except:
			raise IOError("could not open plot file %s for writing"%plotFilename)
		for latIndex, row in enumerate(self.zData):
			lat = self.maxLat - latIndex*self.latIncrement
			for lonIndex, height in enumerate(row):
				lon = self.minLon + lonIndex*self.lonIncrement
				plotFile.write("%.7f %.7f %i\n"%(lon, lat, height))

