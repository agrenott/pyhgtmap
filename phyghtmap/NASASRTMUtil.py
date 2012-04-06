import urllib
import os
from BeautifulSoup import BeautifulSoup
import zipfile
from matplotlib.nxutils import points_inside_poly
import numpy

############################################################
### general vriables #######################################
############################################################

hgtSaveDir = "hgt"

############################################################
### NASA SRTM specific variables ###########################
############################################################

NASAhgtFileServerRe = "http://dds.cr.usgs.gov/srtm/version2_1/SRTM%s"
NASAhgtFileDirs = {3: ["Africa", "Australia", "Eurasia", "Islands", "North_America",
               "South_America"],
               1: ["Region_0%i"%i for i in range(1, 8)]}

NASAhgtSaveSubDirRe = "SRTM%i"
NASAhgtIndexFileRe = os.path.join(hgtSaveDir, "hgtIndex_%i.txt")

############################################################
### www.vierfinderpanoramas.org specific variables #########
############################################################

VIEWfileDictPageRe = "http://www.viewfinderpanoramas.org/Coverage%%20map%%20viewfinderpanoramas_org%i.htm"

VIEWhgtSaveSubDirRe = "VIEW%i"
VIEWhgtIndexFileRe = os.path.join(hgtSaveDir, "viewfinderHgtIndex_%i.txt")

texAreas = []

def calcBbox(area, corrx=0.0, corry=0.0):
	"""calculates the appropriate bouding box for the needed files
	"""
	minLon, minLat, maxLon, maxLat = [float(value)-inc for value, inc in
		zip(area.split(":"), [corrx, corry, corrx, corry])]
	if minLon < 0:
		if minLon % 1 == 0:
			bboxMinLon = int(minLon)
		else:
			bboxMinLon = int(minLon) - 1
	else:
		bboxMinLon = int(minLon)
	if minLat < 0:
		if minLat % 1 == 0:
			bboxMinLat = int(minLat)
		else:
			bboxMinLat = int(minLat) - 1
	else:
		bboxMinLat = int(minLat)
	if maxLon < 0:
		bboxMaxLon = int(maxLon)
	else:
		if maxLon % 1 == 0:
			bboxMaxLon = int(maxLon)
		else:
			bboxMaxLon = int(maxLon) + 1
	if maxLat < 0:
		bboxMaxLat = int(maxLat)
	else:
		if maxLat % 1 == 0:
			bboxMaxLat = int(maxLat)
		else:
			bboxMaxLat = int(maxLat) + 1
	return bboxMinLon, bboxMinLat, bboxMaxLon, bboxMaxLat

"""
def writeTex(milo, mila, malo, mala, color):
	texAreas.append("%s/%.2f/%-2f/%.2f/%.2f"%(
		color, milo, mila, malo, mala))
"""

def getLowInt(n):
	if n%1==0:
		return int(n)
	if n < 0:
		return int(n)-1
	else:
		return int(n)

def getHighInt(n):
	if n < 0 or n%1==0:
		return int(n)
	else:
		return int(n)+1

def getRange(a, b):
	a, b = sorted([a, b])
	l, h = getHighInt(a), getHighInt(b)
	return range(l, h)

def intersecTiles(polygonList, corrx, corry):
	if not polygonList:
		return []
	secs = []
	for polygon in polygonList:
		x_last, y_last = polygon[0]
		x_last -= corrx
		y_last -= corry
		for x, y in polygon[1:]:
			x -= corrx
			y -= corry
			secs.append((getLowInt(x), getLowInt(y)))
			if x-x_last == 0:
				# vertical vertex, don't calculate s
				secs.extend([(getLowInt(x), getLowInt(Y)) for Y in getRange(
					y, y_last)])
			elif y-y_last == 0:
				# horizontal vertex
				secs.extend([(getLowInt(X), getLowInt(y)) for X in getRange(
					x, x_last)])
			else:
				s = (y-y_last)/(x-x_last)
				o = y_last-x_last*s
				for X in getRange(x, x_last):
					# determine intersections with latitude degrees
					Y = getLowInt(s*X+o)
					secs.append((X-1, Y)) # left
					secs.append((X, Y)) # right
				for Y in getRange(y, y_last):
					# determine intersections with longitude degrees
					X = getLowInt((Y-o)/s)
					secs.append((X, Y-1)) # below
					secs.append((X, Y)) # above
			x_last, y_last = x, y
	return [makeFileNamePrefix(x, y) for x, y in set(secs)]

