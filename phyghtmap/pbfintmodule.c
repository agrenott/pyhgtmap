#include <Python.h>

#if defined(_MSC_VER) || defined(__BORLANDC__)
typedef unsigned __int64 ulong64;
typedef signed __int64 long64;
#else
typedef unsigned long long ulong64;
typedef signed long long long64;
#endif

static PyObject * pbfint_sint2str(PyObject *self, PyObject *args) {
	long64 number;
	char b;
	char s[10];
	int count = 0;

	if (!PyArg_ParseTuple(args, "L", &number))
		return NULL;

	if (number < 0) {
		number = -number-0x01;
		number <<= 0x01;
		number |= 0x01;
	} else {
		number <<= 0x01;
	}

	b = number&0x7f;
	number >>= 0x07;
	for (count=0; number>0; ++count) {
		s[count] = b|0x80;
		b = number&0x7f;
		number >>= 0x07;
	}
	s[count] = b;

	return Py_BuildValue("s#", &s, count+1);
	//return Py_BuildValue("i", count);
}

static PyObject * pbfint_int2str(PyObject *self, PyObject *args) {
	ulong64 number;
	char b;
	char s[10];
	int count = 0;

	if (!PyArg_ParseTuple(args, "K", &number))
		return NULL;

	b = number&0x7f;
	number >>= 0x07;
	for (count=0; number>0; ++count) {
		s[count] = b|0x80;
		b = number&0x7f;
		number >>= 0x07;
	}
	s[count] = b;

	return Py_BuildValue("s#", &s, count+1);
	//return Py_BuildValue("i", count);
}

static PyMethodDef PbfintMethods[] = {
	{"int2str", pbfint_int2str, METH_VARARGS,
		"return the varint string representation of an unsigned number."},
	{"sint2str", pbfint_sint2str, METH_VARARGS,
		"return the varint string representation of a signed number."},
	{NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initpbfint(void) {
	(void) Py_InitModule("pbfint", PbfintMethods);
}

//int main(int argc, char *argv[]) {
	///* Pass argv[0] to the Python interpreter */
	//Py_SetProgramName(argv[0]);
//
	///* Initialize the Python interpreter.  Required. */
	//Py_Initialize();
//
	///* Add a static module */
	//initpbfint();
//}
