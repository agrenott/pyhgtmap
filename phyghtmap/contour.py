from typing import Callable, List, Tuple

import contourpy
import numpy
import numpy.typing


class ContourObject(object):
    def __init__(
        self,
        Cntr: contourpy.ContourGenerator,
        maxNodesPerWay,
        transform,
        polygon=None,
        rdpEpsilon=None,
        rdpMaxVertexDistance=None,
    ):
        self.Cntr: contourpy.ContourGenerator = Cntr
        self.maxNodesPerWay = maxNodesPerWay
        self.polygon = polygon
        self.transform = transform
        self.rdpEpsilon = rdpEpsilon
        self.rdpMaxVertexDistance = rdpMaxVertexDistance

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

    def splitList(self, l) -> Tuple[List[numpy.ndarray], int, int]:
        """splits a path to contain not more than self.maxNodesPerWay nodes.

        A list of paths containing at least 2 (or, with closed paths, 3) nodes
        is returned, along with the number of nodes and paths as written later to
        the OSM XML output.
        """
        length = self.maxNodesPerWay
        # l = self._cutBeginning(l)
        if len(l) < 2:
            return [], 0, 0
        if length == 0 or len(l) <= length:
            tmpList = [
                l,
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
            tmpList = [l[i : i + length] for i in range(0, len(l) - 1, length - 1)]
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

    def simplifyPath(self, path) -> numpy.ndarray:
        """simplifies a path using a modified version of the Ramer-Douglas-Peucker
        (RDP) algorithm.

        <path>: a contour line path

        other variables used here:
        self.rdpEpsilon: the epsilon value to use in RDP
        self.rdpMaxVertexDistance: RDP is modified in a way that it preserves some
                points if they are too far from each other, even if the point is less
                than epsilon away from an enclosing contour line segment

        A simplified path is returned as numpy array.
        """
        if self.rdpEpsilon is None:
            return path

        def distance(A, B):
            """determines the distance between two points <A> and <B>"""
            return numpy.linalg.norm(A - B)

        def perpendicularDistance(P, S, E):
            """determines the perpendicular distance of <P> to the <S>-<E> segment"""
            if numpy.all(numpy.equal(S, E)):
                return distance(S, P)
            else:
                cp = numpy.cross(P - S, E - S)
                return abs(cp / distance(E, S))

        if self.rdpEpsilon == 0.0:
            return path
        if path.shape[0] <= 2:
            return path
        S = path[0]
        E = path[-1]
        maxInd = 0
        maxDist = 0.0
        for ind, P in enumerate(path[1:-1]):
            dist = perpendicularDistance(P, S, E)
            if dist > maxDist:
                maxDist = dist
                maxInd = ind + 1
        if maxDist <= self.rdpEpsilon and (
            self.rdpMaxVertexDistance is None
            or distance(S, E) <= self.rdpMaxVertexDistance
        ):
            return numpy.array([S, E])
        elif maxDist <= self.rdpEpsilon:
            ind = 0
            for ind, P in enumerate(path[1:-1]):
                if distance(S, P) > self.rdpMaxVertexDistance:
                    break
            if ind == 0:
                return numpy.vstack((S, path[1], self.simplifyPath(path[2:])))
            else:
                return numpy.vstack((S, self.simplifyPath(path[ind:])))
        else:
            path = numpy.vstack(
                (
                    self.simplifyPath(path[: maxInd + 1]),
                    self.simplifyPath(path[maxInd:])[1:],
                )
            )
            return path

    # Actually returns Tuple[List[numpy.typing.ArrayLike[numpy.typing.ArrayLike[numpy.float64]]], int, int]
    # But can't be typed correctly yet...
    # https://stackoverflow.com/questions/66657117/type-hint-2d-numpy-array
    def trace(self, elevation: int, **kwargs) -> Tuple[List[numpy.ndarray], int, int]:
        """this emulates matplotlib.cntr.Cntr's trace method.
        The difference is that this method returns already split paths,
        along with the number of nodes and paths as expected in the OSM
        XML output.  Also, consecutive identical nodes are removed.
        """
        # Keep only the first element of the tuple, ignoring matplot line code
        rawPaths: List[numpy.ndarray] = self.Cntr.create_contour(elevation)[0]
        numOfPaths, numOfNodes = 0, 0
        resultPaths = []
        for path in rawPaths:
            path = self.simplifyPath(path)
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
    transform: Callable,
    polygon,
    rdp_epsilon,
    rdp_max_vertex_distance,
) -> ContourObject:
    """Build countours generator object."""
    contours: ContourObject = ContourObject(
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
        rdp_max_vertex_distance,
    )
    return contours
