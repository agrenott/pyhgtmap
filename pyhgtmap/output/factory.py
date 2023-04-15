import os
from typing import Any, List, Tuple

import pyhgtmap
import pyhgtmap.output
from pyhgtmap import hgt
from pyhgtmap.output import Output, o5mUtil, osmUtil, pbfUtil

from . import make_elev_classifier


def make_osm_filename(
    borders: Tuple[float, float, float, float], opts, input_files_names: List[str]
) -> str:
    """generate a filename for the output osm file. This is done using the bbox
    of the current hgt file.
    """
    if opts.outputPrefix:
        prefix = "{0:s}_".format(opts.outputPrefix)
    else:
        prefix = ""
    srcNameMiddles = [
        os.path.split(os.path.split(srcName)[0])[1].lower()
        for srcName in input_files_names
    ]
    for srcNameMiddle in set(srcNameMiddles):
        if srcNameMiddle.lower()[:5] in ["srtm1", "srtm3", "view1", "view3"]:
            continue
        elif not opts.dataSource:
            # files from the command line, this could be something custom
            srcTag = ",".join(set(srcNameMiddles))
            # osmName = hgt.makeBBoxString(borders).format(prefix) + "_{0:s}.osm".format(srcTag)
            osmName = hgt.makeBBoxString(borders).format(prefix) + "_local-source.osm"
            break
        else:
            osmName = hgt.makeBBoxString(borders).format(prefix) + ".osm"
            break
    else:
        srcTag = ",".join([s for s in opts.dataSource if s in set(srcNameMiddles)])
        osmName = hgt.makeBBoxString(borders).format(prefix) + "_{0:s}.osm".format(
            srcTag
        )
    if opts.gzip:
        osmName += ".gz"
    elif opts.pbf:
        osmName += ".pbf"
    elif opts.o5m:
        osmName = osmName[:-4] + ".o5m"
    return osmName


bboxStringtypes = (type(str()), type(bytes()), type(bytearray()))


def makeBoundsString(bbox: Any) -> str:
    """returns an OSM XML bounds tag.

    The input <bbox> may be a list or tuple of floats or an area string as passed
    to the --area option of pyhgtmap in the following order:
    minlon, minlat, maxlon, maxlat.
    """
    if type(bbox) in bboxStringtypes and bbox.count(":") == 3:
        bbox = bbox.split(":")
    minlon, minlat, maxlon, maxlat = [float(i) for i in bbox]
    return '<bounds minlat="{0:.7f}" minlon="{1:.7f}" maxlat="{2:.7f}" maxlon="{3:.7f}"/>'.format(
        minlat, minlon, maxlat, maxlon
    )


def get_osm_output(
    opts, input_files_names: List[str], bounds: Tuple[float, float, float, float]
) -> Output:
    """Return the proper OSM Output generator."""
    outputFilename = make_osm_filename(bounds, opts, input_files_names)
    elevClassifier = make_elev_classifier(*[int(h) for h in opts.lineCats.split(",")])
    output: Output
    if opts.pbf:
        output = pbfUtil.Output(
            outputFilename,
            opts.osmVersion,
            pyhgtmap.__version__,
            bounds,
            elevClassifier,
        )
    elif opts.o5m:
        output = o5mUtil.Output(
            outputFilename,
            opts.osmVersion,
            pyhgtmap.__version__,
            bounds,
            elevClassifier,
            writeTimestamp=opts.writeTimestamp,
        )
    else:
        # standard XML output, possibly gzipped
        output = osmUtil.Output(
            outputFilename,
            osmVersion=opts.osmVersion,
            pyhgtmap_version=pyhgtmap.__version__,
            boundsTag=makeBoundsString(bounds),
            gzip=opts.gzip,
            elevClassifier=elevClassifier,
            timestamp=opts.writeTimestamp,
        )
    return output
