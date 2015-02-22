manpage: ../phyghtmap/main.py phyghtmap.help2man
	mkdir build
	echo "#!/usr/bin/python" > build/main.py
	for i in $$(ls ../phyghtmap/*.py); do \
		cat $$i | sed -e s/from\ phyghtmap\ import/import/ |\
			sed -e s/from\ phyghtmap.varint\ import/from\ varint\ import/ \
			>> build/$$(basename $$i); \
		done
	chmod 755 build/main.py
	help2man --no-info --include phyghtmap.help2man "python2 build/main.py" |\
		sed -e s/main.py/phyghtmap/ > phyghtmap.1
	rm -rf build/

html: manpage
	man2html phyghtmap.1 |sed -e s/FBPHYGHTMAPFR/PHYGHTMAP/ \
		| sed -e s/"<A HREF.*man2html<\/A>"/man2html/ \
		| sed -e s/"Content-type: text\/html"// \
		| sed -e s/"<A HREF.*Contents<\/A>"// > phyghtmap.1.html

clean:
	rm phyghtmap.1*
