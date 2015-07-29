__author__ = "Adrian Dempwolff (adrian.dempwolff@urz.uni-heidelberg.de)"
__version__ = "1.72"
__copyright__ = "Copyright (c) 2009-2015 Adrian Dempwolff"
__license__ = "GPLv2+"

def int2str(n):
	b = n&127
	n >>= 7
	s = ""
	while n:
		s += chr(b|128)
		b = n&127
		n >>= 7
	s += chr(b)
	return s

def sint2str(n):
	if n > -1:
		# 0 or positive, shift 1 to the left
		n <<= 1
		return int2str(n)
	# negative number, take abs(n), decrease by 1, shift 1 to the left, add 1
	# as negative bit
	n = ((-n-1)<<1)|1
	return int2str(n)

def writableInt(integer):
	return chr(integer)

def writableString(string):
	return string

def join(sequence):
	"""takes a sequence of string-like objects and returns them as joined string
	"""
	return "".join(sequence)

bboxStringtypes = (type(str()), type(unicode()))

