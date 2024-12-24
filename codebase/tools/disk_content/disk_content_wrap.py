import os, sys
import ctypes

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# Load the shared library
lib = ctypes.CDLL(codebase_dir + '/tools/disk_content/ctx.so')

lib.get_content = lib.get_content
lib.get_content.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
# the return type should be void*,
# because ctypes returns a regular Python string object if the return type is c_type_p
# https://stackoverflow.com/questions/13445568/python-ctypes-how-to-free-memory-getting-invalid-pointer-error
lib.get_content.restype = ctypes.c_void_p

lib.free_content_string = lib.free_content_string
lib.free_content_string.argtypes = [ctypes.c_void_p]
lib.free_content_string.restype = None

# Define a helper function to call the C++ function
def call_get_content(path, desc):
    path = path.encode('utf-8')
    desc = desc.encode('utf-8')

    path_ptr = ctypes.cast(path, ctypes.c_char_p)
    desc_ptr = ctypes.cast(desc, ctypes.c_char_p)
    result_ptr = lib.get_content(path_ptr, desc_ptr)

    if result_ptr is None:
        return ""

    result = ctypes.cast(result_ptr, ctypes.c_char_p).value.decode('utf-8', errors='ignore')

    lib.free_content_string(result_ptr)

    return result

def test_1():
    # Usage
    path = "."
    desc = "test python wrap"
    result = call_get_content(path, desc)
    print(result)