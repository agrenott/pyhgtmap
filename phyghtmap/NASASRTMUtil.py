import urllib
import os
from BeautifulSoup import BeautifulSoup
import zipfile

hgtFileServer = "http://dds.cr.usgs.gov/srtm/version2_1/SRTM3"
hgtFileDirs = ["Africa", "Australia", "Eurasia", "Islands", "North_America",
               "South_America"]

hgtSaveDir = "hgt"
hgtIndexFile = os.path.join(hgtSaveDir, "hgtIndex.txt")

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
	
def makeFileNames(bbox):
	"""generates a list of filenames of the files containing data within the
	bounding box.
	"""
	minLon, minLat, maxLon, maxLat = bbox
	lon = minLon
	filenames = []
	while lon < maxLon:
		if lon < 0:
			lonSwitch = "W"
		else:
			lonSwitch = "E"
		lat = minLat
		while lat < maxLat:
			if lat < 0:
				latSwitch = "S"
			else:
				latSwitch = "N"
			filenames.append("%s%s%s%s.hgt.zip"%(latSwitch, str(abs(lat)).rjust(2, '0'),
				lonSwitch, str(abs(lon)).rjust(3, '0')))
			lat += 1
		lon += 1
	return filenames

def makeHgtIndex():
	"""generates an index file for the NASA SRTM server.
	"""
	print "generating index in %s ..."%hgtIndexFile
	try:
		index = open(hgtIndexFile, 'w')
	except:
		raise IOError("could not open %s for writing"%hgtIndexFile)
	for continent in hgtFileDirs:
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

def getUrl(file):
	"""determines the download url for a given filename.
	"""
	try:
		os.stat(hgtIndexFile)
	except:
		makeHgtIndex()
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

def unzipFile(saveZipFilename):
	"""unzip a .hgt.zip file.
	"""
	saveFilename = saveZipFilename[0:-4]
	print "unzipping file %s ..."%saveZipFilename
	zipFile = zipfile.ZipFile(saveZipFilename)
	for name in zipFile.namelist():
		saveFile = open(saveFilename, 'wb')
		saveFile.write(zipFile.read(name))
		saveFile.close()
		os.remove(saveZipFilename)
	print "DONE"

def getFiles(area):
	try:
		os.stat(hgtSaveDir)
	except:
		os.mkdir(hgtSaveDir)
	bbox = calcBbox(area)
	filesToDownload = makeFileNames(bbox)	
	files = []
	for file in filesToDownload:
		saveZipFilename = os.path.join(hgtSaveDir, file)
		saveFilename = saveZipFilename[0:-4]
		try:
			os.stat(saveFilename)
			if os.path.getsize(saveFilename) != 2884802:
				raise IOError
			print "found existing file %s."%saveFilename
		except:
			try:
				os.stat(saveZipFilename)
				unzipFile(saveZipFilename)
			except:
				url = getUrl(file)
				if url:
					print "donwloading file %s to %s ..."%(url, saveZipFilename)
					urllib.urlretrieve(url, filename=saveZipFilename)
					try:
						unzipFile(saveZipFilename)
					except:
						print "file %s from %s is not a zip file"%(saveZipFilename, url)
				else:
					print "file %s not found on server."%file
		try:
			os.stat(saveFilename)
			files.append(saveFilename)
		except:
			pass
	return files

