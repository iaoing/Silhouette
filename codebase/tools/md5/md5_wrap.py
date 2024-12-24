import ctypes

# Load the shared library
lib = ctypes.CDLL('./md5.so')

lib.compute_md5 = lib.compute_md5
lib.compute_md5.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
# the return type should be void*,
# because ctypes returns a regular Python string object if the return type is c_type_p
# https://stackoverflow.com/questions/13445568/python-ctypes-how-to-free-memory-getting-invalid-pointer-error
lib.compute_md5.restype = ctypes.c_void_p

lib.free_md5_string = lib.free_md5_string
lib.free_md5_string.argtypes = [ctypes.c_void_p]
lib.free_md5_string.restype = None

# Define a helper function to call the C++ function
def call_compute_md5(content_bytes):
    content_ptr = ctypes.cast(content_bytes, ctypes.c_char_p)
    size = len(content_bytes)
    result_ptr = lib.compute_md5(content_ptr, size)

    if result_ptr is None:
        return ""

    result = ctypes.cast(result_ptr, ctypes.c_char_p).value.decode('utf-8', errors='ignore')
    result = result[:32]

    lib.free_md5_string(result_ptr)

    return result

def test_1():
    # Usage
    content_bytes = b"Hello, world!"
    result = call_compute_md5(content_bytes)
    print(result)