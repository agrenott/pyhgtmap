from __future__ import annotations

import logging
import multiprocessing
from multiprocessing.sharedctypes import Synchronized
from typing import TYPE_CHECKING, Callable, cast

from pyhgtmap import BBox
from pyhgtmap.hgt.file import HgtFile
from pyhgtmap.output.factory import get_osm_output

if TYPE_CHECKING:
    from multiprocessing.context import ForkProcess

    from pyhgtmap.configuration import Configuration
    from pyhgtmap.hgt.tile import HgtTile
    from pyhgtmap.output import Output

logger = logging.getLogger(__name__)


class HgtFilesProcessor:
    """
    Generate contour files from HGT (or Geotiff) files.
    One file per tile (part of input file) is generated, ensuring there's no duplicate node nor way ID
    in the output files.
    Process can be parallelized per tile to benefit from multiple cores CPU.
    """

    def __init__(
        self,
        nb_jobs: int,
        node_start_id: int,
        way_start_id: int,
        options: Configuration,
    ) -> None:
        """Initialize files processor.

        Args:
            nb_jobs (int): Max number of processes allowed (>1 to enable parallelization)
            node_start_id (int): ID of the first generated node
            way_start_id (int): ID of the first generated way
            options (Configuration): general options
        """
        self.next_node_id: Synchronized = cast(
            Synchronized,
            multiprocessing.Value("L", node_start_id),
        )
        self.next_way_id: Synchronized = cast(
            Synchronized,
            multiprocessing.Value("L", way_start_id),
        )
        self.available_children = multiprocessing.Semaphore(nb_jobs)
        self.parallel: bool = nb_jobs > 1
        # Not joined yet children
        self.active_children: list[ForkProcess] = []
        # Errors raised by previously joined children
        self.children_errors: list[tuple[int, int]] = []
        self.options: Configuration = options
        # Common output file used in single output mode
        self.common_osm_output: Output | None = None

    @property
    def single_output(self) -> bool:
        """Return true if single output file mode should be used"""
        return self.options.maxNodesPerTile == 0

    def get_osm_output(
        self,
        hgt_files_names: list[str],
        bounding_box: BBox,
    ) -> Output:
        """Allocate or return already existing OSM output (for consecutive calls in single output mode)

        Args:
            hgt_files_names (List[str]): List of HGT input files names
            bounding_box (BoudingBox): Output bounding box

        Returns:
            Output: OSM Output wrapper
        """
        if self.common_osm_output is None:
            # No common output: either this is the first call in single output mode,
            # or we're in multiple outputs; in any case, allocate a new one
            osm_output = get_osm_output(
                self.options,
                hgt_files_names,
                bounding_box,
            )
            if self.single_output:
                # Keep reference for future calls
                self.common_osm_output = osm_output
        else:
            osm_output = self.common_osm_output

        return osm_output

    @staticmethod
    def get_and_inc_counter(counter: Synchronized, inc_value: int) -> int:
        """Atomically (via lock) read and increment counter synchronized between different processes.

        Args:
            counter (Synchronized): multiprocessing Synchronized int counter to increment
            inc_value (int): increment size to add to the counter

        Returns:
            int: original value of the counter
        """
        with counter.get_lock():
            previous_value = counter.value
            counter.value += inc_value
        return previous_value

    def process_tile_internal(self, file_name: str, tile: HgtTile) -> None:
        """Process a single output tile."""
        logger.debug("process_tile %s", tile)
        try:
            # Compute contours
            tile_contours = tile.get_contours(
                step_cont=int(self.options.contourStepSize),
                max_nodes_per_way=self.options.maxNodesPerWay,
                no_zero=self.options.noZero,
                rdp_epsilon=self.options.rdpEpsilon,
            )

            if not tile_contours.nb_nodes:
                logger.info("%s doesn't contain any node, skipping.", tile)
                return

            # Update counters shared among parallel processes
            # This is the actual critical section, to avoid duplicated node IDs
            logger.debug("Pending next_node_id_lock")
            tile_node_start_id: int = self.get_and_inc_counter(
                self.next_node_id,
                tile_contours.nb_nodes,
            )
            tile_way_start_id: int = self.get_and_inc_counter(
                self.next_way_id,
                tile_contours.nb_ways,
            )

            # Writing nodes to output is the most time & resources consuming part
            osm_output = self.get_osm_output(
                [
                    file_name,
                ],
                tile.bbox(),
            )
            logger.debug("writeNodes")
            new_start_id, ways = osm_output.write_nodes(
                tile_contours,
                osm_output.timestampString,
                tile_node_start_id,
                self.options.osmVersion,
            )
            logger.debug("writeWays")
            osm_output.write_ways(ways, tile_way_start_id)
            if not self.single_output:
                # In single output mode, file will be finalized at the very end
                logger.debug("done")
                osm_output.done()

            if new_start_id != tile_node_start_id + tile_contours.nb_nodes:
                logger.warning(
                    "new_start_id mismatch! new_start_id: %d - tile_node_start_id: %d",
                    new_start_id,
                    tile_node_start_id + tile_contours.nb_nodes,
                )
            if len(ways) != tile_contours.nb_ways:
                logger.warning(
                    "tile_way_start_id mismatch! len(ways): %d - tile_way_start_id: %d",
                    len(ways),
                    tile_way_start_id,
                )
        except ValueError:  # tiles with the same value on every element
            logger.warning("Discarding invalid tile %s", tile)

    def run_in_child(self, func: Callable, *args, **kwargs) -> None:
        """
        Basic wrapper function ensuring the available_children semaphore is properly released,
        *once func is DONE* (and not only scheduled).
        """
        try:
            logger.debug("run_in_child %s", func)
            # Clear list of children PIDs we might have inherited from parent process
            # when using fork strategy
            self.active_children.clear()
            func(*args, **kwargs)
        except Exception as e:
            logger.error("Exception caught in child process: %s", e)
            raise e
        finally:
            self.available_children.release()
            logger.debug("done - run_in_child %s", func)

    def try_parallelizing(self, func: Callable, *args, **kwargs) -> None:
        """
        Try to parallelize func over multiple processes if enabled, else execute in current process.
        """
        if self.parallel and not self.single_output:
            # Fork into a child process when available
            logger.debug("Trying to get semaphore to run %s", func)
            if self.available_children.acquire(block=False):
                # Ensure "fork" method is used to share parent's process context
                ctx = multiprocessing.get_context("fork")
                p = ctx.Process(
                    target=self.run_in_child,
                    args=(func, *args),
                    kwargs=kwargs,
                )
                self.active_children.append(p)
                p.start()
                # Try to progressively clean some done children
                self.join_children(skip_active=True)
            else:
                # Execute in current process
                logger.debug("No process available to fork, continuing in current one")
                func(*args, **kwargs)
        else:
            # Execute in current process
            func(*args, **kwargs)

    def process_file(self, file_name: str, check_poly: bool) -> None:
        """Process given file, parallelizing tiles processing if enabled.

        Args:
            file_name (str): original file name
            check_poly (bool): whether polygons must be checked
            options (_type_): processing options
        """
        logger.debug("process_file %s", file_name)
        hgt_file = HgtFile(
            file_name,
            self.options.srtmCorrx,
            self.options.srtmCorry,
            self.options.polygon,
            check_poly,
            self.options.voidMax,
            self.options.contourFeet,
            self.options.smooth_ratio,
        )
        hgt_tiles = hgt_file.make_tiles(self.options)
        logger.debug("Tiles built; nb tiles: %d", len(hgt_tiles))
        for tile in hgt_tiles:
            logger.debug("  %s", tile.get_stats())

        for tile in hgt_tiles:
            self.try_parallelizing(self.process_tile_internal, file_name, tile)
        logger.debug("Done with process_file %s", file_name)

    def join_children(self, skip_active=False) -> None:
        """
        Join all/finished children.
        Call regularly to avoid open file (pipes) exhaustion when spawning
        many processes for big datasets.
        """
        for p in self.active_children:
            if skip_active and p.is_alive():
                continue
            # Wait for child to finish and check return code
            p.join()
            logger.debug("Joined child process %d", p.pid)
            if p.exitcode and p.pid:
                self.children_errors.append((p.pid, p.exitcode))
            self.active_children.remove(p)

    def process_files(self, files: list[tuple[str, bool]]) -> None:
        """Main entry point of this class, processing a bunch of HGT files.

        Args:
            files (List[Tuple[str, bool]]): List of [source file name, check poly toggle]
        """
        if self.single_output:
            # Initialize common OSM output
            if not self.options.area:
                raise ValueError("self.options.area is not defined")
            self.get_osm_output(
                [file_tuple[0] for file_tuple in files],
                cast(
                    BBox,
                    [float(b) for b in self.options.area.split(":")],
                ),
            )

        # import objgraph
        # import tracemalloc
        # import random

        # tracemalloc.start(10)
        for file_name, check_poly in files:
            self.try_parallelizing(self.process_file, file_name, check_poly)
            # snapshot = tracemalloc.take_snapshot()
            # top_stats = snapshot.statistics("traceback")
            # # logger.debug("[memory top 10]\n  "+"\n  ".join([str(s) for s in top_stats[:10]]))
            # logger.debug("===== Memory usage =====")
            # for stat in top_stats[:10]:
            #     logger.debug(
            #         "%s memory blocks: %.1f KiB" % (stat.count, stat.size / 1024)
            #     )
            #     logger.debug("\n ".join(stat.traceback.format()))

            # logger.debug("nb files: %s; nb tiles: %s", objgraph.count("hgtFile"), objgraph.count("hgtTile"))
            # tiles = objgraph.by_type("hgtTile")
            # objgraph.show_backrefs(tiles, filename="tiles_refs.png")
            # objgraph.show_most_common_types()
            # objgraph.show_growth(limit=3)
            # try:
            #     objgraph.show_chain(
            #         objgraph.find_backref_chain(
            #             random.choice(objgraph.by_type("WayType")),
            #             objgraph.is_proper_module,
            #         ),
            #         filename="chain.png",
            #     )
            # except Exception:
            #     pass
            # roots = objgraph.get_leaking_objects()
            # logger.debug("Leaking objects: %s", objgraph.show_most_common_types(objects=roots))
            # objgraph.show_refs(roots[:3], refcounts=True, filename='roots.png')
            # # objgraph.show_refs([y], filename='sample-graph.png')
        logger.debug("Done scheduling, waiting for all children to complete...")

        self.join_children()
        if self.children_errors:
            logger.error(
                "Some child process(es) finished with error; check earlier logs for exception details.%s",
                "\n - ".join(
                    f"pid: {p[0]}; exitcode: {p[1]}" for p in self.children_errors
                ),
            )

        if self.single_output and self.common_osm_output is not None:
            # Finalize output file
            logger.debug("Finalizing output file")
            self.common_osm_output.done()
            self.common_osm_output = None
