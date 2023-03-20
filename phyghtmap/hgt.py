from __future__ import print_function

from typing import Callable, Iterable, List, Optional, Tuple, cast

__author__ = "Adrian Dempwolff (phyghtmap@aldw.de)"
__version__ = "2.23"
__copyright__ = "Copyright (c) 2009-2021 Adrian Dempwolff"
__license__ = "GPLv2+"

import logging
import os
import sys

import numpy
import numpy.typing
import shapely
from matplotlib.path import Path as PolygonPath
from scipy import ndimage


from phyghtmap.contour import ContourObject, build_contours
from phyghtmap.varint import bboxStringtypes

meters2Feet = 1.0 / 0.3048

logger = logging.getLogger(__name__)


class hgtError(Exception):
    """is the main class of visible exceptions from this file."""


class filenameError(hgtError):
    """is raised when parsing bad filenames."""


class elevationError(hgtError):
    """is raised when trying to deal with elevations out of range."""


def halfOf(seq):
    """returns the first half of a sequence"""
    return seq[: len(seq) // 2]


def makeBBoxString(bbox):
    return "{{0:s}}lon{0[0]:.2f}_{0[2]:.2f}lat{0[1]:.2f}_{0[3]:.2f}".format(bbox)


def parsePolygon(filename):
    """reads polygons from a file like one included in
    http://download.geofabrik.de/clipbounds/clipbounds.tgz
    and returns it as list of (<lon>, <lat>) tuples.
    """
    lines = [
        line.strip().lower()
        for line in open(filename).read().split("\n")
        if line.strip()
    ]
    polygons = []
    curPolygon = []
    for l in lines:
        if l in [str(i) for i in range(1, lines.count("end"))]:
            # new polygon begins
            curPolygon = []
        elif l == "end" and len(curPolygon) > 0:
            # polygon ends
            polygons.append(curPolygon)
            curPolygon = []
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
    return (
        "{0:.7f}:{1:.7f}:{2:.7f}:{3:.7f}".format(minLon, minLat, maxLon, maxLat),
        polygons,
    )


def makeBoundsString(bbox):
    """returns an OSM XML bounds tag.

    The input <bbox> may be a list or tuple of floats or an area string as passed
    to the --area option of phyghtmap in the following order:
    minlon, minlat, maxlon, maxlat.
    """
    if type(bbox) in bboxStringtypes and bbox.count(":") == 3:
        bbox = bbox.split(":")
    minlon, minlat, maxlon, maxlat = [float(i) for i in bbox]
    return '<bounds minlat="{0:.7f}" minlon="{1:.7f}" maxlat="{2:.7f}" maxlon="{3:.7f}"/>'.format(
        minlat, minlon, maxlat, maxlon
    )


def parseHgtFilename(filename, corrx, corry) -> Tuple[int, int, int, int]:
    """tries to extract borders from filename and returns them as a tuple
    of floats:
    (<min longitude>, <min latitude>, <max longitude>, <max latitude>)

    Longitudes of west as well as latitudes of south are given as negative
    values.

    Eventually specified longitude (<corrx>) and latitude (<corry>)
    corrections are added here.
    """
    latSwitch = filename[0:1].upper()
    latValue = filename[1:3]
    lonSwitch = filename[3:4].upper()
    lonValue = filename[4:7]
    if latSwitch == "N" and latValue.isdigit():
        minLat = int(latValue)
    elif latSwitch == "S" and latValue.isdigit():
        minLat = -1 * int(latValue)
    else:
        raise filenameError(
            "something wrong with latitude coding in" " filename {0:s}".format(filename)
        )
    maxLat = minLat + 1
    if lonSwitch == "E" and lonValue.isdigit():
        minLon = int(lonValue)
    elif lonSwitch == "W" and lonValue.isdigit():
        minLon = -1 * int(lonValue)
    else:
        raise filenameError(
            "something wrong with longitude coding in"
            " filename {0:s}".format(filename)
        )
    maxLon = minLon + 1
    return minLon + corrx, minLat + corry, maxLon + corrx, maxLat + corry


TransformFunType = Callable[[List[Tuple[float, float]]], List[Tuple[float, float]]]


def getTransform(o, reverse=False) -> Optional[TransformFunType]:
    from osgeo import osr

    n = osr.SpatialReference()
    n.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    n.ImportFromEPSG(4326)
    oAuth = o.GetAttrValue("AUTHORITY", 1)
    nAuth = n.GetAttrValue("AUTHORITY", 1)
    if nAuth == oAuth:
        return None
    else:
        if reverse:
            t = osr.CoordinateTransformation(n, o)
        else:
            t = osr.CoordinateTransformation(o, n)

        def transform(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
            return [
                p[:2]
                for p in t.TransformPoints(points)
                if not any([el == float("inf") for el in p[:2]])
            ]

        return transform


def transformLonLats(minLon, minLat, maxLon, maxLat, transform):
    if transform is None:
        return minLon, minLat, maxLon, maxLat
    else:
        (lon1, lat1), (lon2, lat2), (lon3, lat3), (lon4, lat4) = transform(
            [(minLon, minLat), (maxLon, maxLat), (minLon, maxLat), (maxLon, maxLat)]
        )
        minLon = min([lon1, lon2, lon3, lon4])
        maxLon = max([lon1, lon2, lon3, lon4])
        minLat = min([lat1, lat2, lat3, lat4])
        maxLat = max([lat1, lat2, lat3, lat4])
        return minLon, minLat, maxLon, maxLat


def parseGeotiffBbox(
    filename: str, corrx: float, corry: float, doTransform: bool
) -> Tuple[float, float, float, float]:
    from osgeo import gdal, osr

    try:
        g = gdal.Open(filename)
        geoTransform = g.GetGeoTransform()
        if geoTransform[2] != 0 or geoTransform[4] != 0:
            sys.stderr.write(
                "Can't handle geotiff {!s} with geo transform {!s}\n".format(
                    filename, geoTransform
                )
            )
            raise hgtError
        fileProj = osr.SpatialReference()
        fileProj.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        fileProj.ImportFromWkt(g.GetProjectionRef())
        numOfCols = g.RasterXSize
        numOfRows = g.RasterYSize
    except:
        raise hgtError("Can't handle geotiff file {!s}".format(filename))
    lonIncrement = geoTransform[1]
    latIncrement = geoTransform[5]
    minLon = geoTransform[0] + 0.5 * lonIncrement
    maxLat = geoTransform[3] + 0.5 * latIncrement
    minLat = maxLat + (numOfRows - 1) * latIncrement
    maxLon = minLon + (numOfCols - 1) * lonIncrement
    # get the transformation function from fileProj to EPSG:4326 for this geotiff file
    transform: Optional[TransformFunType] = getTransform(fileProj)
    if doTransform:
        # transformLonLats will return input values if transform is None
        minLon, minLat, maxLon, maxLat = transformLonLats(
            minLon, minLat, maxLon, maxLat, transform
        )
        return minLon + corrx, minLat + corry, maxLon + corrx, maxLat + corry
    else:
        # we need to take care for corrx, corry values then, which are always expected
        # to be EPSG:4326, so transform, add corrections, and transform back to
        # input projection
        # transformation (input projection) -> (epsg:4326)
        minLon, minLat, maxLon, maxLat = transformLonLats(
            minLon, minLat, maxLon, maxLat, transform
        )
        minLon += corrx
        maxLon += corrx
        minLat += corry
        maxLat += corry
        reverseTransform: Optional[TransformFunType] = getTransform(
            fileProj, reverse=True
        )
        # transformation (epsg:4326) -> (input projection)
        minLon, minLat, maxLon, maxLat = transformLonLats(
            minLon, minLat, maxLon, maxLat, reverseTransform
        )
        return minLon, minLat, maxLon, maxLat


def parseFileForBbox(
    fullFilename: str, corrx: float, corry: float, doTransform: bool
) -> Tuple[float, float, float, float]:
    fileExt: str = os.path.splitext(fullFilename)[1].lower().replace(".", "")
    if fileExt == "hgt":
        return parseHgtFilename(os.path.split(fullFilename)[1], corrx, corry)
    elif fileExt in ("tif", "tiff", "vrt"):
        return parseGeotiffBbox(fullFilename, corrx, corry, doTransform)
    raise ValueError(f"Unsupported extension {fileExt}")


def calcHgtArea(
    filenames: List[Tuple[str, bool]], corrx: float, corry: float
) -> Tuple[float, float, float, float]:
    bboxes = [parseFileForBbox(f[0], corrx, corry, doTransform=True) for f in filenames]
    minLon = sorted([b[0] for b in bboxes])[0]
    minLat = sorted([b[1] for b in bboxes])[0]
    maxLon = sorted([b[2] for b in bboxes])[-1]
    maxLat = sorted([b[3] for b in bboxes])[-1]
    return minLon, minLat, maxLon, maxLat


BBOX_EXPAND_EPSILON = 0.1


def polygon_mask(
    x_data: numpy.ndarray,
    y_data: numpy.ndarray,
    polygons: List[List[Tuple[float, float]]],
    transform,
) -> numpy.ndarray:
    """return a mask on self.zData corresponding to all polygons in self.polygons.
    <xData> is meant to be a 1-D array of longitude values, <yData> a 1-D array of
    latitude values.  An array usable as mask for the corresponding zData
    2-D array is returned.
    <transform> may be transform function from the file's projection to EPSG:4326,
    which is the projection used within polygon files.
    """
    X, Y = numpy.meshgrid(x_data, y_data)
    xyPoints = numpy.vstack(([X.T], [Y.T])).T.reshape(len(x_data) * len(y_data), 2)

    # To improve performances, clip original polygons to current data boundaries.
    # Slightly expand the bounding box, as PolygonPath.contains_points result is undefined for points on boundary
    # https://matplotlib.org/stable/api/path_api.html#matplotlib.path.Path.contains_point
    bbox_points: List[Tuple[float, float]] = [
        (x_data.min() - BBOX_EXPAND_EPSILON, y_data.min() - BBOX_EXPAND_EPSILON),
        (x_data.min() - BBOX_EXPAND_EPSILON, y_data.max() + BBOX_EXPAND_EPSILON),
        (x_data.max() + BBOX_EXPAND_EPSILON, y_data.max() + BBOX_EXPAND_EPSILON),
        (x_data.max() + BBOX_EXPAND_EPSILON, y_data.min() - BBOX_EXPAND_EPSILON),
        (x_data.min() - BBOX_EXPAND_EPSILON, y_data.min() - BBOX_EXPAND_EPSILON),
    ]
    if transform is not None:
        xyPoints = transform(xyPoints)
        bbox_points = transform(bbox_points)
    bbox_shape = shapely.Polygon(bbox_points)
    clipped_polygons = []
    for p in polygons:
        clipped_p = shapely.intersection(shapely.Polygon(p), bbox_shape)
        if isinstance(clipped_p, shapely.MultiPolygon):
            clipped_polygons += [
                [(x, y) for x, y in poly.exterior.coords]
                for poly in clipped_p.geoms
                if not poly.is_empty
            ]
        elif not clipped_p.is_empty:
            clipped_polygons.append([(x, y) for x, y in clipped_p.exterior.coords])

    if not clipped_polygons:
        # Empty intersection: data is fully masked
        # Simply return a 1x1 True mask
        return numpy.array([True])

    maskArray = numpy.ma.array(numpy.empty((len(x_data) * len(y_data), 1)))
    for p in clipped_polygons:
        # run through all polygons and combine masks
        mask = PolygonPath(p).contains_points(xyPoints)
        maskArray = numpy.ma.array(maskArray, mask=mask, keep_mask=True)
    return numpy.invert(maskArray.mask.reshape(len(y_data), len(x_data)))


def super_sample(
    input_data: numpy.ndarray, input_mask: numpy.ndarray, zoom_level: float
) -> Tuple[numpy.ndarray, numpy.ndarray]:
    """Super sample the input data and associated mask."""
    logger.debug("Smoothing input by a ratio of %f", zoom_level)
    # Limit order to 1 to avoid artifacts on constant value boundaries (eg. limit of sea areas)
    # Round result to avoid oscillations around 0 due to spline interpolation
    out_data = numpy.around(
        cast(numpy.ndarray, ndimage.zoom(input_data, zoom_level, order=3)), 0
    )
    # Resize mask independantly, using 0 order to avoid artifacts
    out_mask = ndimage.zoom(input_mask, zoom_level, order=0)
    # from PIL import Image as im
    # im.fromarray(input_data, mode="F").save('orig.tiff')
    # im.fromarray(out_data, mode="F").save('super.tiff')
    return out_data, out_mask


class hgtFile:
    """is a handle for SRTM data files"""

    def __init__(
        self,
        filename,
        corrx,
        corry,
        polygons: Optional[List[List[Tuple[float, float]]]] = None,
        checkPoly=False,
        voidMax: int = -0x8000,
        feetSteps=False,
        smooth_ratio: float = 1.0,
    ):
        """tries to open <filename> and extracts content to self.zData.

        <corrx> and <corry> are longitude and latitude corrections (floats)
        as passed to phyghtmap on the commandline.
        """
        self.feetSteps = feetSteps
        self.fullFilename = filename
        self.filename = os.path.split(filename)[-1]
        self.fileExt = os.path.splitext(self.filename)[1].lower().replace(".", "")
        # Assigned by initAsXxx
        self.polygons: Optional[List[List[Tuple[float, float]]]]
        if self.fileExt == "hgt":
            self.initAsHgt(corrx, corry, polygons, checkPoly, voidMax, smooth_ratio)
        elif self.fileExt in ("tif", "tiff", "vrt"):
            self.initAsGeotiff(corrx, corry, polygons, checkPoly, voidMax, smooth_ratio)
        # some statistics
        try:
            minLon, minLat, maxLon, maxLat = transformLonLats(
                self.minLon, self.minLat, self.maxLon, self.maxLat, self.transform
            )
            print(
                "{0:s} file {1:s}: {2:d} x {3:d} points, bbox: ({4:.5f}, {5:.5f}, "
                "{6:.5f}, {7:.5f}){8:s}".format(
                    self.fileExt,
                    self.fullFilename,
                    self.numOfCols,
                    self.numOfRows,
                    minLon,
                    minLat,
                    maxLon,
                    maxLat,
                    {True: ", checking polygon borders", False: ""}[checkPoly],
                )
            )
        except:
            # Best effort stats display
            pass
        # Used only when initialized from GeoTIFF
        self.transform: Optional[TransformFunType]
        self.reverseTransform: Optional[TransformFunType]

    def initAsHgt(
        self,
        corrx: float,
        corry: float,
        polygons: Optional[List[List[Tuple[float, float]]]],
        checkPoly: bool,
        voidMax: int,
        smooth_ratio: float,
    ) -> None:
        """SRTM3 hgt files contain 1201x1201 points;
        however, we try to determine the real number of points.
        Height data are stored as 2-byte signed integers, the byte order is
        big-endian standard. The data are stored in a row major order.
        All height data are in meters referenced to the WGS84/EGM96 geoid as
        documented at http://www.nga.mil/GandG/wgsegm/.
        """
        try:
            numOfDataPoints = os.path.getsize(self.fullFilename) / 2
            self.numOfRows = self.numOfCols = int(numOfDataPoints**0.5)
            self.zData = (
                numpy.fromfile(self.fullFilename, dtype=">i2")
                .reshape(self.numOfRows, self.numOfCols)
                .astype("float32")
            )

            # Compute mask BEFORE zooming, due to zoom artifacts on void areas boundaries
            voidMask = numpy.asarray(numpy.where(self.zData <= voidMax, True, False))
            if smooth_ratio != 1:
                self.zData, voidMask = super_sample(self.zData, voidMask, smooth_ratio)
                self.numOfRows, self.numOfCols = self.zData.shape
            self.zData = numpy.ma.array(
                self.zData, mask=voidMask, fill_value=float("NaN")
            )
            if self.feetSteps:
                self.zData = self.zData * meters2Feet
        finally:
            self.lonIncrement = 1.0 / (self.numOfCols - 1)
            self.latIncrement = 1.0 / (self.numOfRows - 1)
            self.minLon, self.minLat, self.maxLon, self.maxLat = self.borders(
                corrx, corry
            )
            if checkPoly:
                self.polygons = polygons
            else:
                self.polygons = None
            self.transform = None
            self.reverseTransform = None

    def initAsGeotiff(
        self, corrx, corry, polygon, checkPoly, voidMax, smooth_ratio: float
    ) -> None:
        """init this hgtFile instance with data from a geotiff image."""
        from osgeo import gdal, osr

        try:
            g = gdal.Open(self.fullFilename)
            geoTransform = g.GetGeoTransform()
            # we don't need to check for the geo transform, this was already done when
            # calculating the area name from main.py
            fileProj = osr.SpatialReference()
            fileProj.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            fileProj.ImportFromWkt(g.GetProjectionRef())
            self.numOfCols = g.RasterXSize
            self.numOfRows = g.RasterYSize
            # init z data
            self.zData = g.GetRasterBand(1).ReadAsArray().astype("float32")
            # Compute mask BEFORE zooming, due to zoom artifacts on void areas boundaries
            voidMask = numpy.asarray(numpy.where(self.zData <= voidMax, True, False))
            if smooth_ratio != 1:
                self.zData, voidMask = super_sample(self.zData, voidMask, smooth_ratio)
                self.numOfRows, self.numOfCols = self.zData.shape
            self.zData = numpy.ma.array(
                self.zData, mask=voidMask, fill_value=float("NaN")
            )
            if self.feetSteps:
                self.zData = self.zData * meters2Feet
            # make x and y data
            self.lonIncrement = geoTransform[1]
            self.latIncrement = -geoTransform[5]
            self.minLon, self.minLat, self.maxLon, self.maxLat = self.borders(
                corrx, corry
            )
            # get the transformation function from fileProj to EPSG:4326 for this geotiff file
            self.transform = getTransform(fileProj)
            self.reverseTransform = getTransform(fileProj, reverse=True)
        finally:
            if checkPoly:
                self.polygons = polygon
            else:
                self.polygons = None

    def borders(self, corrx=0.0, corry=0.0):
        """determines the bounding box of self.filename using parseHgtFilename()."""
        return parseFileForBbox(self.fullFilename, corrx, corry, doTransform=False)

    def makeTiles(self, opts) -> List["hgtTile"]:
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
                bboxMinLon, bboxMinLat, bboxMaxLon, bboxMaxLat = (
                    float(bound) for bound in area.split(":")
                )
                if self.reverseTransform is not None:
                    bboxMinLon, bboxMinLat, bboxMaxLon, bboxMaxLat = transformLonLats(
                        bboxMinLon,
                        bboxMinLat,
                        bboxMaxLon,
                        bboxMaxLat,
                        self.reverseTransform,
                    )
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
                minLonTruncIndex = int(
                    (bboxMinLon - self.minLon)
                    / (self.maxLon - self.minLon)
                    / self.lonIncrement
                )
                minLatTruncIndex = -1 * int(
                    (bboxMinLat - self.minLat)
                    / (self.maxLat - self.minLat)
                    / self.latIncrement
                )
                maxLonTruncIndex = int(
                    (bboxMaxLon - self.maxLon)
                    / (self.maxLon - self.minLon)
                    / self.lonIncrement
                )
                maxLatTruncIndex = -1 * int(
                    (bboxMaxLat - self.maxLat)
                    / (self.maxLat - self.minLat)
                    / self.latIncrement
                )
                realMinLon = self.minLon + minLonTruncIndex * self.lonIncrement
                realMinLat = self.minLat - minLatTruncIndex * self.latIncrement
                realMaxLon = self.maxLon + maxLonTruncIndex * self.lonIncrement
                realMaxLat = self.maxLat - maxLatTruncIndex * self.latIncrement
                if maxLonTruncIndex == 0:
                    maxLonTruncIndex = None
                if minLatTruncIndex == 0:
                    minLatTruncIndex = None
                zData = inputData[
                    maxLatTruncIndex:minLatTruncIndex, minLonTruncIndex:maxLonTruncIndex
                ]
                return (realMinLon, realMinLat, realMaxLon, realMaxLat), zData
            else:
                return (self.minLon, self.minLat, self.maxLon, self.maxLat), inputData

        def chopData(inputBbox, inputData, depth=0):
            """chops data and appends chops to tiles if small enough."""

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
                # helpData = numpy.where(data==-0x8000, float("NaN"), data) / step
                # TODO: ndarray has no filled() method (anymore?!) - did this ever worked?
                helpData = data.filled() / step
                xHelpData = numpy.abs(helpData[:, 1:] - helpData[:, :-1])
                yHelpData = numpy.abs(helpData[1:, :] - helpData[:-1, :])
                estimatedNumOfNodes = numpy.nansum(xHelpData) + numpy.nansum(yHelpData)
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
				"""
                # number of rows > number of cols, horizontal cutting
                (
                    unchoppedBboxMinLon,
                    unchoppedBboxMinLat,
                    unchoppedBboxMaxLon,
                    unchoppedBboxMaxLat,
                ) = unchoppedBbox
                unchoppedNumOfRows = unchoppedData.shape[0]
                chopLatIndex = int(unchoppedNumOfRows / 2.0)
                chopLat = unchoppedBboxMaxLat - (chopLatIndex * self.latIncrement)
                lowerChopBbox = (
                    unchoppedBboxMinLon,
                    unchoppedBboxMinLat,
                    unchoppedBboxMaxLon,
                    chopLat,
                )
                upperChopBbox = (
                    unchoppedBboxMinLon,
                    chopLat,
                    unchoppedBboxMaxLon,
                    unchoppedBboxMaxLat,
                )
                lowerChopData = unchoppedData[chopLatIndex:, :]
                upperChopData = unchoppedData[: chopLatIndex + 1, :]
                return (lowerChopBbox, lowerChopData), (upperChopBbox, upperChopData)
                """
				else:
					# number of cols > number of rows, vertical cutting
					(unchoppedBboxMinLon, unchoppedBboxMinLat, unchoppedBboxMaxLon,
						unchoppedBboxMaxLat) = unchoppedBbox
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

            # Discard quickly fully void tiles (eg. middle of the sea)
            if isinstance(inputData, numpy.ma.masked_array):
                voidMaskValues = numpy.unique(inputData.mask)
                if numpy.array_equal(voidMaskValues, [True]):
                    # this tile is full of void values, so discard this tile
                    return

            if tooManyNodes(inputData):
                chops = getChops(inputData, inputBbox)
                for choppedBbox, choppedData in chops:
                    chopData(choppedBbox, choppedData, depth + 1)
            else:
                if self.polygons:
                    tileXData = numpy.arange(
                        inputBbox[0],
                        inputBbox[2] + self.lonIncrement / 2.0,
                        self.lonIncrement,
                    )
                    tileYData = numpy.arange(
                        inputBbox[3],
                        inputBbox[1] - self.latIncrement / 2.0,
                        -self.latIncrement,
                    )
                    tileMask = polygon_mask(
                        tileXData, tileYData, self.polygons, self.transform
                    )
                    tilePolygon = self.polygons
                    if not numpy.any(tileMask):
                        # all points are inside the polygon
                        tilePolygon = None
                    elif numpy.all(tileMask):
                        # all elements are masked -> tile is outside of self.polygons
                        return
                else:
                    tilePolygon = None
                    tileMask = None
                tiles.append(
                    hgtTile(
                        {
                            "bbox": inputBbox,
                            "data": inputData,
                            "increments": (self.lonIncrement, self.latIncrement),
                            "polygon": tilePolygon,
                            "mask": tileMask,
                            "transform": self.transform,
                        }
                    )
                )
                # print("depth: {:d}".format(depth))
                # if depth>20:
                # os._exit(11)

        tiles = []
        bbox, truncatedData = truncateData(area, self.zData)
        chopData(bbox, truncatedData)
        return tiles


class hgtTile:
    """is a handle for hgt data tiles as generated by hgtFile.makeTiles()."""

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
        self.polygons = tile["polygon"]
        self.mask = tile["mask"]
        self.transform = tile["transform"]
        self.xData = numpy.arange(self.numOfCols) * self.lonIncrement + self.minLon
        self.yData = numpy.arange(self.numOfRows) * self.latIncrement * -1 + self.maxLat
        self.minEle, self.maxEle = self.getElevRange()

    def get_stats(self) -> str:
        """Get some statistics about the tile."""
        minLon, minLat, maxLon, maxLat = transformLonLats(
            self.minLon, self.minLat, self.maxLon, self.maxLat, self.transform
        )
        result = (
            f"tile with {self.numOfRows:d} x {self.numOfCols:d} points, "
            f"bbox: ({minLon:.2f}, {minLat:.2f}, {maxLon:.2f}, {maxLat:.2f})"
            f"\nminimum elevation: {self.minEle:.2f}\nmaximum elevation: {self.maxEle:.2f}"
        )
        return result

    def printStats(self) -> None:
        """prints some statistics about the tile."""
        print(f"\n{self.get_stats()}")

    def getElevRange(self) -> Tuple[float, float]:
        """returns minEle, maxEle of the current tile.

        We don't have to care about -0x8000 values here since these are masked
        so that self.zData's min and max methods will yield proper values.
        """
        minEle = self.zData.min()
        maxEle = self.zData.max()
        return minEle, maxEle

    def bbox(self, doTransform=True) -> Tuple[float, float, float, float]:
        """returns the bounding box of the current tile."""
        if doTransform:
            return transformLonLats(
                self.minLon, self.minLat, self.maxLon, self.maxLat, self.transform
            )
        else:
            return self.minLon, self.minLat, self.maxLon, self.maxLat

    def contourLines(
        self,
        stepCont=20,
        maxNodesPerWay=0,
        noZero=False,
        minCont=None,
        maxCont=None,
        rdpEpsilon=None,
    ) -> Tuple[Iterable[int], ContourObject]:
        """generates contour lines using matplotlib.

        <stepCont> is height difference of contiguous contour lines in meters
        <maxNodesPerWay>:  the maximum number of nodes contained in each way
        <noZero>:  if True, the 0 m contour line is discarded
        <minCont>:  lower limit of the range to generate contour lines for
        <maxCont>:  upper limit of the range to generate contour lines for
        <rdpEpsilon>: epsilon to use in RDP contour line simplification

        A list of elevations and a ContourObject is returned.
        """

        def getContLimit(ele: int, step: int) -> int:
            """returns a proper value for the lower or upper limit to generate contour
            lines for.
            """
            if ele % step == 0:
                return ele
            corrEle: int = ele + step - ele % step
            return corrEle

        min_cont: int = minCont or getContLimit(self.minEle, stepCont)
        max_cont: int = maxCont or getContLimit(self.maxEle, stepCont)
        levels: Iterable[int]
        if noZero:
            levels = [
                l for l in range(int(min_cont), int(max_cont), stepCont) if l != 0
            ]
        else:
            levels = range(int(min_cont), int(max_cont), stepCont)
        x, y = numpy.meshgrid(self.xData, self.yData)
        # z data is a masked array filled with nan.
        z: numpy.typing.ArrayLike = numpy.ma.array(
            self.zData, mask=self.mask, fill_value=float("NaN"), keep_mask=True
        )

        contours: ContourObject = build_contours(
            x, y, z, maxNodesPerWay, self.transform, self.polygons, rdpEpsilon
        )
        return levels, contours

    def countNodes(
        self,
        maxNodesPerWay=0,
        stepCont=20,
        minCont=None,
        maxCont=None,
        rdpEpsilon=None,
    ):
        """counts the total number of nodes and paths in the current tile
        as written to output.

        <maxNodesPerWay> is the maximal number of nodes per way or 0 for uncut ways
        <stepCont> is height difference of contiguous contour lines in meters
        <minCont>:  lower limit of the range to generate contour lines for
        <maxCont>:  upper limit of the range to generate contour lines for
        <rdpEpsilon>: epsilon to use in RDP contour line simplification
        """
        if not (self.elevations and self.contourData):
            elevations, contourData = self.contourLines(
                stepCont, maxNodesPerWay, minCont, maxCont, rdpEpsilon
            )
        else:
            elevations, contourData = self.elevations, self.contourData
        numOfNodesWays = [contourData.trace(e)[1:] for e in elevations]
        numOfNodes = sum([n for n, w in numOfNodesWays])
        numOfWays = sum([w for n, w in numOfNodesWays])
        return numOfNodes, numOfWays

    def plotData(self, plotPrefix="heightPlot"):
        """generates plot data in the file specified by <plotFilename>."""
        filename = (
            makeBBoxString(self.bbox(doTransform=True)).format(plotPrefix + "_")
            + ".xyz"
        )
        try:
            plotFile = open(filename, "w")
        except:
            raise IOError("could not open plot file {0:s} for writing".format(filename))
        for latIndex, row in enumerate(self.zData):
            lat = self.maxLat - latIndex * self.latIncrement
            for lonIndex, height in enumerate(row):
                lon = self.minLon + lonIndex * self.lonIncrement
                plotFile.write("{0:.7f} {1:.7f} {2:d}\n".format(lon, lat, height))
