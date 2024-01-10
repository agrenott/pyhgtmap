from __future__ import annotations

import logging
import os
import sys
from contextlib import suppress
from typing import TYPE_CHECKING, Iterable, cast

import numpy
import numpy.typing
import shapely
from matplotlib.path import Path as PolygonPath
from scipy import ndimage

from pyhgtmap import BBox
from pyhgtmap.hgt import TransformFunType, transformLonLats

from .tile import HgtTile

if TYPE_CHECKING:
    from pyhgtmap import Polygon, PolygonsList
    from pyhgtmap.cli import Configuration

    with suppress(ImportError):
        from osgeo import osr

meters2Feet = 1.0 / 0.3048

logger = logging.getLogger(__name__)

GEOTIFF_ERROR = "GeoTiff optional support not enabled; please install with 'pip install pyhgtmap[geotiff]'"


class hgtError(Exception):
    """is the main class of visible exceptions from this file."""


class filenameError(hgtError):
    """is raised when parsing bad filenames."""


class elevationError(hgtError):
    """is raised when trying to deal with elevations out of range."""


def parse_polygons_file(filename: str) -> tuple[str, PolygonsList]:
    """reads polygons from a file like one included in
    http://download.geofabrik.de/clipbounds/clipbounds.tgz
    and returns it as list of (<lon>, <lat>) tuples.
    """
    with open(filename) as polygon_file:
        lines = [
            line.strip().lower()
            for line in polygon_file.read().split("\n")
            if line.strip()
        ]
    polygons: PolygonsList = []
    curPolygon: Polygon = []
    for line in lines:
        if line in [str(i) for i in range(1, lines.count("end"))]:
            # new polygon begins
            curPolygon = []
        elif line == "end" and len(curPolygon) > 0:
            # polygon ends
            polygons.append(curPolygon)
            curPolygon = []
        elif len(line.split()) == 2:
            lon, lat = line.split()
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
        f"{minLon:.7f}:{minLat:.7f}:{maxLon:.7f}:{maxLat:.7f}",
        polygons,
    )


def parse_hgt_filename(
    filename: str,
    corrx: float,
    corry: float,
) -> BBox:
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
            f"something wrong with latitude coding in filename {filename:s}",
        )
    maxLat = minLat + 1
    if lonSwitch == "E" and lonValue.isdigit():
        minLon = int(lonValue)
    elif lonSwitch == "W" and lonValue.isdigit():
        minLon = -1 * int(lonValue)
    else:
        raise filenameError(
            f"something wrong with longitude coding in filename {filename:s}",
        )
    maxLon = minLon + 1
    return BBox(minLon + corrx, minLat + corry, maxLon + corrx, maxLat + corry)


def get_transform(
    file_proj: osr.SpatialReference, reverse=False
) -> TransformFunType | None:
    """
    Returns a function to transform coordinate system of a list of points,
    from original projection to EPSG:4326 (or the otherway around).
    """
    try:
        from osgeo import osr
    except ModuleNotFoundError:
        raise ImportError(GEOTIFF_ERROR) from None

    n = osr.SpatialReference()
    n.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    n.ImportFromEPSG(4326)
    oAuth = file_proj.GetAttrValue("AUTHORITY", 1)
    nAuth = n.GetAttrValue("AUTHORITY", 1)
    if nAuth == oAuth:
        return None
    else:
        if reverse:
            t = osr.CoordinateTransformation(n, file_proj)
        else:
            t = osr.CoordinateTransformation(file_proj, n)

        def transform(
            points: Iterable[tuple[float, float]],
        ) -> Iterable[tuple[float, float]]:
            return [
                p[:2]
                for p in t.TransformPoints(points)
                if not any(el == float("inf") for el in p[:2])
            ]

        return transform


