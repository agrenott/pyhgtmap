#!/usr/bin/env python

#import psyco
#psyco.full()

__author__ = "Adrian Dempwolff (adrian.dempwolff@urz.uni-heidelberg.de)"
__version__ = "1.44"
__copyright__ = "Copyright (c) 2009-2012 Adrian Dempwolff"
__license__ = "GPLv2"

import sys
import os
import select
from optparse import OptionParser

from phyghtmap import hgt
from phyghtmap import osmUtil
from phyghtmap import NASASRTMUtil
from phyghtmap import pbfUtil

profile = False

def parseCommandLine():
	"""parses the command line.
	"""
	parser = OptionParser(usage="%prog [options] [<hgt file>] [<hgt files>]"
    "\nphyghtmap generates contour lines from NASA SRTM data."
		"\nIt takes at least an area definition as input.  It then looks for a"
		"\ncache directory (per default: ./hgt/) and the needed SRTM files.  If"
		"\nno cache directory is found, it will be created.  It then downloads"
		"\nall the needed NASA SRTM data files automatically if they are not cached"
		"\nyet.  There is also the possibility of masking the NASA SRTM data with"
		"\ndata from www.viewfinderpanoramas.org which fills voids and other data"
		"\nlacking in the NASA data set.")
	parser.add_option("-a", "--area", help="choses the area to generate osm SRTM"
		"\ndata for by bounding box. If necessary, files are downloaded from"
		"\nthe NASA server (%s)."
		"\nSpecify as <left>:<bottom>:<right>:<top> in degrees of latitude"
		"\nand longitude, respectively. Latitudes south of the equator and"
		"\nlongitudes west of Greenwich may be given as negative decimal numbers."
		"\nIf this option is given, specified hgt"
		"\nfiles will be omitted."%NASASRTMUtil.NASASRTMUtilConfig.NASAhgtFileServerRe%"[1|3]",
	  dest="area", metavar="LEFT:BOTTOM:RIGHT:TOP", action="store", default=None)
	parser.add_option("--polygon", help="use polygon FILENAME as downloaded from"
		"\nhttp://download.geofabrik.de/clipbounds/ as bounds for the output contour"
		"\ndata.  The computation time will be somewhat higher then.  If specified,"
		"\na bounding box passed to the --area option will be ignored.",
		dest="polygon", action="store", metavar="FILENAME", default=None)
	parser.add_option("-s", "--step", help="specify contour line step size in"
		"\nmeters. The default value is 20.", dest="contourStepSize",
		metavar="STEP", action="store", default='20')
	parser.add_option("-0", "--no-zero-contour", help="say this, if you don't want"
		"\nthe sea level contour line (0 m) (which sometimes looks rather ugly) to"
		"\nappear in the output.", action="store_true", default=False, dest="noZero")
	parser.add_option("-o", "--output-prefix", help="specify a prefix for the"
		"\nfilenames of the output osm file(s).", dest="outputPrefix",
		metavar="PREFIX", action="store", default=None)
	parser.add_option("-p", "--plot", help="specify the prefix for the files to write"
		"\nlongitude/latitude/elevation data to instead of generating contour"
		"\nosm.", dest="plotPrefix",
		action="store", default=None)
	parser.add_option("-c", "--line-cat", help="specify a string of two comma"
		"\nseperated integers for major and medium elevation categories, e. g."
		"\n'200,100' which is the default. This is needed for fancy rendering.",
		dest="lineCats", metavar="ELEVATION_MAJOR,ELEVATION_MEDIUM", action="store",
		default='200,100')
	parser.add_option("-j", "--jobs", help="number of jobs to be run"
		" in parallel (POSIX only)", dest="nJobs", action="store",
		type="int", default=1)
	parser.add_option("--osm-version", help="pass a number as OSM-VERSION to"
		"\nuse for the output.  The default value is 0.6.  If you need an older"
		"\nversion, try 0.5.",
		metavar="OSM-VERSION", dest="osmVersion", action="store", default=0.6,
		type="float")
	parser.add_option("--write-timestamp", help="write the timestamp attribute of"
		"\noutput OSM XML node and way elements.  This might be needed by some"
		"\ninterpreters.", dest="writeTimestamp", action="store_true",
		default=False)
	parser.add_option("--start-node-id", help="specify an integer as id of"
		"\nthe first written node in the output OSM xml.  It defaults to 10000000"
		"\nbut some OSM xml mergers are running into trouble when encountering non"
		"\nunique ids.  In this case and for the moment, it is safe to say"
		"\n10000000000 (ten billion) then.", dest="startId", type="int",
		default=10000000, action="store", metavar="NODE-ID")
	parser.add_option("--start-way-id", help="specify an integer as id of"
		"\nthe first written way in the output OSM xml.  It defaults to 10000000"
		"\nbut some OSM xml mergers are running into trouble when encountering non"
		"\nunique ids.  In this case and for the moment, it is safe to say"
		"\n10000000000 (ten billion) then.", dest="startWayId", type="int",
		default=10000000, action="store", metavar="WAY-ID")
	parser.add_option("--max-nodes-per-tile", help="specify an integer as a maximum"
		"\nnumber of nodes per generated tile.  It defaults to 1000000,"
		"\nwhich is approximately the maximum number of nodes handled properly"
		"\nby mkgmap.  For bigger tiles, try higher values.  For a single file"
		"\noutput, say 0 here.",
		dest="maxNodesPerTile", type="int", default=1000000, action="store")
	parser.add_option("--max-nodes-per-way", help="specify an integer as a maximum"
		"\nnumber of nodes per way.  It defaults to 2000, which is the maximum value"
		"\nfor OSM api version 0.6.  Say 0 here, if you want unsplitted ways.",
		dest="maxNodesPerWay", type="int", default=2000, action="store")
	parser.add_option("--gzip", help="turn on gzip compression of output files."
		"\nThis reduces the needed disk space but results in higher computation"
		"\ntimes.  Specifiy an integer between 1 and 9.  1 means low compression and"
		"\nfaster computation, 9 means high compression and lower computation.",
		dest="gzip", action="store", default=0, metavar="COMPRESSLEVEL",
		type="int")
	parser.add_option("--pbf", help="write protobuf binary files instead of OSM"
		"\nXML.  This reduces the needed disk space. Be sure the programs you"
		"\nwant to use the output files with are capable of pbf parsing.  The"
		"\noutput files will have the .osm.pbf extension.", action="store_true",
		default=False, dest="pbf")
	parser.add_option("--srtm", help="use SRTM resolution of SRTM-RESOLUTION"
		"\narc seconds.  Note that the finer 1 arc second grid is only available"
		"\nin the USA.  Possible values are 1 and 3, the default value is 3.",
		metavar="SRTM-RESOLUTION", dest="srtmResolution", action="store",
		type="int", default=3)
	parser.add_option("--viewfinder-mask", help="if specified, NASA SRTM data"
 		"\nare masked with data from www.viewfinderpanoramas.org.  Possible values"
		"\nare 1 and 3 (for explanation, see the --srtm option).",
		metavar="VIEWFINDER-RESOLUTION", type="int", default=0, action="store",
		dest="viewfinder")
	parser.add_option("--source", "--data-source", help="specify a list of"
		"\nsources to use as comma-seperated string.  Available sources are"
		"\n'srtm1', 'srtm3', 'view1' and 'view3'.  If specified, the data source"
		"\nwill be selected using this option as preference list.  Specifying"
		"\n--source=view3,srtm3 for example will prefer viewfinder 3 arc second"
		"\ndata to NASA SRTM 3 arc second data.", metavar="DATA-SOURCE",
		action="store", default=None, dest="dataSource")
	parser.add_option("--corrx", help="correct x offset of contour lines."
		"\n A setting of --corrx=0.0005 was reported to give good results."
		"\n However, the correct setting seems to depend on where you are, so"
		"\nit is may be better to start with 0 here.",
		metavar="SRTM-CORRX", dest="srtmCorrx", action="store",
		type="float", default=0)
	parser.add_option("--corry", help="correct y offset of contour lines."
		"\n A setting of --corry=0.0005 was reported to give good results."
		"\n However, the correct setting seems to depend on where you are, so"
		"\nit may be better to start with 0 here.",
		metavar="SRTM-CORRY", dest="srtmCorry", action="store",
		type="float", default=0)
	parser.add_option("--hgtdir", help="Cache directory for hgt files."
		"\nThe downloaded SRTM files are stored in a cache directory for later use."
		"\nThe default directory for this is ./hgt/ in the current directory.  You can"
		"\nspecify another cache directory with this option.",
		dest="hgtdir", action="store", default=None, metavar="DIRECTORY")
	parser.add_option("-v", "--version", help="print version and exit.",
		dest="version", action="store_true", default=False)
	opts, args = parser.parse_args()
	if opts.version:
		print "phyghtmap %s"%__version__
		sys.exit(0)
	if opts.pbf and opts.gzip:
		sys.stderr.write("You can't combine the --gzip and --pbf options.\n")
		sys.exit(1)
	if opts.srtmResolution not in [1, 3]:
		sys.stderr.write("The --srtm option can only take '1' or '3' as values."
			"  Defaulting to 3.\n")
		opts.srtmResolution = 3
	if opts.viewfinder not in [0, 1, 3]:
		sys.stderr.write("The --viewfinder-mask option can only take '1' or '3' as values."
			"  Won't use viewfinder data.\n")
		opts.viewfinder = 0
	if opts.dataSource:
		opts.dataSource = opts.dataSource.lower().split(",")
		for s in opts.dataSource:
			if not s in ["view1", "view3", "srtm1", "srtm3"]:
				print "Unknown data source: %s"%s
				sys.exit(1)
	else:
		opts.dataSource = []
		if opts.viewfinder != 0:
			opts.dataSource.append("view%i"%opts.viewfinder)
		opts.dataSource.append("srtm%i"%opts.srtmResolution)
	if len(args) == 0 and not opts.area and not opts.polygon:
		parser.print_help()
		sys.exit(1)
	if opts.polygon:
		opts.area, opts.polygon = hgt.parsePolygon(opts.polygon)
	if opts.hgtdir:  # Set custom ./hgt/ directory
		NASASRTMUtil.NASASRTMUtilConfig.CustomHgtSaveDir(opts.hgtdir)
	return opts, args

