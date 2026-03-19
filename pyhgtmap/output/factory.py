from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pyhgtmap
import pyhgtmap.output
from pyhgtmap import hgt
from pyhgtmap.output import Output, o5mUtil, osmUtil, pbfUtil
from pyhgtmap.sources.pool import ALL_SUPPORTED_SOURCES

from . import make_elev_classifier

if TYPE_CHECKING:
    from pyhgtmap import BBox
    from pyhgtmap.configuration import Configuration


def make_osm_filename(
    borders: BBox,
    opts: Configuration,
    input_files_names: list[str],
) -> str:
    """generate a filename for the output osm file. This is done using the bbox
    of the current hgt file.
    """

    prefix = f"{opts.outputPrefix:s}_" if opts.outputPrefix else ""
    srcNameMiddles = [
        os.path.split(os.path.split(srcName)[0])[1].lower()
        for srcName in input_files_names
    ]
    for srcNameMiddle in set(srcNameMiddles):
        if not opts.dataSources:
            # files from the command line, this could be something custom
            srcTag = ",".join(set(srcNameMiddles))
            # osmName = hgt.makeBBoxString(borders).format(prefix) + "_{0:s}.osm".format(srcTag)
            osmName = hgt.makeBBoxString(borders).format(prefix) + "_local-source.osm"
            break
        elif srcNameMiddle.lower()[:5] in ALL_SUPPORTED_SOURCES:
            continue
        else:
            osmName = hgt.makeBBoxString(borders).format(prefix) + ".osm"
            break
    else:
        if not opts.dataSources:
            raise ValueError("opts.dataSources is not defined")
        srcTag = ",".join([s for s in opts.dataSources if s in set(srcNameMiddles)])
        osmName = hgt.makeBBoxString(borders).format(prefix) + f"_{srcTag:s}.osm"
    if opts.gzip:
        osmName += ".gz"
    elif opts.pbf:
        osmName += ".pbf"
    elif opts.o5m:
        osmName = osmName[:-4] + ".o5m"
    return osmName


def get_osm_output(
    opts: Configuration,
    input_files_names: list[str],
    bounds: BBox,
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
            bbox=bounds,
            gzip=opts.gzip,
            elevClassifier=elevClassifier,
            timestamp=opts.writeTimestamp,
        )
    return output
