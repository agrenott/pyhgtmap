# import psyco
# psyco.full()

from __future__ import annotations

import logging
import os
import sys

from pyhgtmap import NASASRTMUtil
from pyhgtmap.cli import parse_command_line
from pyhgtmap.hgt.file import calc_hgt_area
from pyhgtmap.hgt.processor import HgtFilesProcessor
from pyhgtmap.logger import configure_logging

logger = logging.getLogger(__name__)


def main_internal(sys_args: list[str]) -> None:
    opts, args = parse_command_line(sys_args)
    configure_logging(opts.logLevel)

    hgtDataFiles: list[tuple[str, bool]]
    if args:
        # Prefer using any manually provided source file
        use_poly_flag = opts.polygon is not None
        hgtDataFiles = [
            (arg, use_poly_flag)
            for arg in args
            if os.path.splitext(arg)[1].lower() in (".hgt", ".tif", ".tiff", ".vrt")
        ]
        opts.area = ":".join(
            [
                str(i)
                for i in calc_hgt_area(hgtDataFiles, opts.srtmCorrx, opts.srtmCorry)
            ],
        )
    else:
        # Download from area or polygon
        logger.debug(f"Downloading HGT files for area {opts.area}")
        if not opts.area:
            raise ValueError("opts.area is not defined")
        if not opts.dataSource:
            raise ValueError("opts.dataSource is not defined")
        hgtDataFiles = NASASRTMUtil.getFiles(
            opts.area,
            opts.polygon,
            opts.srtmCorrx,
            opts.srtmCorry,
            opts.dataSource,
        )
        if len(hgtDataFiles) == 0:
            print(f"No files for this area {opts.area:s} from desired source(s).")
            sys.exit(0)
        elif opts.downloadOnly:
            sys.exit(0)

    HgtFilesProcessor(opts.nJobs, opts.startId, opts.startWayId, opts).process_files(
        hgtDataFiles,
    )


def main() -> None:
    """Parameter-less entry point, required for python packaging scripts"""
    # https://packaging.python.org/en/latest/specifications/entry-points/#use-for-scripts
    main_internal(sys.argv[1:])


if __name__ == "__main__":
    main()
