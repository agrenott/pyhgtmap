[![Python: 3.9, 3.10](https://img.shields.io/badge/python-3.9%20%7C%203.10-blue)](https://www.python.org)
![GitHub](https://img.shields.io/github/license/agrenott/phyghtmap)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/agrenott/phyghtmap/pythonpackage.yaml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

This is a little program which lets you easily generate OSM contour lines from
NASA SRTM data.  It was initially created as replacement for srtm2osm which
stopped working when the NASA changed the server and started distributing the
raw SRTM data via http instead of ftp.  In the meanwhile, srtm2osm is working
again due to the efforts of bomm.

However, phyghtmap has some advantages compared to srtm2osm.  One is that you
won't need a C# runtime environment installed on your machine.  Another
important thing is that phyghtmap generates already tiled data.  Furthermore,
phyghtmap seems to slightly outperform srtm2osm.  If you are using a multi-core
machine and are running a POSIX compliant operating system you can use a very
simple form of parallelization and the advance will be dramatical.

Note that the intended use is not to upload generated contour OSM data to the
OSM servers but to use it for fancy maps.

# Installation

For ubuntu-like system:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
# Install GDAL via system package, as it's painful to install through PIP
sudo apt install python3-gdal 
# Create virtual env
python3 -m venv my_venv
# Switch to venv
. ./my_venv/bin/activate
# Install phyghtmap with dependencies from latest git version
pip install git+https://github.com/agrenott/phyghtmap.git
```

# Usage

For a detailed help, run `phyghtmap --help` on the console.

## Example output

Generating contours for France [PACA region](https://download.geofabrik.de/europe/france/provence-alpes-cote-d-azur.html) with a 10m step and 0.00001 RDP Epsilon (taking less than a minute on Intel 13600K via Windows WSL 1):

```
> phyghtmap --polygon=provence-alpes-cote-d-azur/provence-alpes-cote-d-azur.poly --step=10 --pbf --hgtdir=work/hgt --source=view1,view3 --simplifyContoursEpsilon=0.00001 -j16
...
> du -shc lon*.pbf |tail -3
196K    lon7.00_7.75lat44.69_44.75_view1.osm.pbf
168K    lon7.00_7.75lat44.75_44.88_view1.osm.pbf
81M     total
> ls -l lon*.pbf |wc -l
104
```

Contour lines displayed over OSM map using QGis:

![PACA 10m contours](doc/phyghtmap_FRA_PACA.jpg)

![PACA 10m contours - zoom in mountains area](doc/phyghtmap_FRA_PACA_zoom.jpg)

## A word on contour simplification

phyghtmap now uses very efficient [pybind11-rdp](https://github.com/cubao/pybind11-rdp) Ramer-Douglas-Peucker Algorithm library for contour simplification. This makes RDP activation the best solution in most cases, as the slight overhead in computing performance is compensated by the reduced number of points to write (which is now the most time consuming part). It also reduces the final file size.

Epsilon value must be chosen with care to get the proper tradeoff between efficiency and quality.

Here is an example originating from a "view1" source with 10m step (lon6.00_7.00lat43.00_43.25_view1.osm.pbf):

|         RDP Epsilon values          | Disabled |   0    |                                       0.00001                                       |                                      0.0001                                       |
| :---------------------------------: | :------: | :----: | :---------------------------------------------------------------------------------: | :-------------------------------------------------------------------------------: |
|           Visual details            |          |        |        ![Comparison between RDP 0 and 0.00001 results](doc/rdp_0_00001.png)         | ![Comparison between RDP 0, 0.0001 and 0.00001 results](doc/rdp_0_0001_00001.png) |
|                                     |          |        | Blue lines (Epsilon=0.00001) are almost indistinguishable from red ones (Epsilon=0) |            Clear difference appears for green lines (Epsilon = 0.0001)            |
| File size (1 tile, PBF format, KiB) |   1840   |  1717  |                                        1424                                         |                                        716                                        |
|      Number of nodes (1 tile)       |  869685  | 761085 |                                       559678                                        |                                      210744                                       |

# Development

The one-liner for local validation:
```bash
black tests/ phyghtmap tools && mypy && coverage run -m pytest --mpl && coverage html
```

## Profiling

```bash
pip install yappi
python -m yappi -f callgrind -o yappi_ex1.out ../../phyghtmap/main.py --pbf --log=DEBUG N43E006.hgt
```

Then open `yappi_ex1.out` with some callgrind viewer (eg. QCacheGrind).
