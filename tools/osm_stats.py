"""
Basic stats on OSM file (supporting formats managed by osmium).

Usage:
python tools/osm_stats.py [files to analyze]

Example:
python tools/osm_stats.py tests/data/lon6*view1_*.pbf
"""

import os
import sys

import osmium


class Counter(osmium.SimpleHandler):
    def __init__(self):
        osmium.SimpleHandler.__init__(self)
        self.num_nodes = 0
        self.num_ways = 0
        self.num_relations = 0

    # this method runs for each node
    def node(self, n):
        self.num_nodes += 1

    # this method runs for each way
    def way(self, w):
        self.num_ways += 1

    # this method runs for each relation
    def relation(self, r):
        self.num_relations += 1


def main() -> None:
    for file_name in sys.argv[1:]:
        counter = Counter()
        counter.apply_file(file_name)

        print(f"File name: {file_name}")
        print(f"File size: {os.stat(file_name).st_size / 1024:.2f} KiB")
        print(f"Number of nodes : {counter.num_nodes}")
        print(f"Number of ways : {counter.num_ways}")
        print(f"Number of relations: {counter.num_relations}\n")


if __name__ == "__main__":
    main()
    sys.exit(0)