def makeOsmFilename(borders, opts, srcNames):
	"""generate a filename for the output osm file. This is done using the bbox
	of the current hgt file.
	"""
	minLon, minLat, maxLon, maxLat = borders
	if opts.outputPrefix:
		prefix = "%s_"%opts.outputPrefix
	else:
		prefix = ""
	srcNameMiddles = [os.path.split(os.path.split(srcName)[0])[1].lower() for srcName in
		srcNames]
	for srcNameMiddle in set(srcNameMiddles):
		if srcNameMiddle.lower()[:4] in ["srtm", "view"]:
			continue
		else:
			osmName = hgt.makeBBoxString(borders)%prefix + ".osm"
			break
	else:
		srcTag = ",".join([s for s in opts.dataSource if s in
			set(srcNameMiddles)])
		osmName = hgt.makeBBoxString(borders)%prefix + "_%s.osm"%(srcTag)
	if opts.gzip:
		osmName += ".gz"
	elif opts.pbf:
		osmName += ".pbf"
	return osmName

def getOutput(opts, srcNames, bounds):
	outputFilename = makeOsmFilename(bounds, opts, srcNames)
	elevClassifier=osmUtil.makeElevClassifier(*[int(h) for h in
		opts.lineCats.split(",")])
	if not opts.pbf:
		output = osmUtil.Output(outputFilename,
			osmVersion=opts.osmVersion, phyghtmapVersion=__version__,
			boundsTag=hgt.makeBoundsString(bounds), gzip=opts.gzip,
			elevClassifier=elevClassifier, timestamp=opts.writeTimestamp)
	else:
		output = pbfUtil.Output(outputFilename, opts.osmVersion, __version__,
			bounds, elevClassifier)
	return output

