from __future__ import annotations

import glob
import itertools
import logging
import multiprocessing
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Callable, Generator, NamedTuple
from unittest import mock
from unittest.mock import MagicMock, Mock

import npyosmium
import npyosmium.io
import npyosmium.osm
import pytest

from pyhgtmap.hgt.processor import HgtFilesProcessor
from pyhgtmap.hgt.tile import TileContours
from tests import TEST_DATA_PATH


class OSMDecoder(npyosmium.SimpleHandler):
    """Basic OSM file decoder, relying on official osmium library."""

    def __init__(self) -> None:
        super().__init__()
        self.min_node_id: int = sys.maxsize
        self.max_node_id: int = 0
        self.min_way_id: int = sys.maxsize
        self.max_way_id: int = 0

    def node(self, n: npyosmium.osm.Node) -> None:
        if n.id < self.min_node_id:
            self.min_node_id = n.id
        elif n.id > self.max_node_id:
            self.max_node_id = n.id

    def way(self, w: npyosmium.osm.Way) -> None:
        if w.id < self.min_way_id:
            self.min_way_id = w.id
        elif w.id > self.max_way_id:
            self.max_way_id = w.id


class IdBoundaries(NamedTuple):
    min_node_id: int
    max_node_id: int
    min_way_id: int
    max_way_id: int


def run_in_spawned_process(function: Callable, *args, **kwargs) -> None:
    """Spawn a child process to execute the given function, and propagate exception from child if any."""
    # "spawn" is key to isolate child process, instead of default "fork" on linux
    ctx = multiprocessing.get_context("spawn")
    # Queue must be created from the same context as Process, otherwise segfault happens...
    exception_queue = ctx.SimpleQueue()
    p = ctx.Process(
        target=run_in_process_child,
        args=[function, exception_queue, *args],
    )
    p.start()
    p.join()
    child_exception = exception_queue.get()
    if child_exception is not None:
        raise child_exception
    assert p.exitcode == 0


