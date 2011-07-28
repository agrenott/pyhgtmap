#!/usr/bin/env python

#import psyco
#psyco.full()

__author__ = "Markus Demleitner (msdemlei@users.sf.net), " +\
	"Adrian Dempwolff (dempwolff@informatik.uni-heidelberg.de)"
__version__ = "1.22"
__copyright__ = "Copyright (c) 2009-2010 Markus Demleitner, Adrian Dempwolff"
__license__ = "GPLv2"

import sys
import os
from optparse import OptionParser

from phyghtmap import hgt
from phyghtmap import osmUtil
from phyghtmap import NASASRTMUtil

profile = False

def parseCommandLine():
	"""parses the command line.
	"""
	parser = OptionParser(usage="%prog [options] [<hgt file>] [<hgt files>]"
    "\nphyghtmap generates contour lines from NASA SRTM data."
		"\nIt takes at least an area definition as input.  It then looks for a"
		"\ncache directory (./hgt/) and the needed SRTM files.  If no cache"
		"\ndirectory is found, it will be created.  It then downloads all the"
		"\nneeded NASA SRTM data files automatically if they are not cached yet."
		"\nThere is also the possibility of masking the NASA SRTM data with data"
		"\nfrom www.viewfinderpanoramas.org which fills voids and other data"
		"\nlacking in the NASA data set.")
	parser.add_option("-a", "--area", help="choses the area to generate osm SRTM"
		"\ndata for by bounding box. If necessary, files are downloaded from"
		"\nthe NASA server (%s)."
		"\nSpecify as <left>:<bottom>:<right>:<top> in degrees of latitude"
		"\nand longitude, respectively. Latitudes south of the equator and"
		"\nlongitudes west of Greenwich may be given as negative decimal numbers."
		"\nIf this option is given, specified hgt"
		"\nfiles will be omitted."%NASASRTMUtil.NASAhgtFileServerRe%"[1|3]",
	  dest="area", metavar="LEFT:BOTTOM:RIGHT:TOP", action="store", default=None)
	parser.add_option("-s", "--step", help="specify contour line step size in"
		"\nmeters. The default value is 20.", dest="contourStepSize",
		metavar="STEP", action="store", default='20')
	parser.add_option("-o", "--output-prefix", help="specify a prefix for the"
		"\nfilenames of the output osm file(s).", dest="outputPrefix",
		metavar="PREFIX", action="store", default=None)
	parser.add_option("-p", "--plot", help="specify the path to write"
		"\nlongitude/latitude/elevation data to instead of generating contour"
		"\nosm.", dest="plotName",
		action="store", default=None)
	parser.add_option("-c", "--line-cat", help="specify a string of two comma"
		"\nseperated integers for major and medium elevation categories, e. g."
		"\n'200,100' which is the default. This is needed for fancy rendering.",
		dest="lineCats", metavar="ELEVATION_MAJOR,ELEVATION_MEDIUM", action="store",
		default='200,100')
	parser.add_option("-j", "--jobs", help="number of jobs to be run"
		" in parallel (POSIX only)", dest="nJobs", action="store",
		type="int", default=1)
	parser.add_option("--version-tag", help="pass an integer as VERSIONTAG for"
		"\nosm elements to output osm.  This is needed to display the generated"
		"\ncontour data with newer JOSM versions.  The default value is None.",
		metavar="VERSIONTAG", dest="versionTag", action="store", default=None,
		type="int")
	parser.add_option("--start-node-id", help="specify an integer as id of"
		"\nthe first written node in the output OSM xml.  It defaults to 10000000"
		"\nbut some OSM xml mergers are running into trouble when encountering non"
		"\nunique ids.  In this case and for the moment, it is safe to say"
		"\n10000000000 (ten billion) then.", dest="startId", type="int",
		default=10000000, action="store")
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
	parser.add_option("-v", "--version", help="print version and exit.",
		dest="version", action="store_true", default=False)
	opts, args = parser.parse_args()
	if opts.version:
		print "phyghtmap %s"%__version__
		sys.exit(0)
	if opts.srtmResolution not in [1, 3]:
		sys.stderr.write("The --srtm option can only take '1' or '3' as values.\n")
	if opts.viewfinder not in [0, 1, 3]:
		sys.stderr.write("The --viewfinder-mask option can only take '1' or '3' as values.\n")
	if len(args) == 0 and not opts.area:
		parser.print_help()
		sys.exit(1)
	return opts, args

def makeOsmFilename(borders, opts, srcName):
	"""generate a filename for the output osm file. This is done using the bbox
	of the current hgt file.
	"""
	minLon, minLat, maxLon, maxLat = borders
	if opts.outputPrefix:
		prefix = "%s_"%opts.outputPrefix
	else:
		prefix = ""
	srcNameMiddle = os.path.split(os.path.split(srcName)[0])[1]
	return "%slon%.2f_%.2flat%.2f_%.2f_%s.osm"%(
		prefix, minLon, maxLon, minLat, maxLat, srcNameMiddle.lower())


def processHgtFile(srcName, opts):
	hgtFile = hgt.hgtFile(srcName)
	hgtTiles = hgtFile.makeTiles(opts)
	for tile in hgtTiles:
		if opts.plotName:
			tile.plotData(opts.plotName)
		else:
			try:
				contourData = tile.contourLines(stepCont=int(opts.contourStepSize))
				output = osmUtil.Output(makeOsmFilename(tile.bbox(), opts, srcName),
					versionTag=opts.versionTag, startId=opts.startId)
				try:
					osmUtil.writeXML(output, osmUtil.makeElevClassifier(
							*[int(h) for h in opts.lineCats.split(",")]), contourData)
				finally:
					opts.startId = output.done()
			except ValueError: # if arrays with the same value at each position are
			                   # tried to be evaluated
				pass

class ProcessQueue(object):
	def __init__(self, nJobs, fileList, **kwargs):
		self.nJobs, self.fileList = nJobs, fileList
		self.kwargs = kwargs
		self.children = {}

	def _forkOne(self):
		pid = os.fork()
		srcName = self.fileList.pop()
		if pid==0:
			print "Computing %s"%srcName
			processHgtFile(srcName, **self.kwargs)
			os._exit(0)
		else:
			self.children[pid] = srcName

	def process(self):
		while self.fileList or self.children:
			while len(self.children)<self.nJobs and self.fileList:
				self._forkOne()
			if self.children:
				pid, res = os.wait()
				if res:
					print "Panic: Didn't work:", self.children[pid]
				del self.children[pid]
	

def main():
	opts, args = parseCommandLine()
	if opts.area:
		hgtDataFiles = NASASRTMUtil.getFiles(opts.area, opts.srtmResolution,
			opts.viewfinder)
	else:
		hgtDataFiles = [arg for arg in args if arg.endswith(".hgt")]

	if hasattr(os, "fork") and opts.nJobs != 1:
		queue = ProcessQueue(opts.nJobs, hgtDataFiles, opts=opts)
		queue.process()
	else:
		for hgtDataFileName in hgtDataFiles:
			processHgtFile(hgtDataFileName, opts)

if __name__=="__main__":
	if profile:
		import cProfile
		cProfile.run("main()", "stats.profile")
		import pstats
		stats = pstats.Stats("stats.profile")
		stats.sort_stats("time").print_stats(20)
	else:
		main()