def writeNodes(*args, **kwargs):
	opts = args[-1]
	if not opts.pbf:
		return osmUtil.writeXML(*args, **kwargs)
	else:
		return pbfUtil.writeNodes(*args, **kwargs)

def processHgtFile(srcName, opts, output=None, wayOutput=None, statsOutput=None,
	timestampString="", checkPoly=False):
	hgtFile = hgt.hgtFile(srcName, opts.srtmCorrx, opts.srtmCorry, opts.polygon,
		checkPoly)
	hgtTiles = hgtFile.makeTiles(opts)
	if opts.plotPrefix:
		for tile in hgtTiles:
			tile.plotData(opts.plotPrefix)
		return []
	if opts.maxNodesPerTile == 0:
		singleOutput = True
	else:
		singleOutput = False
	if opts.doFork:
		# called from processQueue
		numOfPoints, numOfWays = 0, 0
		goodTiles = []
		for tile in hgtTiles:
			try:
				tile.elevations, tile.contourData = tile.contourLines(
					stepCont=int(opts.contourStepSize),
					maxNodesPerWay=opts.maxNodesPerWay, noZero=opts.noZero)
				goodTiles.append(tile)
			except ValueError: # tiles with the same value on every element
				continue
			numOfPointsAdd, numOfWaysAdd = tile.countNodes(maxNodesPerWay=opts.maxNodesPerWay)
			numOfPoints += numOfPointsAdd
			numOfWays += numOfWaysAdd
		hgtTiles = goodTiles
		statsOutput.write(str(numOfWays)+":"+str(numOfPoints))
		statsOutput.close()
		if singleOutput:
			# forked, single output, output is already defined
			#output = output
			ways = []
			for tile in hgtTiles:
				# there is only one tile
				elevations, contourData = tile.elevations, tile.contourData
				_, ways = writeNodes(output, contourData,
						elevations, timestampString, opts)
			output.close() # close the output pipe
			wayOutput.write(str(ways))
			wayOutput.close()
			return # we don't need to return something special
		else:
			# forked, multi output
			for tile in hgtTiles:
				output = getOutput(opts, [srcName, ], tile.bbox())
				elevations, contourData = tile.elevations, tile.contourData
				# we have multiple output files, so we need to count nodeIds here
				opts.startId, ways = writeNodes(output, contourData,
						elevations, output.timestampString, opts)
				output.writeWays(ways, opts.startWayId)
				# we have multiple output files, so we need to count wayIds here
				opts.startWayId += len(ways)
				output.done()
			return # we don't need to return something special
	else:
		if singleOutput:
			# not forked, single output, output is already defined
			# output = output
			ways = []
			for tile in hgtTiles:
				# there is only one tile
				try:
					elevations, contourData = tile.contourLines(
						stepCont=int(opts.contourStepSize),
						maxNodesPerWay=opts.maxNodesPerWay, noZero=opts.noZero)
				except ValueError: # tiles with the same value on every element
					continue
				opts.startId, ways = writeNodes(output, contourData,
						elevations, timestampString, opts)
			return ways # needed to complete file later
		else:
			# not forked, multi output
			for tile in hgtTiles:
				output = getOutput(opts, [srcName, ], tile.bbox())
				try:
					elevations, contourData = tile.contourLines(
						stepCont=int(opts.contourStepSize),
						maxNodesPerWay=opts.maxNodesPerWay, noZero=opts.noZero)
				except ValueError: # tiles with the same value on every element
					continue
				# we have multiple output files, so we need to count nodeIds here
				opts.startId, ways = writeNodes(output, contourData,
						elevations, output.timestampString, opts)
				output.writeWays(ways, opts.startWayId)
				# we have multiple output files, so we need to count wayIds here
				opts.startWayId += len(ways)
				output.done()
			return [] # don't need to return ways, since output is already complete


