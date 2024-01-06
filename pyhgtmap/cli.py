from __future__ import annotations

import os
import sys
from argparse import ArgumentParser, Namespace

from pyhgtmap import NASASRTMUtil, PolygonsList, __version__, configUtil
from pyhgtmap.hgt.file import parse_polygons_file


class Configuration(Namespace):
    """Configuration for pyhgtmap."""

    # Work-around to get typing without a full refactoring of the parser, while
    # providing typing.
    # Sadly some parts have to be duplicated...

    area: str | None
    polygon_file: str | None
    polygon: PolygonsList | None = None
    downloadOnly: bool = False
    contourStepSize: str = "20"
    contourFeet: bool = False
    noZero: bool = False
    outputPrefix: str | None
    plotPrefix: str | None
    lineCats: str = "200,100"
    nJobs: int = 1
    osmVersion: float = 0.6
    writeTimestamp: bool = False
    startId: int = 10000000
    startWayId: int = 10000000
    maxNodesPerTile: int = 1000000
    maxNodesPerWay: int = 2000
    rdpEpsilon: float | None = 0.0
    disableRdp: bool | None
    smooth_ratio: float = 1.0
    gzip: int = 0
    pbf: bool = False
    o5m: bool = False
    srtmResolution: int = 3
    srtmVersion: float = 3.0
    earthexplorerUser: str | None
    earthexplorerPassword: str | None
    viewfinder: int = 0
    dataSource: list[str] | None
    srtmCorrx: float = 0.0
    srtmCorry: float = 0.0
    hgtdir: str | None
    rewriteIndices: bool = False
    voidMax: int = -0x8000
    logLevel: str = "WARNING"
    filenames: list[str]


