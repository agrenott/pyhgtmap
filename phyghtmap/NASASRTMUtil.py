import urllib
import os
from BeautifulSoup import BeautifulSoup
import zipfile

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
	
def makeFileNamePrefixes(bbox, lowercase=False):
	"""generates a list of filename prefixes of the files containing data within the
	bounding box.
	"""
	minLon, minLat, maxLon, maxLat = bbox
	lon = minLon
	prefixes = []
	while lon <= maxLon:
		if lon < 0:
			lonSwitch = "W"
		else:
			lonSwitch = "E"
		lat = minLat
		while lat <= maxLat:
			if lat < 0:
				latSwitch = "S"
			else:
				latSwitch = "N"
			prefixes.append("%s%s%s%s"%(latSwitch, str(abs(lat)).rjust(2, '0'),
				lonSwitch, str(abs(lon)).rjust(3, '0')))
			lat += 1
			if minLat == maxLat or lat == maxLat:
				break
		lon += 1
		if minLon == maxLon or lon == maxLon:
			break
	if lowercase:
		return [p.lower() for p in prefixes]
	else:
		return prefixes

def makeFileNames(bbox, resolution, viewfinder):
	"""generates a list of filenames of the files containing data within the
	bounding box.  If <viewfinder> exists, this data is preferred to NASA SRTM
	data.
	"""
	areas = makeFileNamePrefixes(bbox)
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
	print "generating index in %s ..."%hgtIndexFile
	try:
		index = open(hgtIndexFile, 'w')
	except:
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
	print "generating index in %s ..."%hgtIndexFile
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

def unzipFile(saveZipFilename):
	"""unzip a zip file.
	"""
	print "unzipping file %s ..."%saveZipFilename
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
	print "DONE"
	return areaNames

def getFiles(area, corrx, corry, resolution, viewfinder=0):
	NASAhgtSaveSubDir = os.path.join(hgtSaveDir, NASAhgtSaveSubDirRe%resolution)
	VIEWhgtSaveSubDir = os.path.join(hgtSaveDir, VIEWhgtSaveSubDirRe%viewfinder)
	try:
		os.stat(hgtSaveDir)
	except:
		os.mkdir(hgtSaveDir)
	try:
		os.stat(NASAhgtSaveSubDir)
	except:
		os.mkdir(NASAhgtSaveSubDir)
	if viewfinder:
		try:
			os.stat(VIEWhgtSaveSubDir)
		except:
			os.mkdir(VIEWhgtSaveSubDir)
	bbox = calcBbox(area, corrx, corry)
	filesToDownload = makeFileNames(bbox, resolution, viewfinder)	
	files = []
	for area, url in sorted(filesToDownload.items()):
		if not url:
			print "no file for area %s found on server."%area
			continue
		if "viewfinderpanoramas" in url:
			if not inViewIndex(viewfinder, area):
				# we dynamically update the viewfinder index, so always check this here
				continue
			hgtSaveSubDir = VIEWhgtSaveSubDir
			fileResolution = viewfinder
		else:
			hgtSaveSubDir = NASAhgtSaveSubDir
			fileResolution = resolution
		saveZipFilename = os.path.join(hgtSaveSubDir, url.split("/")[-1])
		saveFilename = os.path.join(hgtSaveSubDir, "%s.hgt"%area)
		try:
			os.stat(saveFilename)
			wantedSize = 2 * (3600/fileResolution + 1)**2
			foundSize = os.path.getsize(saveFilename)
			if foundSize != wantedSize:
				raise IOError("Wrong size: Expected %i, found %i"(wantedSize,foundSize))
			print "found existing file %s."%saveFilename
		except:
			try:
				os.stat(saveZipFilename)
				areaNames = unzipFile(saveZipFilename)
				if "viewfinderpanoramas" in url:
					updateViewIndex(viewfinder, url, areaNames)
			except:
				print "downloading file %s to %s ..."%(url, saveZipFilename)
				urllib.urlretrieve(url, filename=saveZipFilename)
				try:
					areaNames = unzipFile(saveZipFilename)
					if "viewfinderpanoramas" in url:
						updateViewIndex(viewfinder, url, areaNames)
				except Exception, msg:
					print msg
					print "file %s from %s is not a zip file"%(saveZipFilename, url)
		try:
			os.stat(saveFilename)
			wantedSize = 2 * (3600/fileResolution + 1)**2
			foundSize = os.path.getsize(saveFilename)
			if foundSize != wantedSize:
				raise IOError("Wrong size: Expected %i, found %i"(wantedSize,foundSize))
			files.append(saveFilename)
		except Exception, msg:
			print msg
	return files