def run_in_process_child(
    function: Callable,
    exception_queue: multiprocessing.SimpleQueue,
    *args,
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


def check_no_id_overlap(osm_files_names: list[str]) -> None:
    ids_boundaries: list[IdBoundaries] = []
    for out_file_name in osm_files_names:
        osm_decoder = OSMDecoder()

        osm_decoder.apply_file(out_file_name)
        ids_boundaries.append(
            IdBoundaries(
                osm_decoder.min_node_id,
                osm_decoder.max_node_id,
                osm_decoder.min_way_id,
                osm_decoder.max_way_id,
            ),
        )

    result = sorted(ids_boundaries)
    for boundaries_1, boundaries_2 in itertools.combinations(result, 2):
        # Manually instrument asserts, as pytest assert rewriting doesn't work in spawned process
        assert min(boundaries_1.max_node_id, boundaries_2.max_node_id) < max(
            boundaries_1.min_node_id,
            boundaries_2.min_node_id,
        ), f"Overlap of nodes boundaries {boundaries_1} and {boundaries_2}"
        assert min(boundaries_1.max_way_id, boundaries_2.max_way_id) < max(
            boundaries_1.min_way_id,
            boundaries_2.min_way_id,
        ), f"Overlap of ways boundaries {boundaries_1} and {boundaries_2}"


@pytest.fixture()
def default_options() -> SimpleNamespace:
    """Default command line options."""
    return SimpleNamespace(
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


class TestHgtFilesProcessor:
    @staticmethod
    @pytest.mark.parametrize(
        "nb_jobs",
        [
            1,  # Single process mode
            8,  # Multi-processes mode
        ],
    )
    def test_process_files(nb_jobs: int, default_options: SimpleNamespace) -> None:
        """E2E test."""
        # Run in spawned child process, as osmium threads doesn't suuport being used
        # once in main process and then in forked process (causing deadlock situation).
        # Spanwing test case ensures child process doesn't share osmium context with previous
        # runs.
        run_in_spawned_process(
            TestHgtFilesProcessor._test_process_files,
            nb_jobs,
            default_options,
        )

    @staticmethod
    def _test_process_files(nb_jobs: int, options) -> None:
        # Test with default command line options
        processor = HgtFilesProcessor(
            nb_jobs,
            node_start_id=100,
            way_start_id=200,
            options=options,
        )
        with tempfile.TemporaryDirectory() as tempdir_name:
            with cwd(tempdir_name):
                files_list: list[tuple[str, bool]] = [
                    (os.path.join(TEST_DATA_PATH, "N43E006.hgt"), False),
                ]
                # Instrument method without changing its behavior
                processor.process_tile_internal = Mock(  # type: ignore[method-assign]
                    side_effect=processor.process_tile_internal,
                )
                processor.process_files(files_list)
                out_files_names: list[str] = sorted(glob.glob("*.osm.pbf"))
                # We may have more files generated (eg. .coverage ones)
                assert out_files_names == [
                    "lon6.00_7.00lat43.00_43.50_local-source.osm.pbf",
                    "lon6.00_7.00lat43.50_43.75_local-source.osm.pbf",
                    "lon6.00_7.00lat43.75_43.88_local-source.osm.pbf",
                    "lon6.00_7.00lat43.88_44.00_local-source.osm.pbf",
                ], f"out_files_names mismatch; {out_files_names}"
                if nb_jobs == 1:
                    # process_tile_internal called in main process when parallelization is not used
                    assert processor.process_tile_internal.call_count == len(
                        out_files_names,
                    )
                else:
                    # process_tile_internal is NOT called in parent process, but in children
                    # (not reflected in parent's mock). Can' check for actual max concurrency.
                    processor.process_tile_internal.assert_not_called()

                # Ensure nodes and ways IDs do not overlap between generated files
                # (they should actually be continuous, but we really only care about overlapping)
                check_no_id_overlap(out_files_names)

            # Move coverage files of child process back to root
            for coverage_file in glob.glob(os.path.join(tempdir_name, ".coverage.*")):
                shutil.move(coverage_file, ".")

    @staticmethod
    @pytest.mark.parametrize(
        "nb_jobs",
        [
            1,  # Single process mode
            8,  # Multi-processes mode
        ],
    )
    def test_process_files_single_output(
        nb_jobs: int,
        default_options: SimpleNamespace,
    ) -> None:
        """E2E test."""
        # Run in spawned child process, as osmium threads doesn't suuport being used
        # once in main process and then in forked process (causing deadlock situation).
        # Spanwing test case ensures child process doesn't share osmium context with previous
        # runs.

        # Enable single output mode
        default_options.maxNodesPerTile = 0
        run_in_spawned_process(
            TestHgtFilesProcessor._test_process_files_single_output,
            nb_jobs,
            default_options,
        )

    @staticmethod
    def _test_process_files_single_output(nb_jobs: int, options) -> None:
        # Test with default command line options
        processor = HgtFilesProcessor(
            nb_jobs,
            node_start_id=100,
            way_start_id=200,
            options=options,
        )
        with tempfile.TemporaryDirectory() as tempdir_name:
            with cwd(tempdir_name):
                # Use 2 files as input, to validate merging into a common output
                files_list: list[tuple[str, bool]] = [
                    (os.path.join(TEST_DATA_PATH, "N43E006.hgt"), False),
                    (os.path.join(TEST_DATA_PATH, "N43E007.hgt"), False),
                ]
                # This is usually done by main() (could be improved)
                options.area = "6:43:8:44"
                # Increase step size to speed up test case
                options.contourStepSize = 500
                # Instrument method without changing its behavior
                processor.process_tile_internal = Mock(  # type: ignore[method-assign]
                    side_effect=processor.process_tile_internal,
                )
                processor.process_files(files_list)
                out_files_names: list[str] = sorted(glob.glob("*.osm.pbf"))
                # We may have more files generated (eg. .coverage ones)
                assert out_files_names == [
                    "lon6.00_8.00lat43.00_44.00_local-source.osm.pbf",
                ], f"out_files_names mismatch; {out_files_names}"

                # process_tile_internal called in main process when parallelization is not used
                # (and no per-tile parallelization is used in single output mode)
                assert processor.process_tile_internal.call_count == len(files_list)

                # Ensure nodes and ways IDs do not overlap between generated files
                # (they should actually be continuous, but we really only care about overlapping)
                check_no_id_overlap(out_files_names)

            # Move coverage files of child process back to root
            for coverage_file in glob.glob(os.path.join(tempdir_name, ".coverage.*")):
                shutil.move(coverage_file, ".")

    @staticmethod
    def test_get_osm_output(default_options: SimpleNamespace) -> None:
        processor = HgtFilesProcessor(
            1,
            node_start_id=100,
            way_start_id=200,
            options=default_options,
        )
        with mock.patch("pyhgtmap.hgt.processor.get_osm_output") as get_osm_output_mock:
            # Return a different Mock on each call
            get_osm_output_mock.side_effect = lambda *args: Mock()
            output1 = processor.get_osm_output(["file1.hgt"], (0, 1, 2, 3))
            output2 = processor.get_osm_output(["file2.hgt"], (4, 5, 6, 7))

            # 2 different outputs must be allocated
            assert get_osm_output_mock.call_count == 2
            get_osm_output_mock.assert_has_calls(
                [
                    mock.call(default_options, ["file1.hgt"], (0, 1, 2, 3)),
                    mock.call(default_options, ["file2.hgt"], (4, 5, 6, 7)),
                ],
            )
            assert output1 is not output2

    @staticmethod
    def test_get_osm_output_single_output(default_options: SimpleNamespace) -> None:
        # Enable single output mode
        default_options.maxNodesPerTile = 0
        processor = HgtFilesProcessor(
            1,
            node_start_id=100,
            way_start_id=200,
            options=default_options,
        )
        with mock.patch("pyhgtmap.hgt.processor.get_osm_output") as get_osm_output_mock:
            # Return a different Mock on each call
            get_osm_output_mock.side_effect = lambda *args: Mock()
            output1 = processor.get_osm_output(["file1.hgt"], (0, 1, 2, 3))
            output2 = processor.get_osm_output(["file2.hgt"], (4, 5, 6, 7))

            # One single output must be allocated, and return on consecutive calls
            assert get_osm_output_mock.call_count == 1
            get_osm_output_mock.assert_called_once_with(
                default_options,
                ["file1.hgt"],
                (0, 1, 2, 3),
            )
            assert output1 is output2

    @staticmethod
    def test_node_id_overflow(default_options: SimpleNamespace) -> None:
        # Ensure node ID doesn't overflow limit of int32
        processor = HgtFilesProcessor(
            1,
            node_start_id=2147483647,
            way_start_id=200,
            options=default_options,
        )
        assert processor.get_and_inc_counter(processor.next_node_id, 1) == 2147483647
        assert processor.get_and_inc_counter(processor.next_node_id, 1) == 2147483648

    @staticmethod
    def test_way_id_overflow(default_options: SimpleNamespace) -> None:
        # Ensure way ID doesn't overflow limit of int32
        processor = HgtFilesProcessor(
            1,
            node_start_id=100,
            way_start_id=2147483647,
            options=default_options,
        )
        assert processor.get_and_inc_counter(processor.next_way_id, 1) == 2147483647
        assert processor.get_and_inc_counter(processor.next_way_id, 1) == 2147483648

    @staticmethod
    def test_process_tile_internal_empty_contour(
        default_options: SimpleNamespace,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Ensure no empty output file is generated when there's no contour."""
        processor = HgtFilesProcessor(
            1,
            node_start_id=100,
            way_start_id=200,
            options=default_options,
        )
        # Empty tile
        tile_contours = TileContours(nb_nodes=0, nb_ways=0, contours={})
        tile_mock = MagicMock()
        tile_mock.get_contours.return_value = tile_contours
        tile_mock.__str__.return_value = "Tile (28.00, 42.50, 29.00, 43.00)"  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory() as tempdir_name, cwd(tempdir_name):
            caplog.set_level(logging.INFO, logger="pyhgtmap.hgt.processor")
            processor.process_tile_internal("empty.pbf", tile_mock)
            # NO file must be generated
            assert not os.path.exists("empty.pbf")
            assert (
                "Tile (28.00, 42.50, 29.00, 43.00) doesn't contain any node, skipping."
                in caplog.text
            )
