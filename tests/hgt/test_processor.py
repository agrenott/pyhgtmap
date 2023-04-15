import glob
import itertools
import multiprocessing
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Callable, Generator, List, NamedTuple, Tuple

import osmium
import osmium.io
import osmium.osm
import pytest

from pyhgtmap.hgt.processor import HgtFilesProcessor

from .. import TEST_DATA_PATH


class OSMDecoder(osmium.SimpleHandler):
    """Basic OSM file decoder, relying on official osmium library."""

    def __init__(self) -> None:
        super().__init__()
        self.min_node_id: int = sys.maxsize
        self.max_node_id: int = 0
        self.min_way_id: int = sys.maxsize
        self.max_way_id: int = 0

    def node(self, n: osmium.osm.Node) -> None:
        if n.id < self.min_node_id:
            self.min_node_id = n.id
        elif n.id > self.max_node_id:
            self.max_node_id = n.id

    def way(self, w: osmium.osm.Way) -> None:
        if w.id < self.min_way_id:
            self.min_way_id = w.id
        elif w.id > self.max_way_id:
            self.max_way_id = w.id


IdBoundaries = NamedTuple(
    "IdBoundaries",
    [
        ("min_node_id", int),
        ("max_node_id", int),
        ("min_way_id", int),
        ("max_way_id", int),
    ],
)


def run_in_spawned_process(function: Callable, *args, **kwargs) -> None:
    """Spawn a child process to execute the given function, and propagate exception from child if any."""
    # "spawn" is key to isolate child process, instead of default "fork" on linux
    ctx = multiprocessing.get_context("spawn")
    # Queue must be created from the same context as Process, otherwise segfault happens...
    exception_queue = ctx.SimpleQueue()
    p = ctx.Process(
        target=run_in_process_child, args=[function, exception_queue, *args]
    )
    p.start()
    p.join()
    child_exception = exception_queue.get()
    if child_exception is not None:
        raise child_exception
    assert p.exitcode == 0


def run_in_process_child(
    function: Callable, exception_queue: multiprocessing.SimpleQueue, *args
) -> None:
    """Catch and propagate exception to parent process if any."""
    try:
        function(*args)
        exception_queue.put(None)
    except Exception as e:
        # Propagate exception to parent
        exception_queue.put(e)
        raise


@contextmanager
def cwd(path) -> Generator[None, None, None]:
    """chdir to given path and revert to original one."""
    oldpwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldpwd)


class TestHgtFilesProcessor:
    @staticmethod
    @pytest.mark.parametrize(
        "nb_jobs",
        [
            1,  # Single process mode
            8,  # Multi-processes mode
        ],
    )
    def test_process_files(nb_jobs: int) -> None:
        """E2E test."""
        # Run in spawned child process, as osmium threads doesn't suuport being used
        # once in main process and then in forked process (causing deadlock situation).
        # Spanwing test case ensures child process doesn't share osmium context with previous
        # runs.
        run_in_spawned_process(TestHgtFilesProcessor._test_process_files, nb_jobs)

    @staticmethod
    def _test_process_files(nb_jobs: int) -> None:
        # Test with default command line options
        custom_options = SimpleNamespace(
            area=None,
            maxNodesPerTile=500000,
            maxNodesPerWay=2000,
            contourStepSize=20,
            srtmCorrx=0,
            srtmCorry=0,
            polygon=None,
            voidMax=-0x8000,
            contourFeet=False,
            smooth_ratio=1,
            noZero=False,
            rdpEpsilon=0.00001,
            outputPrefix=None,
            dataSource=None,
            gzip=0,
            pbf=True,
            lineCats="200,100",
            osmVersion=0.6,
        )
        processor = HgtFilesProcessor(nb_jobs, node_start_id=100, way_start_id=200)
        with tempfile.TemporaryDirectory() as tempdir_name:
            with cwd(tempdir_name):
                files_list: List[Tuple[str, bool]] = [
                    (os.path.join(TEST_DATA_PATH, "N43E006.hgt"), False)
                ]
                processor.process_files(files_list, custom_options)
                out_files_names: list[str] = sorted(glob.glob("*.osm.pbf"))
                # We may have more files generated (eg. .coverage ones)
                assert out_files_names == [
                    "lon6.00_7.00lat43.00_43.50_local-source.osm.pbf",
                    "lon6.00_7.00lat43.50_43.75_local-source.osm.pbf",
                    "lon6.00_7.00lat43.75_43.88_local-source.osm.pbf",
                    "lon6.00_7.00lat43.88_44.00_local-source.osm.pbf",
                ], f"out_files_names mismatch; {out_files_names}"
                if nb_jobs == 1:
                    # No child process used if jobs == 1
                    assert len(processor.children) == 0
                else:
                    # As many children as output tiles (painful to check for actual max concurrency)
                    assert len(processor.children) == len(out_files_names)

                # Ensure nodes and ways IDs do not overlap between generated files
                # (they should actually be continuous, but we really only care about overlapping)
                ids_boundaries: List[IdBoundaries] = []
                for out_file_name in out_files_names:
                    osm_decoder = OSMDecoder()

                    osm_decoder.apply_file(out_file_name)
                    ids_boundaries.append(
                        IdBoundaries(
                            osm_decoder.min_node_id,
                            osm_decoder.max_node_id,
                            osm_decoder.min_way_id,
                            osm_decoder.max_way_id,
                        )
                    )

                result = sorted(ids_boundaries)
                for boundaries_1, boundaries_2 in itertools.combinations(result, 2):
                    # Manually instrument asserts, as pytest assert rewriting doesn't work in spawned process
                    assert min(
                        boundaries_1.max_node_id, boundaries_2.max_node_id
                    ) < max(
                        boundaries_1.min_node_id, boundaries_2.min_node_id
                    ), f"Overlap of nodes boundaries {boundaries_1} and {boundaries_2}"
                    assert min(boundaries_1.max_way_id, boundaries_2.max_way_id) < max(
                        boundaries_1.min_way_id, boundaries_2.min_way_id
                    ), f"Overlap of ways boundaries {boundaries_1} and {boundaries_2}"

            # Move coverage files of child process back to root
            for coverage_file in glob.glob(os.path.join(tempdir_name, ".coverage.*")):
                shutil.move(coverage_file, ".")
