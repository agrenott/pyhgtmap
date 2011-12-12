manpage: ../phyghtmap/main.py phyghtmap.help2man
	help2man --no-info --include phyghtmap.help2man ../phyghtmap/main.py |\
		sed -e s/main.py/phyghtmap/ > phyghtmap.1

html: manpage
	man2html phyghtmap.1 |sed -e s/FBPHYGHTMAPFR/PHYGHTMAP/ \
		| sed -e s/"<A HREF.*man2html<\/A>"/man2html/ \
		| sed -e s/"Content-type: text\/html"// \
		| sed -e s/"<A HREF.*Contents<\/A>"// > phyghtmap.1.html