def areaNeeded(lat, lon, bbox, polygon, corrx, corry):
	"""checks if a source file is needed depending on the bounding box and
	the passed polygon.
	"""
	if polygon==None:
		return True
	minLat = lat + corry
	maxLat = minLat + 1
	minLon = lon + corrx
	maxLon = minLon + 1
	MinLon, MinLat, MaxLon, MaxLat = bbox
	MinLon += corrx
	MaxLon += corrx
	MinLat += corry
	MaxLat += corry
	print "checking if area %s intersects with polygon ..."%(
		makeFileNamePrefix(lon, lat)),
	if minLon==MinLon and minLat==MinLat and maxLon==MaxLon and maxLat==MaxLat:
		# the polygon is completely inside the bounding box
		print "yes"
		#writeTex(lon, lat, lon+1, lat+1, "green")
		return True
	# the area is not or completely inside one of the polygons passed to
	# <polygon>.  We just look if the corners are inside the polygons.
	points = []
	for lo in [minLon, maxLon]:
		for la in [minLat, maxLat]:
			points.append((lo, la))
	inside = numpy.zeros((1, 4))
	for p in polygon:
		inside += points_inside_poly(points, p)
	if numpy.all(inside):
		print "yes"
		#writeTex(lon, lat, lon+1, lat+1, "green")
		return True
	elif not numpy.any(inside):
		print "no"
		#writeTex(lon, lat, lon+1, lat+1, "red")
		return False
	else:
		# This only happens it a polygon vertex is on the tile border.
		# Because in this case points_inside_poly() returns unpredictable
		# results, we better return True here.
		print "maybe"
		#writeTex(lon, lat, lon+1, lat+1, "pink")
		return True

def makeFileNamePrefix(lon, lat):
	if lon < 0:
		lonSwitch = "W"
	else:
		lonSwitch = "E"
	if lat < 0:
		latSwitch = "S"
	else:
		latSwitch = "N"
	return "%s%s%s%s"%(latSwitch, str(abs(lat)).rjust(2, '0'),
		lonSwitch, str(abs(lon)).rjust(3, '0'))

def makeFileNamePrefixes(bbox, polygon, corrx, corry, lowercase=False):
	"""generates a list of filename prefixes of the files containing data within the
	bounding box.
	"""
	minLon, minLat, maxLon, maxLat = bbox
	lon = minLon
	intersecAreas = intersecTiles(polygon, corrx, corry)
	prefixes = []
	if minLon > maxLon:
		# bbox covers the W180/E180 longitude
		lonRange = range(minLon, 180) + range(-180, maxLon)
	else:
		lonRange = range(minLon, maxLon)
	for lon in lonRange:
		for lat in range(minLat, maxLat):
			fileNamePrefix = makeFileNamePrefix(lon, lat)
			if fileNamePrefix in intersecAreas:
				prefixes.append(fileNamePrefix)
				#writeTex(lon, lat, lon+1, lat+1, "blue")
			elif areaNeeded(lat, lon, bbox, polygon, corrx, corry):
				prefixes.append(fileNamePrefix)
	if lowercase:
		return [p.lower() for p in prefixes]
	else:
		return prefixes

