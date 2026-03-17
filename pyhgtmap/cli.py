from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, cast

from configargparse import ArgumentDefaultsHelpFormatter, ArgumentParser

from pyhgtmap import BBox, __version__
from pyhgtmap.configuration import CONFIG_FILENAME, Configuration, NestedConfig
from pyhgtmap.hgt.file import parse_polygons_file
from pyhgtmap.sources.pool import ALL_SUPPORTED_SOURCES, Pool

if TYPE_CHECKING:
    from pyhgtmap.sources import Source


def _str_to_bbox(area_str: str) -> BBox:
    """Convert area string format 'left:bottom:right:top' to BBox."""
    parts = area_str.split(":")
    if len(parts) != 4:
        raise ValueError(f"Invalid area format: {area_str}")
    return BBox(*[float(x) for x in parts])


def build_common_parser() -> ArgumentParser:
    """Build the common argument parser for pyhgtmap."""
    default_config = Configuration()
    parser = ArgumentParser(
        default_config_files=[CONFIG_FILENAME],
        formatter_class=ArgumentDefaultsHelpFormatter,
        usage="%(prog)s [options] [<hgt or GeoTiff file>] [<hgt or GeoTiff files>]"
        "\npyhgtmap generates contour lines from multiple elevation data sources"
        "\nincluding NASA SRTM v3.0, GeoTiff data, and others via plugins."
        "\nThere are three ways to use pyhgtmap: First, it can process existing"
        "\nsource files given as command-line arguments.  Note that filenames must"
        "\nhave the format [N|S]YY[W|E]XXX.hgt, with YY the latitude and XXX the"
        "\nlongitude of the lower left corner of the tile.  Second, it can be used"
        "\nwith an area definition as input.  Third, you can specify a polygon"
        "\ndefinition.  In the latter two cases, pyhgtmap will look for a cache"
        f"\ndirectory (default: '{default_config.hgtdir}') and download the needed elevation data files"
        "\nautomatically if not cached.  If no cache directory is found, it will be"
        "\ncreated.  Data sources are specified using the --sources parameter and can"
        "\ninclude NASA SRTM (srtm1, srtm3), Viewfinder Panoramas (view1, view3),"
        "\nALOS (alos1, alos3), and others.  For higher resolution data, use"
        "\n--sources=srtm1 for 1 arc second NASA SRTM data (available between 60°S"
        "\nand 60°N).  For global coverage at 3 arc second resolution, use"
        "\n--sources=view3 or --sources=srtm3.  Multiple sources can be specified"
        "\nas a comma-separated list; the first available source for each tile will be used.",
    )
    parser.add_argument(
        "-a",
        "--area",
        help="specify the area to generate contour OSM data for using a bounding box."
        "\nIf necessary, elevation data files are downloaded from the configured"
        "\ndata sources. Specify as <left>:<bottom>:<right>:<top> in degrees of"
        "\nlatitude and longitude, respectively. Latitudes south of the equator and"
        "\nlongitudes west of Greenwich may be given as negative decimal numbers."
        "\nIf this option is given, any specified HGT files will be omitted.",
        dest="area",
        metavar="LEFT:BOTTOM:RIGHT:TOP",
        action="store",
        default=default_config.area,
        type=_str_to_bbox,
    )
    parser.add_argument(
        "--polygon",
        help="use polygon FILENAME as downloaded from"
        "\nhttp://download.geofabrik.de/clipbounds/ as bounds for the output contour"
        "\ndata.  The computation time will be somewhat higher then.  If specified,"
        "\na bounding box passed to the --area option will be ignored.",
        dest="polygon_file",
        action="store",
        metavar="FILENAME",
        default=default_config.polygon_file,
    )
    parser.add_argument(
        "--download-only",
        help="only download needed files,\ndon't write contour data.",
        action="store_true",
        default=default_config.downloadOnly,
        dest="downloadOnly",
    )
    parser.add_argument(
        "-s",
        "--step",
        help="specify contour line step size in"
        "\nmeters or feet, if using the --feet option.",
        dest="contourStepSize",
        metavar="STEP",
        action="store",
        default=default_config.contourStepSize,
    )
    parser.add_argument(
        "-f",
        "--feet",
        help="output contour lines in feet steps\nrather than in meters.",
        action="store_true",
        default=default_config.contourFeet,
        dest="contourFeet",
    )
    parser.add_argument(
        "-0",
        "--no-zero-contour",
        help="say this, if you don't want"
        "\nthe sea level contour line (0 m) (which sometimes looks rather ugly) to"
        "\nappear in the output.",
        action="store_true",
        default=default_config.noZero,
        dest="noZero",
    )
    parser.add_argument(
        "-o",
        "--output-prefix",
        help="specify a prefix for the\nfilenames of the output osm file(s).",
        dest="outputPrefix",
        metavar="PREFIX",
        action="store",
        default=default_config.outputPrefix,
    )
    parser.add_argument(
        "-p",
        "--plot",
        help="specify the prefix for the files to write"
        "\nlongitude/latitude/elevation data to instead of generating contour"
        "\nosm.",
        dest="plotPrefix",
        action="store",
        default=default_config.plotPrefix,
    )
    parser.add_argument(
        "-c",
        "--line-cat",
        help="specify a string of two comma"
        "\nseperated integers for major and medium elevation categories, e. g."
        f"\n'{default_config.lineCats}' which is the default. This is needed for fancy rendering.",
        dest="lineCats",
        metavar="ELEVATION_MAJOR,ELEVATION_MEDIUM",
        action="store",
        default=default_config.lineCats,
    )
    parser.add_argument(
        "-j",
        "--jobs",
        help="number of jobs to be run in parallel (POSIX only)",
        dest="nJobs",
        action="store",
        type=int,
        default=default_config.nJobs,
    )
    parser.add_argument(
        "--osm-version",
        help="pass a number as OSM-VERSION to"
        "\nuse for the output. If you need an older version, try 0.5.",
        metavar="OSM-VERSION",
        dest="osmVersion",
        action="store",
        default=default_config.osmVersion,
        type=float,
    )
    parser.add_argument(
        "--write-timestamp",
        help="write the timestamp attribute of"
        "\nnode and way elements in OSM XML and o5m output.  This might be needed by some"
        "\ninterpreters.  In o5m output, this also triggers writing of changeset and"
        "\nuser information.",
        dest="writeTimestamp",
        action="store_true",
        default=default_config.writeTimestamp,
    )
    parser.add_argument(
        "--start-node-id",
        help="specify an integer as id of"
        f"\nthe first written node in the output OSM xml.  It defaults to {default_config.startId}"
        "\nbut some OSM xml mergers are running into trouble when encountering non"
        "\nunique ids.  In this case and for the moment, it is safe to say"
        "\n10000000000 (ten billion) then.",
        dest="startId",
        type=int,
        default=default_config.startId,
        action="store",
        metavar="NODE-ID",
    )
    parser.add_argument(
        "--start-way-id",
        help="specify an integer as id of"
        f"\nthe first written way in the output OSM xml.  It defaults to {default_config.startWayId}"
        "\nbut some OSM xml mergers are running into trouble when encountering non"
        "\nunique ids.  In this case and for the moment, it is safe to say"
        "\n10000000000 (ten billion) then.",
        dest="startWayId",
        type=int,
        default=default_config.startWayId,
        action="store",
        metavar="WAY-ID",
    )
    parser.add_argument(
        "--max-nodes-per-tile",
        help="specify an integer as a maximum"
        f"\nnumber of nodes per generated tile.  It defaults to {default_config.maxNodesPerTile},"
        "\nwhich is approximately the maximum number of nodes handled properly"
        "\nby mkgmap.  For bigger tiles, try higher values. For a single file"
        "\noutput, say 0 here (this disables any parallelization).",
        dest="maxNodesPerTile",
        type=int,
        default=default_config.maxNodesPerTile,
        action="store",
    )
    parser.add_argument(
        "--max-nodes-per-way",
        help="specify an integer as a maximum"
        f"\nnumber of nodes per way.  It defaults to {default_config.maxNodesPerWay}, which is the maximum value"
        "\nfor OSM api version 0.6.  Say 0 here, if you want unsplitted ways.",
        dest="maxNodesPerWay",
        type=int,
        default=default_config.maxNodesPerWay,
        action="store",
    )
    parser.add_argument(
        "--simplifyContoursEpsilon",
        help="simplify contour lines"
        "\nusing the Ramer-Douglas-Peucker (RDP) algorithm with this EPSILON value. "
        "\nThe larger the value, the more simplified the contour lines.  The"
        "\nvalue passed will be directly used, i. e. in case of WGS84 based"
        "\nreference systems like EPSG:4326, the passed value is interpreted as"
        "\ndegrees of latitude and longitude, respectively.  Use a value of 0.0 to"
        "\nremove only vertices on straight lines.  Sensible values to reduce the"
        "\noutput file size while preserving reasonable accuracy are dependent on"
        "\nthe file resolution.  For SRTM3 data, some value between 0.0001 and"
        "\n0.0005 seems reasonable, reducing the file size by something like one"
        f"\nor two thirds. The default is {default_config.rdpEpsilon} value to remove dupe points and optimize"
        "\nstraight lines.",
        dest="rdpEpsilon",
        type=float,
        default=default_config.rdpEpsilon,
        action="store",
        metavar="EPSILON",
    )
    parser.add_argument(
        "--disableRDP",
        help="Fully disable contour simplification",
        dest="disableRdp",
        action="store_true",
    )
    parser.add_argument(
        "--smooth",
        help="Smooth contour lines by zooming input files by SMOOTH_RATIO. EXPERIMENTAL."
        "\nA zoom factor of 3 results in a 9-times bigger input set, and increases processing"
        "\ntime and output siz A LOT. You should probably increase --max-nodes-per-tile to avoid"
        "'maximum recursion depth exceeded' error in tiles chopping.",
        dest="smooth_ratio",
        action="store",
        type=float,
        default=default_config.smooth_ratio,
        metavar="SMOOTH_RATIO",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--gzip",
        help="turn on gzip compression of output files."
        "\nThis reduces the needed disk space but results in higher computation"
        "\ntimes. Specify an integer between 1 and 9.  1 means low compression and"
        "\nfaster computation, 9 means high compression and lower computation.",
        dest="gzip",
        action="store",
        default=default_config.gzip,
        metavar="COMPRESSLEVEL",
        type=int,
    )
    group.add_argument(
        "--pbf",
        help="write protobuf binary files instead of OSM"
        "\nXML.  This reduces the needed disk space. Be sure the programs you"
        "\nwant to use the output files with are capable of pbf parsing.  The"
        "\noutput files will have the .osm.pbf extension.",
        action="store_true",
        default=default_config.pbf,
        dest="pbf",
    )
    group.add_argument(
        "--o5m",
        help="write o5m binary files instead of OSM"
        "\nXML.  This reduces the needed disk space. Be sure the programs you"
        "\nwant to use the output files with are capable of o5m parsing.  The"
        "\noutput files will have the .o5m extension.",
        action="store_true",
        default=default_config.o5m,
        dest="o5m",
    )
    # Backward compatible with old "source" option, thanks to argparse abbreviations
    # https://docs.python.org/3/library/argparse.html#allow-abbrev
    parser.add_argument(
        "--sources",
        "--data-sources",
        help="specify a list of"
        "\nsources to use as comma-separated string.  Available sources are:\n"
        f"\n{', '.join(s for s in ALL_SUPPORTED_SOURCES)}.\nIf specified,"
        "\nthe data sources will be selected using this option as preference list."
        "\nSpecifying --sources=view3,srtm3 for example will prefer viewfinder 3"
        "\narc second data to NASA SRTM 3 arc second data.",
        metavar="DATA-SOURCES",
        type=lambda x: x.lower().split(","),
        default=default_config.dataSources,
        dest="dataSources",
    )
    parser.add_argument(
        "--corrx",
        help="correct x offset of contour lines."
        "\n A setting of --corrx=0.0005 was reported to give good results."
        "\n However, the correct setting seems to depend on where you are, so"
        "\nit is may be better to start with 0 here.",
        metavar="SRTM-CORRX",
        dest="srtmCorrx",
        action="store",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--corry",
        help="correct y offset of contour lines."
        "\n A setting of --corry=0.0005 was reported to give good results."
        "\n However, the correct setting seems to depend on where you are, so"
        "\nit may be better to start with 0 here.",
        metavar="SRTM-CORRY",
        dest="srtmCorry",
        action="store",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--hgtdir",
        help="Cache directory for hgt files."
        "\nThe downloaded SRTM files are stored in a cache directory for later use."
        f"\nThe default directory for this is '{default_config.hgtdir}' in the current directory.  You can"
        "\nspecify another cache directory with this option.",
        dest="hgtdir",
        action="store",
        default="hgt",
        metavar="DIRECTORY",
    )
    parser.add_argument(
        "--void-range-max",
        help="extend the void value range"
        "\nup to this height.  The hgt file format uses a void value which is"
        "\n-0x8000 or, in terms of decimal numbers, -32768.  Some hgt files"
        "\ncontain other negative values which are implausible as height values,"
        "\ne. g. -0x4000 (-16384) or similar.  Since the lowest place on earth is"
        "\nabout -420 m below sea level, it should be safe to say -500 here in"
        "\ncase you encounter strange pyhgtmap behavior such as program aborts"
        "\ndue to exceeding the maximum allowed number of recursions.",
        default=-0x8000,
        type=int,
        metavar="MINIMUM_PLAUSIBLE_HEIGHT_VALUE",
        action="store",
        dest="voidMax",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"pyhgtmap {__version__:s}",
    )
    parser.add_argument(
        "-l",
        "--log",
        dest="logLevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="WARNING",
        help="Set this tool's debug logging level",
    )
    parser.add_argument(
        "filenames",
        type=str,
        action="store",
        nargs="*",
        help="List of files to process (HGT or geotiff).",
    )
    return parser