def parse_geotiff_bbox(
    filename: str,
    corrx: float,
    corry: float,
    doTransform: bool,
) -> BBox:
    try:
        from osgeo import gdal, osr

        gdal.UseExceptions()
    except ModuleNotFoundError:
        raise ImportError(GEOTIFF_ERROR) from None
    try:
        g: gdal.Dataset = gdal.Open(filename)
        geoTransform = g.GetGeoTransform()
        if geoTransform[2] != 0 or geoTransform[4] != 0:
            sys.stderr.write(
                "Can't handle geotiff {!s} with geo transform {!s}\n".format(
                    filename,
                    geoTransform,
                ),
            )
            raise hgtError
        fileProj = osr.SpatialReference()
        fileProj.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        fileProj.ImportFromWkt(g.GetProjectionRef())
        numOfCols = g.RasterXSize
        numOfRows = g.RasterYSize
    except Exception:
        raise hgtError(f"Can't handle geotiff file {filename!s}") from None
    lonIncrement = geoTransform[1]
    latIncrement = geoTransform[5]
    minLon = geoTransform[0] + 0.5 * lonIncrement
    maxLat = geoTransform[3] + 0.5 * latIncrement
    minLat = maxLat + (numOfRows - 1) * latIncrement
    maxLon = minLon + (numOfCols - 1) * lonIncrement
    # get the transformation function from fileProj to EPSG:4326 for this geotiff file
    transform: TransformFunType | None = get_transform(fileProj)
    if doTransform:
        # transformLonLats will return input values if transform is None
        minLon, minLat, maxLon, maxLat = transformLonLats(
            minLon,
            minLat,
            maxLon,
            maxLat,
            transform,
        )
        return BBox(minLon + corrx, minLat + corry, maxLon + corrx, maxLat + corry)
    else:
        # we need to take care for corrx, corry values then, which are always expected
        # to be EPSG:4326, so transform, add corrections, and transform back to
        # input projection
        # transformation (input projection) -> (epsg:4326)
        minLon, minLat, maxLon, maxLat = transformLonLats(
            minLon,
            minLat,
            maxLon,
            maxLat,
            transform,
        )
        minLon += corrx
        maxLon += corrx
        minLat += corry
        maxLat += corry
        reverseTransform: TransformFunType | None = get_transform(
            fileProj,
            reverse=True,
        )
        # transformation (epsg:4326) -> (input projection)
        minLon, minLat, maxLon, maxLat = transformLonLats(
            minLon,
            minLat,
            maxLon,
            maxLat,
            reverseTransform,
        )
        return BBox(minLon, minLat, maxLon, maxLat)


def parse_file_for_bbox(
    fullFilename: str,
    corrx: float,
    corry: float,
    doTransform: bool,
) -> BBox:
    fileExt: str = os.path.splitext(fullFilename)[1].lower().replace(".", "")
    if fileExt == "hgt":
        return parse_hgt_filename(os.path.split(fullFilename)[1], corrx, corry)
    elif fileExt in ("tif", "tiff", "vrt"):
        return parse_geotiff_bbox(fullFilename, corrx, corry, doTransform)
    raise ValueError(f"Unsupported extension {fileExt}")


def calc_hgt_area(
    filenames: list[tuple[str, bool]],
    corrx: float,
    corry: float,
) -> BBox:
    bboxes = [
        parse_file_for_bbox(f[0], corrx, corry, doTransform=True) for f in filenames
    ]
    minLon = sorted([b[0] for b in bboxes])[0]
    minLat = sorted([b[1] for b in bboxes])[0]
    maxLon = sorted([b[2] for b in bboxes])[-1]
    maxLat = sorted([b[3] for b in bboxes])[-1]
    return BBox(minLon, minLat, maxLon, maxLat)


BBOX_EXPAND_EPSILON = 0.1