def parse_command_line(sys_args: list[str]) -> tuple[Configuration, list[str]]:
    """parses the command line."""
    parser = ArgumentParser(
        usage="%(prog)s [options] [<hgt or GeoTiff file>] [<hgt or GeoTiff files>]"
        "\npyhgtmap generates contour lines from NASA SRTM and similar data"
        "\nas well as from GeoTiff data"
        "\nin OSM formats.  For now, there are three ways to achieve this. First,"
        "\nit can be used to process existing source files given as arguments"
        "\non the command line.  Note that the filenames must have the format"
        "\n[N|S]YY[W|E]XXX.hgt, with YY the latitude and XXX the longitude of the"
        "\nlower left corner of the tile.  Second, it can be used with an area"
        "\ndefinition as input.  The third way to use pyhgtmap is to specify a"
        "\npolygon definition.  In the last two cases, pyhgtmap will look for a"
        "\ncache directory (per default: ./hgt/) and the needed SRTM files.  If"
        "\nno cache directory is found, it will be created.  It then downloads"
        "\nall the needed NASA SRTM data files automatically if they are not cached"
        "\nyet.  There is also the possibility of masking the NASA SRTM data with"
        "\ndata from www.viewfinderpanoramas.org which fills voids and other data"
        "\nlacking in the original NASA data set.  Since the 3 arc second data available"
        "\nfrom www.viewfinderpanoramas.org is complete for the whole world,"
        "\ngood results can be achieved by specifying --source=view3.  For higher"
        "\nresolution, the 1 arc second SRTM data in version 3.0 can be used by"
        "\nspecifying --source=srtm1 in combination with --srtm-version=3.0. "
        "\nSRTM 1 arc second data is, however, only available for latitudes"
        "\nbetween 59 degrees of latitude south and 60 degrees of latitude north.",
    )
    parser.add_argument(
        "-a",
        "--area",
        help="choses the area to generate osm SRTM"
        "\ndata for by bounding box. If necessary, files are downloaded from"
        "\nthe NASA server. "
        "\nSpecify as <left>:<bottom>:<right>:<top> in degrees of latitude"
        "\nand longitude, respectively. Latitudes south of the equator and"
        "\nlongitudes west of Greenwich may be given as negative decimal numbers."
        "\nIf this option is given, specified hgt"
        "\nfiles will be omitted.",
        dest="area",
        metavar="LEFT:BOTTOM:RIGHT:TOP",
        action="store",
        default=None,
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
        default=None,
    )
    parser.add_argument(
        "--download-only",
        help="only download needed files,\ndon't write contour data.",
        action="store_true",
        default=False,
        dest="downloadOnly",
    )
    parser.add_argument(
        "-s",
        "--step",
        help="specify contour line step size in"
        "\nmeters or feet, if using the --feet option. The default value is 20.",
        dest="contourStepSize",
        metavar="STEP",
        action="store",
        default="20",
    )
    parser.add_argument(
        "-f",
        "--feet",
        help="output contour lines in feet steps\nrather than in meters.",
        action="store_true",
        default=False,
        dest="contourFeet",
    )
    parser.add_argument(
        "-0",
        "--no-zero-contour",
        help="say this, if you don't want"
        "\nthe sea level contour line (0 m) (which sometimes looks rather ugly) to"
        "\nappear in the output.",
        action="store_true",
        default=False,
        dest="noZero",
    )
    parser.add_argument(
        "-o",
        "--output-prefix",
        help="specify a prefix for the\nfilenames of the output osm file(s).",
        dest="outputPrefix",
        metavar="PREFIX",
        action="store",
        default=None,
    )
    parser.add_argument(
        "-p",
        "--plot",
        help="specify the prefix for the files to write"
        "\nlongitude/latitude/elevation data to instead of generating contour"
        "\nosm.",
        dest="plotPrefix",
        action="store",
        default=None,
    )
    parser.add_argument(
        "-c",
        "--line-cat",
        help="specify a string of two comma"
        "\nseperated integers for major and medium elevation categories, e. g."
        "\n'200,100' which is the default. This is needed for fancy rendering.",
        dest="lineCats",
        metavar="ELEVATION_MAJOR,ELEVATION_MEDIUM",
        action="store",
        default="200,100",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        help="number of jobs to be run in parallel (POSIX only)",
        dest="nJobs",
        action="store",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--osm-version",
        help="pass a number as OSM-VERSION to"
        "\nuse for the output.  The default value is 0.6.  If you need an older"
        "\nversion, try 0.5.",
        metavar="OSM-VERSION",
        dest="osmVersion",
        action="store",
        default=0.6,
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
        default=False,
    )
    parser.add_argument(
        "--start-node-id",
        help="specify an integer as id of"
        "\nthe first written node in the output OSM xml.  It defaults to 10000000"
        "\nbut some OSM xml mergers are running into trouble when encountering non"
        "\nunique ids.  In this case and for the moment, it is safe to say"
        "\n10000000000 (ten billion) then.",
        dest="startId",
        type=int,
        default=10000000,
        action="store",
        metavar="NODE-ID",
    )
    parser.add_argument(
        "--start-way-id",
        help="specify an integer as id of"
        "\nthe first written way in the output OSM xml.  It defaults to 10000000"
        "\nbut some OSM xml mergers are running into trouble when encountering non"
        "\nunique ids.  In this case and for the moment, it is safe to say"
        "\n10000000000 (ten billion) then.",
        dest="startWayId",
        type=int,
        default=10000000,
        action="store",
        metavar="WAY-ID",
    )
    parser.add_argument(
        "--max-nodes-per-tile",
        help="specify an integer as a maximum"
        "\nnumber of nodes per generated tile.  It defaults to 1000000,"
        "\nwhich is approximately the maximum number of nodes handled properly"
        "\nby mkgmap.  For bigger tiles, try higher values. For a single file"
        "\noutput, say 0 here (this disables any parallelization).",
        dest="maxNodesPerTile",
        type=int,
        default=1000000,
        action="store",
    )
    parser.add_argument(
        "--max-nodes-per-way",
        help="specify an integer as a maximum"
        "\nnumber of nodes per way.  It defaults to 2000, which is the maximum value"
        "\nfor OSM api version 0.6.  Say 0 here, if you want unsplitted ways.",
        dest="maxNodesPerWay",
        type=int,
        default=2000,
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
        "\nor two thirds. The default is 0.0 value to remove dupe points and optimize"
        "\nstraight lines.",
        dest="rdpEpsilon",
        type=float,
        default=0.0,
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
        default=1.0,
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
        default=0,
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
        default=False,
        dest="pbf",
    )
    group.add_argument(
        "--o5m",
        help="write o5m binary files instead of OSM"
        "\nXML.  This reduces the needed disk space. Be sure the programs you"
        "\nwant to use the output files with are capable of o5m parsing.  The"
        "\noutput files will have the .o5m extension.",
        action="store_true",
        default=False,
        dest="o5m",
    )

    parser.add_argument(
        "--srtm",
        help="use SRTM resolution of SRTM-RESOLUTION"
        "\narc seconds.  Possible values are 1 and 3, the default value is 3. "
        "\nFor different SRTM data versions and map coverage, see the --srtm-version"
        "\noption.",
        metavar="SRTM-RESOLUTION",
        dest="srtmResolution",
        action="store",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--srtm-version",
        help="use this VERSION of SRTM data."
        "\nSupported SRTM versions are 2.1 and 3.  Version 2.1 has voids which"
        "\nwere filled in version 3 using ASTER GDEM and other data.  In version"
        "\n2.1, only the US territory is included in the 1 arc second dataset.  In"
        "\nversion 3, nearly the whole world is covered.  The default for this"
        "\noption is 3.  If you want the old version, say --srtm-version=2.1 here",
        dest="srtmVersion",
        action="store",
        metavar="VERSION",
        default=3.0,
        type=float,
    )
    parser.add_argument(
        "--earthexplorer-user",
        help="the username to use for"
        "\nearthexplorer login.  This is needed if you want to use NASA SRTM sources"
        "\nin version 3.0.  If you do not yet have an earthexplorer login, visit"
        "\nhttps://ers.cr.usgs.gov/register/ and create one.  Once specified,"
        "\npyhgtmap will store the earthexplorer login credentials unencrypted in a"
        "\nfile called '.pyhgtmaprc' in your home directory.  I. e., you only"
        "\nhave to specify this option (and the --earthexplorer-password option) once. "
        "\nIn addition, the password specified on the command line may be read"
        "\nby every user on your system.  So, don't choose a password which you"
        "\ndon't want to be disclosed to others.  This option should be specified"
        "\nin combination with the --earthexplorer-password option.",
        dest="earthexplorerUser",
        action="store",
        default=None,
        metavar="EARTHEXPLORER_USERNAME",
    )
    parser.add_argument(
        "--earthexplorer-password",
        help="the password to use for"
        "\nearthexplorer login.  This option should be specified in combination with"
        "\nthe --earthexplorer-user option.  For further explanation, see the help"
        "\ngiven for the --earthexplorer-user option.",
        dest="earthexplorerPassword",
        action="store",
        default=None,
        metavar="EARTHEXPLORER_PASSWORD",
    )
    parser.add_argument(
        "--viewfinder-mask",
        help="if specified, NASA SRTM data"
        "\nare masked with data from www.viewfinderpanoramas.org.  Possible values"
        "\nare 1 and 3 (for explanation, see the --srtm option).",
        metavar="VIEWFINDER-RESOLUTION",
        type=int,
        default=0,
        action="store",
        dest="viewfinder",
    )
    parser.add_argument(
        "--source",
        "--data-source",
        help="specify a list of"
        "\nsources to use as comma-separated string.  Available sources are"
        "\n'srtm1', 'srtm3', 'sonn1', 'sonn3' 'view1' and 'view3'.  If specified,"
        "\nthe data source will be selected using this option as preference list."
        "\nSpecifying --source=view3,srtm3 for example will prefer viewfinder 3"
        "\narc second data to NASA SRTM 3 arc second data.  Also see the"
        "\n--srtm-version option for different versions of SRTM data.",
        metavar="DATA-SOURCE",
        type=lambda x: x.lower().split(","),
        default=None,
        dest="dataSource",
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
        "\nThe default directory for this is ./hgt/ in the current directory.  You can"
        "\nspecify another cache directory with this option.",
        dest="hgtdir",
        action="store",
        default=None,
        metavar="DIRECTORY",
    )
    parser.add_argument(
        "--rewrite-indices",
        help="rewrite the index files and"
        "\nexit.  Try this if pyhgtmap encounters problems when trying to download"
        "\ndata files.",
        dest="rewriteIndices",
        action="store_true",
        default=False,
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

    opts: Configuration = parser.parse_args(sys_args, namespace=Configuration())

    if opts.hgtdir:  # Set custom ./hgt/ directory
        NASASRTMUtil.NASASRTMUtilConfig.CustomHgtSaveDir(opts.hgtdir)
    if opts.rewriteIndices:
        NASASRTMUtil.rewriteIndices()
        sys.exit(0)

    for supportedVersion in [2.1, 3]:
        if opts.srtmVersion == supportedVersion:
            break
    else:
        # unsupported SRTM data version
        sys.stderr.write(
            f"Unsupported SRTM data version '{opts.srtmVersion:.1f}'.  See the"
            " --srtm-version option for details.\n\n",
        )
        parser.print_help()
        sys.exit(1)
    if opts.srtmResolution not in [1, 3]:
        sys.stderr.write(
            "The --srtm option can only take '1' or '3' as values."
            "  Defaulting to 3.\n",
        )
        opts.srtmResolution = 3
    if opts.viewfinder not in [0, 1, 3]:
        sys.stderr.write(
            "The --viewfinder-mask option can only take '1' or '3' as values."
            "  Won't use viewfinder data.\n",
        )
        opts.viewfinder = 0
    if opts.dataSource:
        for s in opts.dataSource:
            if s[:5] not in ["view1", "view3", "srtm1", "srtm3", "sonn1", "sonn3"]:
                print(f"Unknown data source: {s:s}")
                sys.exit(1)
            elif s in ["srtm1", "srtm3"]:
                while s in opts.dataSource:
                    opts.dataSource[
                        opts.dataSource.index(s)
                    ] = f"{s:s}v{opts.srtmVersion:.1f}"
    elif len(opts.filenames) == 0:
        # No explicit source nor input provided, try to download using default
        opts.dataSource = []
        if opts.viewfinder != 0:
            opts.dataSource.append(f"view{opts.viewfinder:d}")
        opts.dataSource.append(f"srtm{opts.srtmResolution:d}v{opts.srtmVersion:.1f}")
    else:
        # Input files provided, no download source
        opts.dataSource = []
    needsEarthexplorerLogin = False
    for s in opts.dataSource:
        if s.startswith("srtm") and "v3" in s:
            needsEarthexplorerLogin = True
    if needsEarthexplorerLogin:
        # we need earthexplorer login credentials handling then
        earthexplorerUser = configUtil.Config().setOrGet(
            "earthexplorer_credentials",
            "user",
            opts.earthexplorerUser,
        )
        earthexplorerPassword = configUtil.Config().setOrGet(
            "earthexplorer_credentials",
            "password",
            opts.earthexplorerPassword,
        )
        if not all((earthexplorerUser, earthexplorerPassword)):
            print(
                "Need earthexplorer login credentials to continue.  See the help for the",
            )
            print(
                "--earthexplorer-user and --earthexplorer-password options for details.",
            )
            print("-" * 60)
            parser.print_help()
            sys.exit(1)
        NASASRTMUtil.NASASRTMUtilConfig.earthexplorerCredentials(
            earthexplorerUser,
            earthexplorerPassword,
        )
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
        opts.area, opts.polygon = parse_polygons_file(opts.polygon_file)
    elif opts.downloadOnly and not opts.area:
        # no area, no polygon, so nothing to download
        sys.stderr.write(
            "Nothing to download.  Combine the --download-only option with"
            "\neither one of the --area and --polygon options.\n",
        )
        sys.exit(1)
    if opts.disableRdp:
        opts.rdpEpsilon = None

    return opts, opts.filenames
