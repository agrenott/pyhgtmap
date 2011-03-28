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


def calcBbox(area):
	"""calculates the appropriate bouding box for the needed files
	"""
	minLon, minLat, maxLon, maxLat = [float(value) for value in area.split(":")]
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

def makeViewHgtIndex(resolution):
	"""generates an index file for the viewfinder hgt files.
	"""
	hgtIndexFile = VIEWhgtIndexFileRe%resolution
	hgtFileServer = NASAhgtFileServerRe%resolution
	print "generating index in %s ..."%hgtIndexFile
	try:
		index = open(hgtIndexFile, 'w')
	except:
		raise IOError("could not open %s for writing"%hgtIndexFile)
	hgtDictUrl = VIEWfileDictPageRe%resolution
	areaDict = dict([(a["title"], a["href"]) for a in
		BeautifulSoup(urllib.urlopen(hgtDictUrl).read()).findAll("area")])
	zipFileDict = {}
	for areaName, zipFileUrl in areaDict.items():
		if not zipFileDict.has_key(zipFileUrl):
			zipFileDict[zipFileUrl] = []
		zipFileDict[zipFileUrl].append(areaName.upper())
	for zipFileUrl in sorted(zipFileDict):
		index.write("[%s]\n"%zipFileUrl)
		for areaName in zipFileDict[zipFileUrl]:
			index.write(areaName + "\n")
	index.close()
	print "DONE"

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
		if line.startswith("["):
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
	for name in zipFile.namelist():
		areaName = os.path.splitext(os.path.split(name)[-1])[0].upper().strip()
		if not areaName:
			continue
		saveFilename = os.path.join(os.path.split(saveZipFilename)[0],
			areaName + ".hgt")
		saveFile = open(saveFilename, 'wb')
		saveFile.write(zipFile.read(name))
		saveFile.close()
	os.remove(saveZipFilename)
	print "DONE"

def getFiles(area, resolution, viewfinder=False):
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
	try:
		os.stat(VIEWhgtSaveSubDir)
	except:
		os.mkdir(VIEWhgtSaveSubDir)
	bbox = calcBbox(area)
	#print bbox
	filesToDownload = makeFileNames(bbox, resolution, viewfinder)	
	files = []
	for area, url in sorted(filesToDownload.items()):
		if not url:
			print "no file for area %s found on server."%area
			continue
		if "viewfinderpanoramas" in url:
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
				unzipFile(saveZipFilename)
			except:
				print "downloading file %s to %s ..."%(url, saveZipFilename)
				urllib.urlretrieve(url, filename=saveZipFilename)
				try:
					unzipFile(saveZipFilename)
				except:
					print "file %s from %s is not a zip file"%(saveZipFilename, url)
		try:
			os.stat(saveFilename)
			files.append(saveFilename)
		except:
			pass
	return files