def clip_polygons(
    polygons: PolygonsList,
    clip_polygon: Iterable[tuple[float, float]],
) -> PolygonsList:
    """
    Clips a list of polygons to a given clip polygon.

    Args:
        polygons: A list of polygons to be clipped.
        clip_polygon: The clip polygon to be used for clipping.

    Returns:
        A list of clipped polygons.
    """
    bbox_shape = shapely.Polygon(clip_polygon)
    clipped_polygons: PolygonsList = []
    for p in polygons:
        # Intersect each input polygon with the clip one
        clipped_p = shapely.intersection(shapely.Polygon(p), bbox_shape)
        # Resulting intersection(s) might have several forms
        if isinstance(clipped_p, (shapely.MultiPolygon, shapely.GeometryCollection)):
            # Keep only polygons intersections
            clipped_polygons += [
                list(poly.exterior.coords)
                for poly in clipped_p.geoms
                if isinstance(poly, shapely.Polygon) and not poly.is_empty
            ]
        elif isinstance(clipped_p, shapely.Polygon) and not clipped_p.is_empty:
            clipped_polygons.append(list(clipped_p.exterior.coords))

    return clipped_polygons


def polygon_mask(
    x_data: numpy.ndarray,
    y_data: numpy.ndarray,
    polygons: PolygonsList,
    transform: TransformFunType | None,
) -> numpy.ndarray:
    """return a mask on self.zData corresponding to all polygons in self.polygons.
    <xData> is meant to be a 1-D array of longitude values, <yData> a 1-D array of
    latitude values.  An array usable as mask for the corresponding zData
    2-D array is returned.
    <transform> may be transform function from the file's projection to EPSG:4326,
    which is the projection used within polygon files.
    """
    X, Y = numpy.meshgrid(x_data, y_data)
    xyPoints: Iterable[tuple[float, float]] = numpy.vstack(([X.T], [Y.T])).T.reshape(
        len(x_data) * len(y_data),
        2,
    )

    # To improve performances, clip original polygons to current data boundaries.
    # Slightly expand the bounding box, as PolygonPath.contains_points result is undefined for points on boundary
    # https://matplotlib.org/stable/api/path_api.html#matplotlib.path.Path.contains_point
    bbox_points: Iterable[tuple[float, float]] = [
        (x_data.min() - BBOX_EXPAND_EPSILON, y_data.min() - BBOX_EXPAND_EPSILON),
        (x_data.min() - BBOX_EXPAND_EPSILON, y_data.max() + BBOX_EXPAND_EPSILON),
        (x_data.max() + BBOX_EXPAND_EPSILON, y_data.max() + BBOX_EXPAND_EPSILON),
        (x_data.max() + BBOX_EXPAND_EPSILON, y_data.min() - BBOX_EXPAND_EPSILON),
        (x_data.min() - BBOX_EXPAND_EPSILON, y_data.min() - BBOX_EXPAND_EPSILON),
    ]
    if transform is not None:
        xyPoints = transform(xyPoints)
        bbox_points = transform(bbox_points)

    clipped_polygons = clip_polygons(polygons, bbox_points)

    if not clipped_polygons:
        # Empty intersection: data is fully masked
        # Simply return a 1x1 True mask
        return numpy.array([True])

    maskArray = numpy.ma.array(numpy.empty((len(x_data) * len(y_data), 1)))
    for p in clipped_polygons:
        # run through all polygons and combine masks
        mask = PolygonPath(p).contains_points(xyPoints)  # type: ignore[arg-type]
        maskArray = numpy.ma.array(maskArray, mask=mask, keep_mask=True)
    return numpy.invert(maskArray.mask.reshape(len(y_data), len(x_data)))


def super_sample(
    input_data: numpy.ndarray,
    input_mask: numpy.ndarray,
    zoom_level: float,
) -> tuple[numpy.ndarray, numpy.ndarray]:
    """Super sample the input data and associated mask."""
    logger.debug("Smoothing input by a ratio of %f", zoom_level)
    # Limit order to 1 to avoid artifacts on constant value boundaries (eg. limit of sea areas)
    # Round result to avoid oscillations around 0 due to spline interpolation
    out_data = numpy.around(
        cast(numpy.ndarray, ndimage.zoom(input_data, zoom_level, order=3)),
        0,
    )
    # Resize mask independantly, using 0 order to avoid artifacts
    out_mask = ndimage.zoom(input_mask, zoom_level, order=0)
    # from PIL import Image as im
    # im.fromarray(input_data, mode="F").save('orig.tiff')
    # im.fromarray(out_data, mode="F").save('super.tiff')
    return out_data, out_mask


