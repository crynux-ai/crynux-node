package main

// #include <stdlib.h>
// #include <Python.h>
// int PyArg_ParseTuple_U(PyObject*, PyObject**);
import "C"
import "unsafe"

import (
	"encoding/binary"
	"encoding/hex"
	"image"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"os"

	"github.com/corona10/goimagehash"
)

func imagePHash(file io.Reader) (string, error) {
	image, _, err := image.Decode(file)
	if err != nil {
		return "", err
	}
	pHash, err := goimagehash.PerceptionHash(image)
	if err != nil {
		return "", err
	}

	bs := make([]byte, pHash.Bits()/8)
	binary.BigEndian.PutUint64(bs, pHash.GetHash())

	return "0x" + hex.EncodeToString(bs), nil
}

//export getPHash
func getPHash(self *C.PyObject, args *C.PyObject) *C.PyObject {
	var obj *C.PyObject
	if C.PyArg_ParseTuple_U(args, &obj) == 0 {
		return nil
	}
	pyFileBytes := C.PyUnicode_AsUTF8String(obj)
	cFilename := C.PyBytes_AsString(pyFileBytes)
	filename := C.GoString(cFilename)
	file, err := os.Open(filename)
	if err != nil {
		cErrstr := C.CString(err.Error())
		pyErrStr := C.PyUnicode_FromString(cErrstr)
		C.PyErr_SetObject(C.PyExc_RuntimeError, pyErrStr)
		C.free(unsafe.Pointer(cErrstr))
		return nil
	}
	defer file.Close()
	hash, err := imagePHash(file)
	if err != nil {
		cErrstr := C.CString(err.Error())
		pyErrStr := C.PyUnicode_FromString(cErrstr)
		C.PyErr_SetObject(C.PyExc_RuntimeError, pyErrStr)
		C.free(unsafe.Pointer(cErrstr))
		return nil
	}
	cRetstr := C.CString(hash)
	ret := C.PyUnicode_FromString(cRetstr)

	C.free(unsafe.Pointer(cRetstr))
	C.Py_DecRef(pyFileBytes)

	return ret
}

func main() {}
