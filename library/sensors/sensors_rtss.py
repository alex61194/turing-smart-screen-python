import math
import struct

from library.sensors.sensors_librehardwaremonitor import *
from library.sensors.sensors_librehardwaremonitor import Gpu as _LhmGpuClass
from library.log import logger

_RTSS_MEMORY_MAP_NAME = "RTSSSharedMemoryV2"
_RTSS_BUFFER_ENTRY_STRIDE = 0x400
_RTSS_ENTRY_FRAMERATE = 8

_rtss_available = False


def _check_rtss():
    global _rtss_available
    try:
        import mmap
        mmap.mmap(-1, 16, _RTSS_MEMORY_MAP_NAME).close()
        _rtss_available = True
        logger.info("RTSS shared memory available for FPS reading")
    except:
        _rtss_available = False


_check_rtss()


def _read_rtss_fps() -> float:
    if not _rtss_available:
        return math.nan
    try:
        import mmap
        m = mmap.mmap(-1, 0x10000, _RTSS_MEMORY_MAP_NAME)
        entries = struct.unpack_from('<I', m, 0x3C)[0]
        for i in range(entries):
            off = 0x400 + i * _RTSS_BUFFER_ENTRY_STRIDE
            eid = struct.unpack_from('<I', m, off + 8)[0]
            if eid == _RTSS_ENTRY_FRAMERATE:
                fps = struct.unpack_from('<d', m, off + 0x18)[0]
                m.close()
                if 0 < fps < 999:
                    return round(fps, 1)
                return math.nan
        m.close()
        return math.nan
    except:
        return math.nan


_original_fps = _LhmGpuClass.fps.__func__


@classmethod
def _rtss_fps(cls):
    fps = _read_rtss_fps()
    if not math.isnan(fps) and fps > 0:
        cls.prev_fps = int(fps)
        return cls.prev_fps
    return _original_fps(cls)


_LhmGpuClass.fps = _rtss_fps
