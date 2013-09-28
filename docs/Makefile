manpage: ../phyghtmap/main.py phyghtmap.help2man
	echo "#!/usr/bin/env python" > ../phyghtmap/phyghtmap_main.py
	cat ../phyghtmap/main.py >> ../phyghtmap/phyghtmap_main.py
	chmod 755 ../phyghtmap/phyghtmap_main.py
	help2man --no-info --include phyghtmap.help2man ../phyghtmap/phyghtmap_main.py |\
		sed -e s/phyghtmap_main.py/phyghtmap/ > phyghtmap.1
	rm ../phyghtmap/phyghtmap_main.py

html: manpage
	man2html phyghtmap.1 |sed -e s/FBPHYGHTMAPFR/PHYGHTMAP/ \
		| sed -e s/"<A HREF.*man2html<\/A>"/man2html/ \
		| sed -e s/"Content-type: text\/html"// \
		| sed -e s/"<A HREF.*Contents<\/A>"// > phyghtmap.1.html