def makeFileNames(bbox, polygon, corrx, corry, resolution, viewfinder):
	"""generates a list of filenames of the files containing data within the
	bounding box.  If <viewfinder> exists, this data is preferred to NASA SRTM
	data.
	"""
	areas = makeFileNamePrefixes(bbox, polygon, corrx, corry)
	areaDict = {}
	for a in areas:
		NASAurl = getNASAUrl(a, resolution)
		areaDict[a] = NASAurl
	if viewfinder:
		for a in areas:
			VIEWurl = getViewUrl(a, viewfinder)
			if not VIEWurl:
				continue
			areaDict[a] = VIEWurl
	return areaDict

def makeNasaHgtIndex(resolution):
	"""generates an index file for the NASA SRTM server.
	"""
	hgtIndexFile = NASAhgtIndexFileRe%resolution
	hgtFileServer = NASAhgtFileServerRe%resolution
	print "generating index in %s ..."%hgtIndexFile, 
	try:
		index = open(hgtIndexFile, 'w')
	except:
		print ""
		raise IOError("could not open %s for writing"%hgtIndexFile)
	for continent in NASAhgtFileDirs[resolution]:
		index.write("[%s]\n"%continent)
		url = "/".join([hgtFileServer, continent])
		continentHtml = urllib.urlopen(url)
		continentSoup = BeautifulSoup(continentHtml)
		anchors = continentSoup.findAll("a")
		for anchor in anchors:
			if anchor.contents[0].endswith(".hgt.zip"):
				zipFilename = anchor.contents[0].strip()
				index.write("%s\n"%zipFilename)
	print "DONE"

def writeViewIndex(resolution, zipFileDict):
	hgtIndexFile = VIEWhgtIndexFileRe%resolution
	try:
		index = open(hgtIndexFile, 'w')
	except:
		print ""
		raise IOError("could not open %s for writing"%hgtIndexFile)
	for zipFileUrl in sorted(zipFileDict):
		index.write("[%s]\n"%zipFileUrl)
		for areaName in zipFileDict[zipFileUrl]:
			index.write(areaName + "\n")
	index.close()
	print "DONE"

def inViewIndex(resolution, areaName):
	hgtIndexFile = VIEWhgtIndexFileRe%resolution
	index = [line.strip() for line in open(hgtIndexFile, 'r').read().split("\n")
		if line.strip()]
	areaNames = [a for a in index if not a.startswith("[")]
	if areaName in areaNames:
		return True
	else:
		return False

def makeViewHgtIndex(resolution):
	"""generates an index file for the viewfinder hgt files.
	"""
	def calcAreaNames(coordTag):
		viewfinderGraphicsDimension = 2000.0/360.0
		l, t, r, b = [int(c) for c in coordTag.split(",")]
		w = int(l / viewfinderGraphicsDimension + 0.5) - 180
		e = int(r / viewfinderGraphicsDimension + 0.5) - 180
		s = 90 - int(b / viewfinderGraphicsDimension + 0.5)
		n = 90 - int(t / viewfinderGraphicsDimension + 0.5)
		names = []
		for lon in range(w, e):
			for lat in range(s, n):
				if lon < 0:
					lonName = "W%s"%(str(-lon).rjust(3, "0"))
				else:
					lonName = "E%s"%(str(lon).rjust(3, "0"))
				if s < 0:
					latName = "S%s"%(str(-lat).rjust(2, "0"))
				else:
					latName = "N%s"%(str(lat).rjust(2, "0"))
				name = "".join([latName, lonName])
				names.append(name)
		return names

	hgtIndexFile = VIEWhgtIndexFileRe%resolution
	hgtFileServer = NASAhgtFileServerRe%resolution
	hgtDictUrl = VIEWfileDictPageRe%resolution
	areaDict = {}
	for a in BeautifulSoup(urllib.urlopen(hgtDictUrl).read()).findAll("area"):
		areaNames = calcAreaNames(a["coords"])
		for areaName in areaNames:
			areaDict[areaName] = a["href"].strip()
	zipFileDict = {}
	for areaName, zipFileUrl in sorted(areaDict.items()):
		if not zipFileDict.has_key(zipFileUrl):
			zipFileDict[zipFileUrl] = []
		zipFileDict[zipFileUrl].append(areaName.upper())
	print "generating index in %s ..."%hgtIndexFile,
	writeViewIndex(resolution, zipFileDict)

