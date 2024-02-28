.PHONY: all clean

# Requires help2man and man2html system packages

MANPAGE_FILE:=pyhgtmap.1
HTML_FILE:=${MANPAGE_FILE}.html
PLAIN_HTML_FILE:=${MANPAGE_FILE}.plain.html

all: ${HTML_FILE}

${MANPAGE_FILE}: ../pyhgtmap/main.py pyhgtmap.help2man
	help2man --no-info --include pyhgtmap.help2man "python3 ../pyhgtmap/main.py" |\
		sed -e s/main.py/pyhgtmap/ > pyhgtmap.1

${HTML_FILE}: ${MANPAGE_FILE}
	man2html ${MANPAGE_FILE} |sed -e s/FBPYHGTMAPFR/pyhgtmap/ \
		| sed -e s/"<A HREF.*man2html<\/A>"/man2html/ \
		| sed -e s/"<I>,"//g \
		| sed -e s/"\/<\/I>"//g \
		| sed -e s/"Content-type: text\/html; charset=UTF-8"// \
		| sed -e s/"<A HREF.*Contents<\/A>"// > ${HTML_FILE}

${PLAIN_HTML_FILE}: ${MANPAGE_FILE}
	man2html ${MANPAGE_FILE} > ${PLAIN_HTML_FILE}

clean:
	rm pyhgtmap.1*
