manpage: ../phyghtmap/main.py phyghtmap.help2man
	mkdir build
	echo "#!/usr/bin/python3" > build/main.py
	for i in $$(ls ../phyghtmap/*.py); do \
		cat $$i | sed -e s/from\ phyghtmap\ import/import/ |\
			sed -e s/from\ phyghtmap.varint\ import/from\ varint\ import/ \
			>> build/$$(basename $$i); \
		done
	chmod 755 build/main.py
	help2man --no-info --include phyghtmap.help2man "python3 build/main.py" |\
		sed -e s/main.py/phyghtmap/ > phyghtmap.1
	rm -rf build/

manpage_old: ../phyghtmap/main.py phyghtmap.help2man
	mkdir build
	echo "#!/usr/bin/python3" > build/main.py
	for i in $$(ls ../phyghtmap/*.py); do \
		cat $$i | sed -e s/from\ phyghtmap\ import/import/ |\
			sed -e s/from\ phyghtmap.varint\ import/from\ varint\ import/ \
			>> build/$$(basename $$i); \
		done
	chmod 755 build/main.py
	help2man --no-info --include phyghtmap.help2man "python3 build/main.py" |\
		sed -e s/main.py/phyghtmap/ > phyghtmap.1
	rm -rf build/

html: manpage
	man2html phyghtmap.1 |sed -e s/FBPHYGHTMAPFR/PHYGHTMAP/ \
		| sed -e s/"<A HREF.*man2html<\/A>"/man2html/ \
		| sed -e s/"<I>,"//g \
		| sed -e s/"\/<\/I>"//g \
		| sed -e s/"Content-type: text\/html; charset=UTF-8"// \
		| sed -e s/"<A HREF.*Contents<\/A>"// > phyghtmap.1.html

plainhtml: manpage
	man2html phyghtmap.1 > phyghtmap.1.plain.html

clean:
	rm phyghtmap.1*
