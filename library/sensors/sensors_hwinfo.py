import math
import struct
import ctypes
import ctypes.wintypes
from typing import Tuple

import library.sensors.sensors as sensors
from library.log import logger

try:
    import library.sensors.sensors_python as python_sensors
except:
    python_sensors = None

try:
    import win32com.client
    _wmi_available = True
except:
    _wmi_available = False

_wmi_temp = math.nan
_wmi_freq = math.nan
_wmi_initialized = False

SHARED_MEM_PATH = "Global\\HWiNFO_SENS_SM2"
FILE_MAP_READ = 0x0004
HWINFO_SIG = 0x53695748
SENSOR_TYPE_TEMP = 1
SENSOR_TYPE_CLOCK = 6

_hwinfo_available = False
_cached_cpu_temp = math.nan
_cached_cpu_freq = math.nan


def _read_lhm_wmi():
    global _wmi_temp, _wmi_freq, _wmi_initialized
    try:
        if not _wmi_initialized:
            wmi = win32com.client.GetObject("winmgmts:root\\LibreHardwareMonitor")
            _wmi_conn = wmi
            _wmi_initialized = True
        sensors_data = _wmi_conn.ExecQuery("SELECT * FROM Sensor")
        temp = math.nan
        freqs = []
        for s in sensors_data:
            name = str(s.Name)
            stype = str(s.SensorType)
            val = s.Value
            if val is None:
                continue
            if stype == "Temperature":
                if name == "CPU Package" or name == "CPU" or name == "Core Average":
                    if math.isnan(temp) or float(val) > temp:
                        temp = float(val)
                elif name == "Core Max" and math.isnan(temp):
                    temp = float(val)
            elif stype == "Clock":
                if name.startswith("CPU Core #") and val > 100:
                    freqs.append(float(val))
        if not math.isnan(temp):
            _wmi_temp = temp
        if freqs:
            _wmi_freq = max(freqs)
        return _wmi_temp, _wmi_freq
    except:
        return _wmi_temp, _wmi_freq


def _read_shared_mem():
    global _hwinfo_available, _cached_cpu_temp, _cached_cpu_freq
    _cached_cpu_temp = math.nan
    _cached_cpu_freq = math.nan

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenFileMappingW.restype = ctypes.wintypes.HANDLE
    kernel32.OpenFileMappingW.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
    kernel32.MapViewOfFile.restype = ctypes.c_void_p
    kernel32.MapViewOfFile.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
                                       ctypes.c_size_t, ctypes.c_size_t]
    kernel32.UnmapViewOfFile.restype = ctypes.wintypes.BOOL
    kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
    kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

    h = kernel32.OpenFileMappingW(FILE_MAP_READ, False, SHARED_MEM_PATH)
    if not h:
        _hwinfo_available = False
        return

    p = kernel32.MapViewOfFile(h, FILE_MAP_READ, 0, 0, 0)
    kernel32.CloseHandle(h)
    if not p:
        _hwinfo_available = False
        return

    try:
        base = ctypes.addressof(p.contents) if hasattr(p, 'contents') else int(p)
        raw = ctypes.string_at(base, 44)
        sig = struct.unpack_from('<I', raw, 0)[0]
        if sig != HWINFO_SIG:
            _hwinfo_available = False
            return

        _hwinfo_available = True
        ro = struct.unpack_from('<I', raw, 32)[0]
        rc = struct.unpack_from('<I', raw, 40)[0]

        for i in range(rc):
            off = ro + i * 460
            entry = ctypes.string_at(base + off, 316)
            sensor_type = struct.unpack_from('<I', entry, 0)[0]
            name_raw = entry[12:140]
            null_pos = name_raw.find(b'\x00')
            name = name_raw[:null_pos].decode('ascii', errors='replace') if null_pos >= 0 else ''
            value = struct.unpack_from('<d', entry, 284)[0]
            name_lower = name.lower()

            if sensor_type == SENSOR_TYPE_TEMP and value > 0:
                if 'cpu package' in name_lower:
                    if math.isnan(_cached_cpu_temp) or value > _cached_cpu_temp:
                        _cached_cpu_temp = value
                elif 'core max' in name_lower:
                    if math.isnan(_cached_cpu_temp):
                        _cached_cpu_temp = value

            if sensor_type == SENSOR_TYPE_CLOCK and value > 100:
                if 'p-core' in name_lower or 'e-core' in name_lower and 'effective' not in name_lower:
                    if math.isnan(_cached_cpu_freq) or value > _cached_cpu_freq:
                        _cached_cpu_freq = value
    finally:
        kernel32.UnmapViewOfFile(p)


if _wmi_available:
    try:
        _read_lhm_wmi()
    except:
        pass


class Cpu(sensors.Cpu):
    @staticmethod
    def percentage(interval: float) -> float:
        if python_sensors:
            return python_sensors.Cpu.percentage(interval)
        return math.nan

    @staticmethod
    def frequency() -> float:
        try:
            _read_shared_mem()
            if not math.isnan(_cached_cpu_freq) and _cached_cpu_freq > 0:
                return _cached_cpu_freq
        except:
            pass
        if _wmi_available:
            _, freq = _read_lhm_wmi()
            if not math.isnan(freq) and freq > 0:
                return freq
        if python_sensors:
            return python_sensors.Cpu.frequency()
        return math.nan

    @staticmethod
    def load() -> Tuple[float, float, float]:
        if python_sensors:
            return python_sensors.Cpu.load()
        return math.nan, math.nan, math.nan

    @staticmethod
    def temperature() -> float:
        try:
            _read_shared_mem()
            if not math.isnan(_cached_cpu_temp) and _cached_cpu_temp > 0:
                return _cached_cpu_temp
        except:
            pass
        if _wmi_available:
            temp, _ = _read_lhm_wmi()
            if not math.isnan(temp) and temp > 0:
                return temp
        if python_sensors:
            return python_sensors.Cpu.temperature()
        return math.nan

    @staticmethod
    def fan_percent(fan_name: str = None) -> float:
        if python_sensors:
            return python_sensors.Cpu.fan_percent(fan_name)
        return math.nan


_RTSS_MEMORY_MAP_NAME = "RTSSSharedMemoryV2"
_RTSS_FPS_FRAME_INDEX = 0x1F4
_RTSS_FPS_FRAME_TIME_INDEX = 0x1F5

_RTSS_BUFFER_ENTRY_STRIDE = 0x400
_RTSS_ENTRY_FRAMERATE = 8

_rtss_available = False


def _check_rtss():
    global _rtss_available
    try:
        import mmap
        size = 4 + 4 + 4 + 4
        mmap.mmap(-1, size, _RTSS_MEMORY_MAP_NAME).close()
        _rtss_available = True
    except:
        _rtss_available = False


_check_rtss()


def _read_rtss_fps() -> float:
    if not _rtss_available:
        return math.nan
    try:
        import mmap
        size = 0x10000
        m = mmap.mmap(-1, size, _RTSS_MEMORY_MAP_NAME)
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


class Gpu(python_sensors.Gpu if python_sensors else sensors.Gpu):
    @staticmethod
    def fps() -> float:
        fps = _read_rtss_fps()
        if not math.isnan(fps):
            return fps
        return math.nan


class Memory(python_sensors.Memory if python_sensors else sensors.Memory):
    pass


class Disk(python_sensors.Disk if python_sensors else sensors.Disk):
    pass


class Net(python_sensors.Net if python_sensors else sensors.Net):
    pass