def add_sources_options(parser: ArgumentParser, root_config: NestedConfig) -> None:
    """Enrich parser and configuration with plugin-specific arguments."""
    for source in Pool.registered_sources():
        cast("type[Source]", source).register_cli_options(parser, root_config)


def parse_command_line(sys_args: list[str]) -> tuple[Configuration, list[str]]:
    """parses the command line."""
    parser = build_common_parser()
    root_configuration = Configuration()
    add_sources_options(parser, root_configuration)

    opts: Configuration = parser.parse_args(sys_args, namespace=root_configuration)

    for s in opts.dataSources:
        if s[:5] not in ALL_SUPPORTED_SOURCES:
            print(f"Unknown data source: {s:s}")
            sys.exit(1)

    if len(opts.filenames) == 0 and not opts.area and not opts.polygon_file:
        parser.print_help()
        sys.exit(1)
    if opts.polygon_file:
        try:
            os.stat(opts.polygon_file)
        except OSError:
            print(f"Couldn't find polygon file: {opts.polygon_file:s}")
            sys.exit(1)
        if not os.path.isfile(opts.polygon_file):
            print(f"Polygon file '{opts.polygon_file:s}' is not a regular file")
            sys.exit(1)
        area_str, opts.polygons = parse_polygons_file(opts.polygon_file)
        opts.area = _str_to_bbox(area_str)

    if not opts.area and opts.downloadOnly:
        # no area, no polygon, so nothing to download
        sys.stderr.write(
            "Nothing to download.  Combine the --download-only option with"
            "\neither one of the --area and --polygon options.\n",
        )
        sys.exit(1)
    if opts.disableRdp:
        opts.rdpEpsilon = None

    return opts, opts.filenames
