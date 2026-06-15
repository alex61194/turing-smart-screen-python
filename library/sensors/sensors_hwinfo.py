import math
import struct
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
_wmi_conn = None


def _read_lhm_wmi():
    global _wmi_temp, _wmi_freq, _wmi_initialized, _wmi_conn
    try:
        if not _wmi_initialized:
            _wmi_conn = win32com.client.GetObject("winmgmts:root\\LibreHardwareMonitor")
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


class Cpu(sensors.Cpu):
    @staticmethod
    def percentage(interval: float) -> float:
        if python_sensors:
            return python_sensors.Cpu.percentage(interval)
        return math.nan

    @staticmethod
    def frequency() -> float:
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
_RTSS_BUFFER_ENTRY_STRIDE = 0x400
_RTSS_ENTRY_FRAMERATE = 8

_rtss_available = False


def _check_rtss():
    global _rtss_available
    try:
        import mmap
        mmap.mmap(-1, 16, _RTSS_MEMORY_MAP_NAME).close()
        _rtss_available = True
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
