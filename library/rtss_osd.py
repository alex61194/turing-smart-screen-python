import ctypes
import ctypes.wintypes
import struct

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.OpenFileMappingW.restype = ctypes.wintypes.HANDLE
_kernel32.OpenFileMappingW.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
_kernel32.MapViewOfFile.restype = ctypes.c_void_p
_kernel32.MapViewOfFile.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.c_size_t]
_kernel32.UnmapViewOfFile.restype = ctypes.wintypes.BOOL
_kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
_kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
_kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

_last_fps = 0


def _open_rtss():
    h = _kernel32.OpenFileMappingW(0x0004, False, "RTSSSharedMemoryV2")
    if not h:
        return None, None
    p = _kernel32.MapViewOfFile(h, 0x0004, 0, 0, 0)
    if not p:
        _kernel32.CloseHandle(h)
        return None, None
    return h, p


def _close_rtss(h, p):
    if p:
        _kernel32.UnmapViewOfFile(p)
    if h:
        _kernel32.CloseHandle(h)


def read_fps() -> int:
    global _last_fps
    h, p = _open_rtss()
    if not p:
        _last_fps = 0
        return 0
    try:
        entry_size = struct.unpack_from("<I", ctypes.string_at(p + 8, 4))[0]
        arr_offset = struct.unpack_from("<I", ctypes.string_at(p + 12, 4))[0]
        arr_count = struct.unpack_from("<I", ctypes.string_at(p + 16, 4))[0]
        best_fps = 0.0
        for i in range(arr_count):
            eb = p + arr_offset + i * entry_size
            pid = struct.unpack_from("<I", ctypes.string_at(eb, 4))[0]
            if pid == 0:
                continue
            t0 = struct.unpack_from("<I", ctypes.string_at(eb + 268, 4))[0]
            t1 = struct.unpack_from("<I", ctypes.string_at(eb + 272, 4))[0]
            frames = struct.unpack_from("<I", ctypes.string_at(eb + 276, 4))[0]
            dt = t1 - t0
            if dt > 0 and frames > 0:
                fps = float(int(frames * 1000.0 / dt))
                if fps > best_fps:
                    best_fps = fps
        if best_fps > 0:
            _last_fps = int(best_fps)
            return _last_fps
    finally:
        _close_rtss(h, p)
    _last_fps = 0
    return 0


def write_osd(text: str) -> bool:
    h, p = _open_rtss()
    if not p:
        return False
    try:
        sig = struct.unpack_from("<I", ctypes.string_at(p, 4))[0]
        osd_entry_size = struct.unpack_from("<I", ctypes.string_at(p + 20, 4))[0]
        osd_array_offset = struct.unpack_from("<I", ctypes.string_at(p + 24, 4))[0]
        osd_array_count = struct.unpack_from("<I", ctypes.string_at(p + 28, 4))[0]

        if osd_array_count == 0 or osd_entry_size < 8:
            return False

        entry = p + osd_array_offset
        pid_bytes = struct.pack("<I", 0)
        ctypes.memmove(entry, pid_bytes, 4)

        encoded = text.encode("utf-16-le") + b"\x00\x00"
        max_bytes = osd_entry_size - 4
        if len(encoded) > max_bytes:
            encoded = encoded[:max_bytes]
        ctypes.memmove(entry + 4, encoded, len(encoded))
        return True
    finally:
        _close_rtss(h, p)


def clear_osd() -> bool:
    return write_osd("")


def is_running() -> bool:
    h, p = _open_rtss()
    if p:
        _close_rtss(h, p)
        return True
    return False
