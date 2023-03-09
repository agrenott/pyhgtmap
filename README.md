[![Python: 33.9, 3.10](https://img.shields.io/badge/python-3.9%20%7C%203.10-blue)](https://www.python.org)
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

For a detailed help, run

```bash
phyghtmap --help
```

on the console.

# Development

## Profiling

```bash
pip install yappi
python -m yappi -f callgrind -o yappi_ex1.out ../../phyghtmap/main.py --pbf --log=DEBUG N43E006.hgt
```

Then open `yappi_ex1.out` with some callgrind viewer (eg. QCacheGrind).
