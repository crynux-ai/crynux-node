#include <Python.h>

/* Will come from go */
PyObject* getPHash(PyObject*);

/* To shim go's missing variadic function support */
int PyArg_ParseTuple_U(PyObject* args, PyObject** obj) {
    return PyArg_ParseTuple(args, "U", obj);
}

static struct PyMethodDef methods[] = {
    {"getPHash", (PyCFunction)getPHash, METH_VARARGS},
    {NULL, NULL}
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "imhash",
    NULL,
    -1,
    methods
};

PyMODINIT_FUNC PyInit_imhash(void) {
    return PyModule_Create(&module);
}