def updateViewIndex(resolution, zipFileUrl, areaList):
	"""cleans up the viewfinder index.
	"""
	hgtIndexFile = VIEWhgtIndexFileRe%resolution
	try:
		os.stat(hgtIndexFile)
	except:
		print "Cannot update index file %s because it's not there."%hgtIndexFile
		return
	index = [line.strip() for line in open(hgtIndexFile, 'r').read().split("\n")
		if line.strip()]
	zipFileDict = {}
	for line in index:
		if line.startswith("["):
			url = line[1:-1]
			if not zipFileDict.has_key(url):
				zipFileDict[url] = []
		else:
			zipFileDict[url].append(line)
	if not zipFileDict.has_key(zipFileUrl):
		print "No such url in zipFileDict: %s"%zipFileUrl
		return
	if sorted(zipFileDict[zipFileUrl]) != sorted(areaList):
		zipFileDict[zipFileUrl] = sorted(areaList)
		print "updating index in %s ..."%hgtIndexFile
		writeViewIndex(resolution, zipFileDict)

def getNASAUrl(area, resolution):
	"""determines the NASA download url for a given area.
	"""
	file = "%s.hgt.zip"%area
	hgtIndexFile = NASAhgtIndexFileRe%resolution
	hgtFileServer = NASAhgtFileServerRe%resolution
	try:
		os.stat(hgtIndexFile)
	except:
		makeNasaHgtIndex(resolution)
	index = open(hgtIndexFile, 'r').readlines()
	fileMap = {}
	for line in index:
		line = line.strip()
		if line.startswith("["):
			continent = line[1:-1]
		else:
			fileMap[line] = continent
	if not fileMap.has_key(file):
		return None
	url = '/'.join([hgtFileServer, fileMap[file], file])
	return url

def getViewUrl(area, resolution):
	"""determines the viewfinder download url for a given area.
	"""
	hgtIndexFile = VIEWhgtIndexFileRe%resolution
	try:
		os.stat(hgtIndexFile)
	except:
		makeViewHgtIndex(resolution)
	index = open(hgtIndexFile, 'r').readlines()
	fileMap = {}
	for line in index:
		line = line.strip()
		if line.startswith("[") and line.endswith("]"):
			url = line[1:-1]
		else:
			fileMap[line] = url
	if not fileMap.has_key(area):
		return None
	url = fileMap[area]
	return url

def unzipFile(saveZipFilename, area):
	"""unzip a zip file.
	"""
	print "%s: unzipping file %s ..."%(area, saveZipFilename)
	zipFile = zipfile.ZipFile(saveZipFilename)
	areaNames = []
	for name in zipFile.namelist():
		if os.path.splitext(name)[1].lower() != ".hgt":
			continue
		areaName = os.path.splitext(os.path.split(name)[-1])[0].upper().strip()
		if not areaName:
			continue
		areaNames.append(areaName)
		saveFilename = os.path.join(os.path.split(saveZipFilename)[0],
			areaName + ".hgt")
		saveFile = open(saveFilename, 'wb')
		saveFile.write(zipFile.read(name))
		saveFile.close()
	# destruct zipFile before removing it.  removing otherwise fails under windows
	zipFile.__del__()
	os.remove(saveZipFilename)
	#print "DONE"
	return areaNames

"""
def makePolygonCoords(polygonList):
	pathList = []
	for polygon in polygonList:
		coords = []
		for lon, lat in polygon:
			coords.append("(%.7f, %.7f)"%(lon, lat))
		pathList.append("\\draw[line width=2pt] plot coordinates{%s} --cycle;"%(" ".join(coords)))
	return "\n\t".join(pathList)
"""

