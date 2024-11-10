/**
 * The MIT License (MIT)
 *
 * Copyright (c) 2019 Erik Moqvist
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include "pyfuzzer_common.h"


static PyObject *test_one_input_p = NULL;
static PyObject *args_p;

int LLVMFuzzerInitialize(int *argc, char ***argv) {
    (void) argc;
    (void) argv;

    pyfuzzer_init(&test_one_input_p, &args_p, NULL);

    if (test_one_input_p == NULL || args_p == NULL) {
        abort();
    }

    return 0;
}

int LLVMFuzzerTestOneInput(const uint8_t *data_p, size_t size)
{
    PyObject *res_p;
    PyObject *data_obj_p;

    data_obj_p = PyBytes_FromStringAndSize((const char *)data_p, size);

    if (data_obj_p == NULL) {
        PyErr_Print();
        exit(1);
    }

    PyTuple_SET_ITEM(args_p, 0, data_obj_p);
    res_p = PyObject_CallObject(test_one_input_p, args_p);
    Py_DECREF(data_obj_p);

    if (res_p != NULL) {
        /* printf("res: %s\n", PyUnicode_AsUTF8(PyObject_Str(res_p))); */
        Py_DECREF(res_p);
    }

    /* if (PyErr_Occurred()) { */
    /*     PyErr_Print(); */
    /* } */

    PyErr_Clear();

    return (0);
}
