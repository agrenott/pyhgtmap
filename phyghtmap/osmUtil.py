import numpy

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


class Output(object):
	"""An OSM output.

	It is constructed with a destination name,  the parameters of the
	transformations turning native (matplotlib) coordinates to geographic
	coordinates, optionally, a start id...
	"""
	def __init__(self, fName, osmVersion=0.5, startId=10000000):
		self.outF = open(fName, "w")
		self.curId = startId
		self.versionString = ""
		self.osmVersion = "%.1f"%osmVersion
		if osmVersion > 0.5:
			self.versionString = ' version="1"'
		self._writePreamble()

	def _writePreamble(self):
		self.outF.write('<?xml version="1.0" encoding="utf-8"?>\n')
		self.outF.write('<osm version="%s" generator="phyghtmap">\n'%self.osmVersion)
	
	def done(self):
		self.outF.write("</osm>\n")
		self.outF.close()
		return self.getID()

	def write(self, output):
		self.outF.write(output)

	def getID(self):
		self.curId += 1
		return self.curId-1


def _makePoints(output, path):
	"""writes OSM representations of the points making up path to
	output.

	It returns a string containing nd-elements for a closed OSM shape 
	ready for inclusion into a path.
	"""
	ids, content = [], []
	for lon, lat in path.vertices:
		id = output.curId
		output.curId += 1
		content.append('<node id="%d"%s lat="%.7f" lon="%.7f"/>'%(
			id, output.versionString, lat, lon))
		ids.append(id)
	if numpy.all(path.vertices[0]==path.vertices[-1]):  # close contour
		del content[-1]  # remove last node
		del ids[-1]
		ids.append(ids[0])
		output.curId -= 1
	output.write("".join(content)+"\n")
	return ('<nd ref="%d"/>'*len(ids))%tuple(ids)


def _writeContour(output, contour, elevation, osmCat):
	for path in contour.get_paths():
		nodeRefs = _makePoints(output, path)
		output.write('<way id="%d"%s>%s'
			'<tag k="ele" v="%d"/>'
			'<tag k="contour" v="elevation"/>'
			'<tag k="contour_ext" v="%s"/>'
			'</way>\n'%(
				output.getID(),
				output.versionString,
				nodeRefs,
				elevation,
				osmCat))


def writeXML(output, classifier, contours):
	"""emits OSM XML to the Output instance output

	classifier is a function returning an osm contour class for a given
	height.  You probably want to generate it using makeElevClassifier.

	Contours is a matplotlib ContourSet.
	"""
	elevations = contours.cvalues
	for cInd, contour in enumerate(contours.collections):
		elevation = elevations[cInd]
		_writeContour(output, contour, elevation, classifier(elevation))
