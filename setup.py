import ez_setup
ez_setup.use_setuptools

from setuptools import setup, find_packages
import warnings
warnings.filterwarnings("ignore", "Unknown distribution option")

#from phyghtmap import __version__

setup(name="phyghtmap",
	version="1.25",
	packages = find_packages(),
	description="OSM contour lines creator.",
	include_data_files=True,
	author="Markus Demleitner, Adrian Dempwolff",
	author_email="msdemlei@users.sf.net, dempwolff@informatik.uni-heidelberg.de",
	url="http://katze.tfiu.de/projects/phyghtmap/",
	long_description="""phyghtmap creates openstreetmap suitable contour lines from NASA SRTM data.""",
	license="GPL",
	entry_points = {
		'console_scripts': [
			'phyghtmap = phyghtmap.main:main',
		],
	},
	)