class ProcessQueue(object):
	def __init__(self, nJobs, fileList, **kwargs):
		self.nJobs, self.fileList = nJobs, fileList
		self.kwargs = kwargs
		self.opts = self.kwargs["opts"]
		self.children = {}
		if self.opts.maxNodesPerTile == 0:
			self.singleOutput = True
			bounds = [float(b) for b in self.opts.area.split(":")]
			srcNames = [s[0] for s in self.fileList]
			self.output = getOutput(self.opts, srcNames, bounds)
		else:
			self.singleOutput = False

	def _forkOneSingleOutput(self):
		nodeR, nodeW = os.pipe()
		wayR, wayW = os.pipe()
		statsR, statsW = os.pipe()
		pid = os.fork()
		srcName, checkPoly = self.fileList.pop()
		if pid==0:
			print "Computing %s"%srcName
			os.close(statsR)
			statsWPipe = os.fdopen(statsW, "w")
			os.close(nodeR)
			nodeWPipe = os.fdopen(nodeW, "w")
			wayWPipe = os.fdopen(wayW, "w")
			processHgtFile(srcName, self.opts, nodeWPipe, wayWPipe, statsWPipe,
				self.output.timestampString, checkPoly=checkPoly)
			statsWPipe.close()
			nodeWPipe.close()
			wayWPipe.close()
			os._exit(0)
		else:
			os.close(statsW)
			statsRPipe = os.fdopen(statsR)
			statsRList, _, _ = select.select([statsRPipe, ], [], [])
			stats = statsRList[0].read()
			statsRPipe.close()
			numOfWays, numOfNodes = [int(el) for el in stats.split(":")]
			os.close(nodeW)
			os.close(wayW)
			nodeRPipe = os.fdopen(nodeR)
			wayRPipe = os.fdopen(wayR)
			self.children[pid] = (srcName, nodeRPipe, wayRPipe)
			self.Poll.register(nodeRPipe, select.POLLIN)
			return numOfWays, numOfNodes

	def processSingleOutput(self):
		self.Poll = select.poll()
		self.ways = []
		while self.fileList or self.children:
			while len(self.children)<self.nJobs and self.fileList:
				expectedNumOfWays, expectedNumOfNodes = self._forkOneSingleOutput()
				self.opts.startId += expectedNumOfNodes
				#self.opts.startWayId += expectedNumOfWays
			if self.children:
				rDict = dict([(nodeRPipe.fileno(), nodeRPipe) for _, nodeRPipe, _ in
					self.children.values()])
				readyRPipes = [rDict[i] for i, _ in self.Poll.poll()]
				for readyRPipe in readyRPipes:
					while True:
						line = readyRPipe.readline()
						if len(line) == 0:
							break
						self.output.write(line)
				for readyWayRPipe in select.select([child[2] for child in
					self.children.values()], [], [])[0]:
					s = readyWayRPipe.read()
					if len(s):
						self.ways.extend(eval(s))
				pid, res = os.wait()
				if res:
					print "Panic: Didn't work:", self.children[pid][0]
				self.Poll.unregister(self.children[pid][1])
				self.children[pid][1].close()
				self.children[pid][2].close()
				del self.children[pid]
		self.output.writeWays(self.ways, self.opts.startWayId)
		self.output.done()

	def _forkOneMultiOutput(self):
		statsR, statsW = os.pipe()
		pid = os.fork()
		srcName, checkPoly = self.fileList.pop()
		if pid==0:
			print "Computing %s"%srcName
			os.close(statsR)
			statsWPipe = os.fdopen(statsW, "w")
			processHgtFile(srcName, self.opts, None, None, statsWPipe,
				checkPoly=checkPoly)
			statsWPipe.close()
			os._exit(0)
		else:
			os.close(statsW)
			statsRPipe = os.fdopen(statsR)
			statsRList, _, _ = select.select([statsRPipe, ], [], [])
			stats = statsRList[0].read()
			statsRPipe.close()
			numOfWays, numOfNodes = [int(el) for el in stats.split(":")]
			self.children[pid] = (srcName, )
			return numOfWays, numOfNodes

	def processMultiOutput(self):
		while self.fileList or self.children:
			while len(self.children)<self.nJobs and self.fileList:
				expectedNumOfWays, expectedNumOfNodes = self._forkOneMultiOutput()
				self.opts.startId += expectedNumOfNodes
				self.opts.startWayId += expectedNumOfWays
			if self.children:
				pid, res = os.wait()
				if res:
					print "Panic: Didn't work:", self.children[pid][0]
				del self.children[pid]

	def process(self):
		if self.singleOutput:
			self.processSingleOutput()
		else:
			self.processMultiOutput()


