from setuptools import setup, find_packages
#from setuptools import setup, find_packages, Extension
import warnings
warnings.filterwarnings("ignore", "Unknown distribution option")

#from phyghtmap import __version__

setup(name="phyghtmap",
	version="2.23",
	packages = find_packages(),
	description="OSM contour lines creator.",
	include_data_files=True,
	author="Adrian Dempwolff",
	author_email="phyghtmap@aldw.de",
	url="http://katze.tfiu.de/projects/phyghtmap/",
	long_description="""phyghtmap creates openstreetmap suitable contour lines from NASA SRTM data.""",
	license="GPLv2+",
	#ext_modules=[
		#Extension("phyghtmap.pbfint", ["phyghtmap/pbfintmodule.c"])
	#],
	entry_points = {
		'console_scripts': [
			'phyghtmap = phyghtmap.main:main',
		],
	},
)

