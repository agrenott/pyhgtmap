from typing import List, Optional, Tuple, cast

import contourpy
import numpy
import numpy.typing
from pybind11_rdp import rdp

from pyhgtmap.hgt import TransformFunType


def simplify_path(
    input_path: numpy.ndarray, rdp_epsilon: Optional[float] = None
) -> numpy.ndarray:
    """Simplifies a path using the Ramer-Douglas-Peucker (RDP) algorithm.

    <input_path>: a contour line path
    <rdp_epsilon>: the epsilon value to use in RDP

    A simplified path is returned as numpy array.
    """
    # Remove duplicated consecutive points
    deduped_path = input_path
    # While in theory this would be a good thing, this is a computing intensive step, and RDP will remove
    # most (but not all) of the useless points anyway...
    # On the whole France-PACA region, the delta is less than 0.05% when adding the dedupe to a RDP with epsion = 0.0...
    # deduped_path = input_path[numpy.any(input_path != numpy.r_[input_path[1:], [[None,None]]], axis=1)]
    if rdp_epsilon is not None:
        deduped_path = rdp(deduped_path, epsilon=rdp_epsilon)
    return deduped_path


class ContoursGenerator(object):
    def __init__(
        self,
        cntr: contourpy.ContourGenerator,
        max_nodes_per_way,
        transform: Optional[TransformFunType],
        polygon=None,
        rdp_epsilon=None,
    ) -> None:
        self.cntr: contourpy.ContourGenerator = cntr
        self.max_nodes_per_way = max_nodes_per_way
        self.polygon = polygon
        self.transform: Optional[TransformFunType] = transform
        self.rdp_epsilon = rdp_epsilon

    def _cutBeginning(self, p):
        """is recursively called to cut off a path's first element
        if it equals the second one.

        This is needed for beauty only.  Such a path makes no sense, but
        matplotlib.Cntr.cntr's trace method sometimes returns this.

        If the path gets too short, an empty list is returned.
        """
        if len(p) < 2:
            return []
        elif not numpy.all(p[0] == p[1]):
            return p
        else:
            return self._cutBeginning(p[1:])

    def splitList(self, input_list) -> Tuple[List[numpy.ndarray], int, int]:
        """splits a path to contain not more than self.maxNodesPerWay nodes.

        A list of paths containing at least 2 (or, with closed paths, 3) nodes
        is returned, along with the number of nodes and paths as written later to
        the OSM XML output.
        """
        length = self.max_nodes_per_way
        # l = self._cutBeginning(l)
        if len(input_list) < 2:
            return [], 0, 0
        if length == 0 or len(input_list) <= length:
            tmpList = [
                input_list,
            ]
        else:
            """
            if len(l)%(length-1) == 1:
                    # the last piece of a path should contain at least 2 nodes
                    l, endPiece = l[:-1], l[-2:]
            else:
                    endPiece = None
            tmpList = [l[i:i+length] for i in range(0, len(l), length-1)]
            if endPiece != None:
                    tmpList.append(endPiece)
            """
            # we don't need to do the stuff with the end piece if we stop the list
            # comprehension at the second-last element of the list (i being at maximum
            # len(l)-2.  This works because <length> is at least two, so we are sure
            # to always include the last two elements.
            tmpList = [
                input_list[i : i + length]
                for i in range(0, len(input_list) - 1, length - 1)
            ]
        pathList = []
        numOfClosedPaths = 0
        for path in tmpList:
            # path = self._cutBeginning(path)
            if len(path) == 0:
                # self._cutBeginning() returned an empty list for this path
                continue
            if numpy.all(path[0] == path[-1]):
                # a closed path with at least 3 nodes
                numOfClosedPaths += 1
            pathList.append(path)
        numOfPaths = len(pathList)
        numOfNodes = sum([len(p) for p in pathList]) - numOfClosedPaths
        return pathList, numOfNodes, numOfPaths

    # Actually returns Tuple[List[numpy.typing.ArrayLike[numpy.typing.ArrayLike[numpy.float64]]], int, int]
    # But can't be typed correctly yet...
    # https://stackoverflow.com/questions/66657117/type-hint-2d-numpy-array
    def trace(self, elevation: int) -> Tuple[List[numpy.ndarray], int, int]:
        """this emulates matplotlib.cntr.Cntr's trace method.
        The difference is that this method returns already split paths,
        along with the number of nodes and paths as expected in the OSM
        XML output.  Also, consecutive identical nodes are removed.
        """
        # Keep only the first element of the tuple, ignoring matplot line code
        rawPaths: List[numpy.ndarray] = cast(
            List[numpy.ndarray], self.cntr.create_contour(elevation)[0]
        )
        numOfPaths, numOfNodes = 0, 0
        resultPaths = []
        for path in rawPaths:
            path = simplify_path(path, self.rdp_epsilon)
            splitPaths, numOfNodesAdd, numOfPathsAdd = self.splitList(path)
            resultPaths.extend(splitPaths)
            numOfPaths += numOfPathsAdd
            numOfNodes += numOfNodesAdd
        return resultPaths, numOfNodes, numOfPaths


def build_contours(
    x: numpy.typing.ArrayLike,
    y: numpy.typing.ArrayLike,
    z: numpy.typing.ArrayLike,
    max_nodes_per_way: int,
    transform: Optional[TransformFunType],
    polygon,
    rdp_epsilon,
) -> ContoursGenerator:
    """Build countours generator object."""
    contours: ContoursGenerator = ContoursGenerator(
        contourpy.contour_generator(
            x,
            y,
            z,
            corner_mask=True,
            chunk_size=0,
            line_type=contourpy.LineType.SeparateCode,
            fill_type=contourpy.FillType.OuterCode,
        ),
        max_nodes_per_way,
        transform,
        polygon,
        rdp_epsilon,
    )
    return contours
