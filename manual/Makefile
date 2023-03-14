.PHONY: all clean

MANPAGE_FILE:=phyghtmap.1
HTML_FILE:=${MANPAGE_FILE}.html
PLAIN_HTML_FILE:=${MANPAGE_FILE}.plain.html

all: ${HTML_FILE}

${MANPAGE_FILE}: ../phyghtmap/main.py phyghtmap.help2man
	help2man --no-info --include phyghtmap.help2man "python3 ../phyghtmap/main.py" |\
		sed -e s/main.py/phyghtmap/ > phyghtmap.1

${HTML_FILE}: ${MANPAGE_FILE}
	man2html ${MANPAGE_FILE} |sed -e s/FBPHYGHTMAPFR/PHYGHTMAP/ \
		| sed -e s/"<A HREF.*man2html<\/A>"/man2html/ \
		| sed -e s/"<I>,"//g \
		| sed -e s/"\/<\/I>"//g \
		| sed -e s/"Content-type: text\/html; charset=UTF-8"// \
		| sed -e s/"<A HREF.*Contents<\/A>"// > ${HTML_FILE}

${PLAIN_HTML_FILE}: ${MANPAGE_FILE}
	man2html ${MANPAGE_FILE} > ${PLAIN_HTML_FILE}

clean:
	rm phyghtmap.1*
