import logging
import multiprocessing
from multiprocessing.context import ForkProcess
from multiprocessing.sharedctypes import Synchronized
from typing import Callable, List, Tuple, cast

from pyhgtmap.hgt.file import hgtFile
from pyhgtmap.hgt.tile import hgtTile
from pyhgtmap.output.factory import get_osm_output

logger = logging.getLogger(__name__)


class HgtFilesProcessor:
    """
    Generate contour files from HGT (or Geotiff) files.
    One file per tile (part of input file) is generated, ensuring there's no duplicate node nor way ID
    in the output files.
    Process can be parallelized per tile to benefit from multiple cores CPU.
    """

    def __init__(self, nb_jobs: int, node_start_id: int, way_start_id: int) -> None:
        """Initialiaze files processor.

        Args:
            nb_jobs (int): Max number of processes allowed (>1 to enable parallelization)
            node_start_id (int): ID of the first generated node
            way_start_id (int): ID of the first generated way
        """
        self.next_node_id: Synchronized = cast(
            Synchronized, multiprocessing.Value("i", node_start_id)
        )
        self.next_way_id: Synchronized = cast(
            Synchronized, multiprocessing.Value("i", way_start_id)
        )
        self.available_children = multiprocessing.Semaphore(nb_jobs)
        self.parallel: bool = nb_jobs > 1
        # Not joined yet children
        self.active_children: List[ForkProcess] = []
        # Errors raised by previously joined children
        self.children_errors: List[Tuple[int, int]] = []

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

    def process_tile_internal(self, file_name: str, tile: hgtTile, options) -> None:
        """Process a single output tile."""
        logger.debug("process_tile %s", tile)
        try:
            # Compute contours
            tile_contours = tile.get_contours(
                step_cont=int(options.contourStepSize),
                max_nodes_per_way=options.maxNodesPerWay,
                no_zero=options.noZero,
                rdp_epsilon=options.rdpEpsilon,
            )

            # Update counters shared among parallel processes
            # This is the actual critical section, to avoid duplicated node IDs
            logger.debug("Pending next_node_id_lock")
            tile_node_start_id: int = self.get_and_inc_counter(
                self.next_node_id, tile_contours.nb_nodes
            )
            tile_way_start_id: int = self.get_and_inc_counter(
                self.next_way_id, tile_contours.nb_ways
            )

            # Writing nodes to output is the most time & resources consuming part
            osm_output = get_osm_output(
                options,
                [
                    file_name,
                ],
                tile.bbox(),
            )
            logger.debug("writeNodes")
            new_start_id, ways = osm_output.writeNodes(
                tile_contours,
                osm_output.timestampString,
                tile_node_start_id,
                options.osmVersion,
            )
            logger.debug("writeWays")
            osm_output.writeWays(ways, tile_way_start_id)
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
            logger.warn("Discarding invalid tile %s", tile)

    def run_in_child(self, func: Callable, *args) -> None:
        """
        Basic wrapper function ensuring the available_children semaphore is properly released.
        """
        try:
            func(*args)
        except Exception as e:
            logger.error("Exception caught in child process: %s", e)
            raise e
        finally:
            self.available_children.release()

    def process_tile(self, file_name: str, tile: hgtTile, options) -> None:
        """Process given tile, in a dedicated process if parallelization is enabled.

        Args:
            file_name (str): original file name (used for output file name generation)
            tile (hgt.hgtTile): tile to process
            options (_type_): processing options
        """
        if self.parallel:
            # Fork into a child process when available
            self.available_children.acquire()
            # Ensure "fork" method is used to share parent's process context
            ctx = multiprocessing.get_context("fork")
            p = ctx.Process(
                target=self.run_in_child,
                args=(self.process_tile_internal, file_name, tile, options),
            )
            self.active_children.append(p)
            p.start()
            # Try to progressively clean some done children
            self.join_children(skip_active=True)
        else:
            # Process tile in current process
            self.process_tile_internal(file_name, tile, options)

    def process_file(self, file_name: str, check_poly: bool, options) -> None:
        """Process given file, parallelizing tiles processing if enabled.

        Args:
            file_name (str): original file name
            check_poly (bool): whether polygons must be checked
            options (_type_): processing options
        """
        logger.debug("process_file %s", file_name)
        hgt_file = hgtFile(
            file_name,
            options.srtmCorrx,
            options.srtmCorry,
            options.polygon,
            check_poly,
            options.voidMax,
            options.contourFeet,
            options.smooth_ratio,
        )
        hgt_tiles = hgt_file.makeTiles(options)
        logger.debug("Tiles built; nb tiles: %d", len(hgt_tiles))
        for tile in hgt_tiles:
            logger.debug("  %s", tile.get_stats())

        for tile in hgt_tiles:
            self.process_tile(file_name, tile, options)

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

    def process_files(self, files: List[Tuple[str, bool]], options) -> None:
        for file_name, check_poly in files:
            self.process_file(file_name, check_poly, options)
        logger.debug("Done scheduling, waiting for all children to complete...")

        self.join_children()
        if self.children_errors:
            logger.error(
                "Some child process(es) finished with error; check earlier logs for exception details.%s",
                "\n - ".join(
                    f"pid: {p[0]}; exitcode: {p[1]}" for p in self.children_errors
                ),
            )
