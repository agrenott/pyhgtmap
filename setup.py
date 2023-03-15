from setuptools import setup, find_packages

# from setuptools import setup, find_packages, Extension
import warnings

warnings.filterwarnings("ignore", "Unknown distribution option")

# from phyghtmap import __version__

setup(
    name="phyghtmap",
    version="2.23",
    packages=find_packages(),
    description="OSM contour lines creator.",
    include_data_files=True,
    author="Adrian Dempwolff",
    author_email="phyghtmap@aldw.de",
    url="http://katze.tfiu.de/projects/phyghtmap/",
    long_description="""phyghtmap creates openstreetmap suitable contour lines from NASA SRTM data.""",
    license="GPLv2+",
    # ext_modules=[
    # Extension("phyghtmap.pbfint", ["phyghtmap/pbfintmodule.c"])
    # ],
    entry_points={
        "console_scripts": [
            "phyghtmap = phyghtmap.main:main",
        ],
    },
    install_requires=[
		# Do NOT pin GDAL version to ease installing it via OS package manager (due to many dependencies)
        "GDAL",
        "matplotlib>=3.4.3",
        "contourpy>=1.0.7",
        "bs4>=0.0.1",
        "numpy>=1.24.2",
        "colorlog>=6.7.0",
        "osmium>=3.6.0",
        "shapely>=2.0.1", 
        "pybind11-rdp>=0.1.3",
        "scipy>=1.8.0"
    ],
)