def main():
	opts, args = parseCommandLine()
	if opts.area:
		hgtDataFiles = NASASRTMUtil.getFiles(opts.area, opts.polygon,
			opts.srtmCorrx, opts.srtmCorry, opts.dataSource)
		if len(hgtDataFiles) == 0:
			print "No files for this area %s from desired source."%opts.area
			sys.exit(0)
	else:
		hgtDataFiles = [(arg, False) for arg in args if arg.endswith(".hgt")]
		opts.area = ":".join([str(i) for i in hgt.calcHgtArea(hgtDataFiles,
			opts.srtmCorrx, opts.srtmCorry)])

	if hasattr(os, "fork") and opts.nJobs != 1:
		opts.doFork = True
		queue = ProcessQueue(opts.nJobs, hgtDataFiles, opts=opts)
		queue.process()
	else:
		opts.doFork = False
		if opts.maxNodesPerTile == 0:
			bounds = [float(b) for b in opts.area.split(":")]
			srcNames = [s[0] for s in hgtDataFiles]
			output = getOutput(opts, srcNames, bounds)
		else:
			output = None
		ways = []
		for hgtDataFileName, checkPoly in hgtDataFiles:
			if output:
				ways.extend(processHgtFile(hgtDataFileName, opts, output,
					timestampString=output.timestampString, checkPoly=checkPoly))
			else:
				ways.extend(processHgtFile(hgtDataFileName, opts, output,
					checkPoly=checkPoly))
		if opts.maxNodesPerTile == 0:
			# writing to single file, need to complete it here
			output.writeWays(ways, opts.startWayId)
			output.done()

if __name__=="__main__":
	if profile:
		import cProfile
		cProfile.run("main()", "stats.profile")
		import pstats
		stats = pstats.Stats("stats.profile")
		stats.sort_stats("time").print_stats(20)
	else:
		main()