class HgtFile:
    """is a handle for SRTM data files"""

    def __init__(
        self,
        filename: str,
        corrx: float,
        corry: float,
        polygons: PolygonsList | None = None,
        checkPoly=False,
        voidMax: int = -0x8000,
        feetSteps=False,
        smooth_ratio: float = 1.0,
    ) -> None:
        """tries to open <filename> and extracts content to self.zData.

        <corrx> and <corry> are longitude and latitude corrections (floats)
        as passed to pyhgtmap on the commandline.
        """
        self.feetSteps = feetSteps
        self.fullFilename = filename
        self.filename = os.path.split(filename)[-1]
        self.fileExt = os.path.splitext(self.filename)[1].lower().replace(".", "")
        # Assigned by initAsXxx
        self.polygons: PolygonsList | None
        self.zData: numpy.ma.masked_array
        # Thjose represent the bounding box coordinates of the file,
        # ** using the actual file's projection coordinates!!! **
        self.minLon: float
        self.minLat: float
        self.maxLon: float
        self.maxLat: float

        if self.fileExt == "hgt":
            self.init_as_hgt(corrx, corry, polygons, checkPoly, voidMax, smooth_ratio)
        elif self.fileExt in ("tif", "tiff", "vrt"):
            self.init_as_geotiff(
                corrx, corry, polygons, checkPoly, voidMax, smooth_ratio
            )

        # Best effort stats display
        with suppress(Exception):
            minLon, minLat, maxLon, maxLat = transformLonLats(
                self.minLon,
                self.minLat,
                self.maxLon,
                self.maxLat,
                self.transform,
            )
            check_poly_txt = {True: ", checking polygon borders", False: ""}[checkPoly]
            logger.info(
                f"{self.fileExt:s} file {self.fullFilename:s}: {self.numOfCols:d} x "
                f"{self.numOfRows:d} points, bbox: ({minLon:.5f}, {minLat:.5f}, "
                f"{maxLon:.5f}, {maxLat:.5f}){check_poly_txt:s}",
            )

        # Used only when initialized from GeoTIFF
        self.transform: TransformFunType | None
        self.reverseTransform: TransformFunType | None

    def init_as_hgt(
        self,
        corrx: float,
        corry: float,
        polygons: PolygonsList | None,
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
            raw_z_data = (
                numpy.fromfile(self.fullFilename, dtype=">i2")
                .reshape(self.numOfRows, self.numOfCols)
                .astype("float32")
            )

            # Compute mask BEFORE zooming, due to zoom artifacts on void areas boundaries
            voidMask = numpy.asarray(numpy.where(raw_z_data <= voidMax, True, False))
            if smooth_ratio != 1:
                raw_z_data, voidMask = super_sample(raw_z_data, voidMask, smooth_ratio)
                self.numOfRows, self.numOfCols = raw_z_data.shape
            self.zData = numpy.ma.array(
                raw_z_data,
                mask=voidMask,
                fill_value=float("NaN"),
            )
            if self.feetSteps:
                self.zData = self.zData * meters2Feet
        finally:
            self.lonIncrement = 1.0 / (self.numOfCols - 1)
            self.latIncrement = 1.0 / (self.numOfRows - 1)
            self.minLon, self.minLat, self.maxLon, self.maxLat = self.borders(
                corrx,
                corry,
            )
            if checkPoly:
                self.polygons = polygons
            else:
                self.polygons = None
            self.transform = None
            self.reverseTransform = None

    def init_as_geotiff(
        self,
        corrx: float,
        corry: float,
        polygons: PolygonsList | None,
        checkPoly: bool,
        voidMax: int,
        smooth_ratio: float,
    ) -> None:
        """init this hgtFile instance with data from a geotiff image."""
        try:
            from osgeo import gdal, osr

            gdal.UseExceptions()
        except ModuleNotFoundError:
            raise ImportError(GEOTIFF_ERROR) from None

        try:
            g: gdal.Dataset = gdal.Open(self.fullFilename)
            geoTransform = g.GetGeoTransform()
            # we don't need to check for the geo transform, this was already done when
            # calculating the area name from main.py
            fileProj = osr.SpatialReference()
            fileProj.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            fileProj.ImportFromWkt(g.GetProjectionRef())
            self.numOfCols = g.RasterXSize
            self.numOfRows = g.RasterYSize
            # init z data
            raw_z_data = g.GetRasterBand(1).ReadAsArray().astype("float32")
            # Compute mask BEFORE zooming, due to zoom artifacts on void areas boundaries
            voidMask = numpy.asarray(numpy.where(raw_z_data <= voidMax, True, False))
            if smooth_ratio != 1:
                raw_z_data, voidMask = super_sample(raw_z_data, voidMask, smooth_ratio)
                self.numOfRows, self.numOfCols = raw_z_data.shape
            self.zData = numpy.ma.array(
                raw_z_data,
                mask=voidMask,
                fill_value=float("NaN"),
            )
            if self.feetSteps:
                self.zData = self.zData * meters2Feet
            # make x and y data
            self.lonIncrement = geoTransform[1]
            self.latIncrement = -geoTransform[5]
            self.minLon, self.minLat, self.maxLon, self.maxLat = self.borders(
                corrx,
                corry,
            )
            # get the transformation function from fileProj to EPSG:4326 for this geotiff file
            self.transform = get_transform(fileProj)
            self.reverseTransform = get_transform(fileProj, reverse=True)
        finally:
            if checkPoly:
                self.polygons = polygons
            else:
                self.polygons = None

    def borders(self, corrx=0.0, corry=0.0) -> BBox:
        """determines the bounding box of self.filename using parseHgtFilename()."""
        return parse_file_for_bbox(self.fullFilename, corrx, corry, doTransform=False)

    def make_tiles(self, opts: Configuration) -> list[HgtTile]:
        """generate tiles from self.zData according to the given <opts>.area and
        return them as list of hgtTile objects.
        """
        area = opts.area or None
        maxNodes = opts.maxNodesPerTile
        step = int(opts.contourStepSize) or 20

        def truncate_data(
            area: str | None, inputData: numpy.ma.masked_array
        ) -> tuple[BBox, numpy.ma.masked_array]:
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
                    / self.lonIncrement,
                )
                minLatTruncIndex = -1 * int(
                    (bboxMinLat - self.minLat)
                    / (self.maxLat - self.minLat)
                    / self.latIncrement,
                )
                maxLonTruncIndex = int(
                    (bboxMaxLon - self.maxLon)
                    / (self.maxLon - self.minLon)
                    / self.lonIncrement,
                )
                maxLatTruncIndex = -1 * int(
                    (bboxMaxLat - self.maxLat)
                    / (self.maxLat - self.minLat)
                    / self.latIncrement,
                )
                realMinLon = self.minLon + minLonTruncIndex * self.lonIncrement
                realMinLat = self.minLat - minLatTruncIndex * self.latIncrement
                realMaxLon = self.maxLon + maxLonTruncIndex * self.lonIncrement
                realMaxLat = self.maxLat - maxLatTruncIndex * self.latIncrement
                if maxLonTruncIndex == 0:
                    maxLonTruncIndex = None  # type: ignore[assignment]
                if minLatTruncIndex == 0:
                    minLatTruncIndex = None  # type: ignore[assignment]
                zData: numpy.ma.masked_array = inputData[
                    maxLatTruncIndex:minLatTruncIndex,
                    minLonTruncIndex:maxLonTruncIndex,
                ]
                return BBox(realMinLon, realMinLat, realMaxLon, realMaxLat), zData
            else:
                return BBox(
                    self.minLon, self.minLat, self.maxLon, self.maxLat
                ), inputData

        def chop_data(
            inputBbox: BBox,
            inputData: numpy.ma.masked_array,
            depth=0,
        ):
            """chops data and appends chops to tiles if small enough."""

            def estim_num_of_nodes(data: numpy.ma.masked_array) -> int:
                """simple estimation of the number of nodes. The number of nodes is
                estimated by summing over all absolute differences of contiguous
                points in the zData matrix which is previously divided by the step
                size.

                This method works pretty well in areas with no voids (e. g. points
                tagged with the value -32768 (-0x8000)), but overestimates the number of points
                in areas with voids by approximately 0 ... 50 % although the
                corresponding differences are explicitly set to 0.
                """
                helpData = data.filled() / step
                xHelpData = numpy.abs(helpData[:, 1:] - helpData[:, :-1])
                yHelpData = numpy.abs(helpData[1:, :] - helpData[:-1, :])
                estimatedNumOfNodes = numpy.nansum(xHelpData) + numpy.nansum(yHelpData)
                return estimatedNumOfNodes

            def too_many_nodes(data: numpy.ma.masked_array) -> bool:
                """returns True if the estimated number of nodes is greater than
                <maxNodes> and False otherwise.  <maxNodes> defaults to 1000000,
                which is an approximate limit for correct handling of osm files
                in mkgmap.  A value of 0 means no tiling.
                """
                if maxNodes == 0:
                    return False
                return estim_num_of_nodes(data) > maxNodes

            def get_chops(
                unchoppedData: numpy.ma.masked_array, unchoppedBbox
            ) -> tuple[
                tuple[BBox, numpy.ma.masked_array],
                tuple[BBox, numpy.ma.masked_array],
            ]:
                """returns a data chop and the according bbox. This function is
                recursively called until all tiles are estimated to be small enough.

                One could cut the input data either horizontally or vertically depending
                on the shape of the input data in order to achieve more quadratic tiles.
                However, generating contour lines from horizontally cut data appears to be
                significantly faster.
                """
                (
                    unchoppedBboxMinLon,
                    unchoppedBboxMinLat,
                    unchoppedBboxMaxLon,
                    unchoppedBboxMaxLat,
                ) = unchoppedBbox
                unchoppedNumOfRows = unchoppedData.shape[0]
                chopLatIndex = int(unchoppedNumOfRows / 2.0)
                chopLat = unchoppedBboxMaxLat - (chopLatIndex * self.latIncrement)
                lowerChopBbox = BBox(
                    unchoppedBboxMinLon,
                    unchoppedBboxMinLat,
                    unchoppedBboxMaxLon,
                    chopLat,
                )
                upperChopBbox = BBox(
                    unchoppedBboxMinLon,
                    chopLat,
                    unchoppedBboxMaxLon,
                    unchoppedBboxMaxLat,
                )
                lowerChopData = unchoppedData[chopLatIndex:, :]
                upperChopData = unchoppedData[: chopLatIndex + 1, :]
                return (lowerChopBbox, lowerChopData), (upperChopBbox, upperChopData)

            # Discard quickly fully void tiles (eg. middle of the sea)
            if isinstance(inputData, numpy.ma.masked_array):
                voidMaskValues = numpy.unique(inputData.mask)
                if numpy.array_equal(voidMaskValues, [True]):
                    # this tile is full of void values, so discard this tile
                    return

            if too_many_nodes(inputData):
                chops = get_chops(inputData, inputBbox)
                for choppedBbox, choppedData in chops:
                    chop_data(choppedBbox, choppedData, depth + 1)
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
                        tileXData,
                        tileYData,
                        self.polygons,
                        self.transform,
                    )
                    tilePolygon: PolygonsList | None = self.polygons
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
                    HgtTile(
                        bbox=inputBbox,
                        data=inputData,
                        increments=(self.lonIncrement, self.latIncrement),
                        polygons=tilePolygon,
                        mask=tileMask,
                        transform=self.transform,
                    ),
                )

        tiles: list[HgtTile] = []
        bbox, truncatedData = truncate_data(area, self.zData)
        chop_data(bbox, truncatedData)
        return tiles
