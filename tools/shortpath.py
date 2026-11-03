"""Return an existing Windows 8.3 path to keep ESP32 compiler commands short."""
import ctypes
import os
import sys


def short_path(path):
    path = os.path.abspath(path)
    if os.name != 'nt':
        return path
    api = ctypes.windll.kernel32.GetShortPathNameW
    api.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    api.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    size = api(path, buffer, len(buffer))
    return buffer.value if 0 < size < len(buffer) else path


if __name__ == '__main__':
    print(short_path(sys.argv[1]))