def mkdir(dirName):
	try:
		os.stat(dirName)
	except:
		os.mkdir(dirName)

def getDirNames(source):
	resolution = int(source[-1])
	if source.startswith("srtm"):
		hgtSaveSubDir = os.path.join(hgtSaveDir, NASAhgtSaveSubDirRe%resolution)
	elif source.startswith("view"):
		hgtSaveSubDir = os.path.join(hgtSaveDir, VIEWhgtSaveSubDirRe%resolution)
	return hgtSaveDir, hgtSaveSubDir

def initDirs(sources):
	mkdir(hgtSaveDir)
	for source in sources:
		sourceType, sourceResolution = source[:4], int(source[-1])
		if sourceType == "srtm":
			NASAhgtSaveSubDir = os.path.join(hgtSaveDir, NASAhgtSaveSubDirRe%sourceResolution)
			mkdir(NASAhgtSaveSubDir)
		elif sourceType == "view":
			VIEWhgtSaveSubDir = os.path.join(hgtSaveDir, VIEWhgtSaveSubDirRe%sourceResolution)
			mkdir(VIEWhgtSaveSubDir)

def downloadAndUnzip(url, area, source):
	hgtSaveDir, hgtSaveSubDir = getDirNames(source)
	fileResolution = int(source[-1])
	saveZipFilename = os.path.join(hgtSaveSubDir, url.split("/")[-1])
	saveFilename = os.path.join(hgtSaveSubDir, "%s.hgt"%area)
	try:
		os.stat(saveFilename)
		wantedSize = 2 * (3600/fileResolution + 1)**2
		foundSize = os.path.getsize(saveFilename)
		if foundSize != wantedSize:
			raise IOError("Wrong size: Expected %i, found %i"%(wantedSize,foundSize))
		print "%s: using existing file %s."%(area, saveFilename)
		return saveFilename
	except:
		try:
			os.stat(saveZipFilename)
			areaNames = unzipFile(saveZipFilename, area)
			if source.startswith("view"):
				updateViewIndex(fileResolution, url, areaNames)
				if not inViewIndex(fileResolution, area):
					return None
		except:
			print "%s: downloading file %s to %s ..."%(area, url, saveZipFilename)
			urllib.urlretrieve(url, filename=saveZipFilename)
			try:
				areaNames = unzipFile(saveZipFilename, area)
				if source.startswith("view"):
					updateViewIndex(fileResolution, url, areaNames)
					if not inViewIndex(fileResolution, area):
						return None
			except Exception, msg:
				print msg
				print "%s: file %s from %s is not a zip file"%(area, saveZipFilename, url)
	try:
		os.stat(saveFilename)
		wantedSize = 2 * (3600/fileResolution + 1)**2
		foundSize = os.path.getsize(saveFilename)
		if foundSize != wantedSize:
			raise IOError("%s: wrong size: Expected %i, found %i"%(area,
				wantedSize,foundSize))
		print "%s: using file %s."%(area, saveFilename)
		return saveFilename
	except Exception, msg:
		print msg
		return None

def getFile(area, source):
	fileResolution = int(source[-1])
	if source.startswith("srtm"):
		url = getNASAUrl(area, fileResolution)
	elif source.startswith("view"):
		url = getViewUrl(area, fileResolution)
	if not url:
		return None
	else:
		return downloadAndUnzip(url, area, source)

def getFiles(area, polygon, corrx, corry, sources):
	initDirs(sources)
	bbox = calcBbox(area, corrx, corry)
	areaPrefixes = makeFileNamePrefixes(bbox, polygon, corrx, corry)
	files = []
	for area in areaPrefixes:
		for source in sources:
			print "%s: trying %s ..."%(area, source)
			saveFilename = getFile(area, source)
			if saveFilename:
				files.append(saveFilename)
				break
		else:
			print "%s: no file found on server."%area
			continue
	return files

