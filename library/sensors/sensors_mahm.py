# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# This file reads CPU / GPU / RAM data from MSI Afterburner's "MAHM" shared
# memory instead of LibreHardwareMonitor. This means:
#   - No administrator rights required (LHM needs elevation, MAHM doesn't).
#   - MSI Afterburner must be running in the background, with the desired
#     items checked in Settings -> Monitoring (Ctrl+S). Only checked items
#     are written to shared memory - anything unchecked will read as NaN.
#   - Coverage is narrower than LHM: no per-core CPU temps/clocks, no
#     motherboard/VRM sensors, no disk/network stats. Disk and Net below
#     fall back to psutil, same approach as sensors_python.py.
#   - The MAHM layout is not officially documented by MSI; it's reverse
#     engineered by the community and has been stable for years, but if a
#     future Afterburner build changes it, or if your language/version uses
#     different item names than the ones matched below, run
#     debug_dump_sources() once (see bottom of file) to print every
#     szSrcName your Afterburner session actually exposes, then adjust the
#     _NAME_CANDIDATES lists accordingly.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import ctypes
import ctypes.wintypes
import math
import struct
import threading
from typing import Optional, Tuple

import psutil

import library.sensors.sensors as sensors
from library.log import logger

try:
    from library.sensors.rtss_osd import read_fps as _read_rtss_fps
except ImportError:
    def _read_rtss_fps() -> int:
        return 0

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.OpenFileMappingW.restype = ctypes.wintypes.HANDLE
_kernel32.OpenFileMappingW.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
_kernel32.MapViewOfFile.restype = ctypes.c_void_p
_kernel32.MapViewOfFile.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
                                     ctypes.wintypes.DWORD, ctypes.c_size_t]
_kernel32.UnmapViewOfFile.restype = ctypes.wintypes.BOOL
_kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
_kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
_kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

_MAHM_MAP_NAME = "MAHMSharedMemory"
_FILE_MAP_READ = 0x0004
_MAHM_SIGNATURE = 0x4D41484D  # 'MAHM'
_MAX_PATH = 260

# Cached mapping, same pattern as rtss_osd.py: open once, reuse, reopen only
# on failure (Afterburner restarted, etc).
_mapping_lock = threading.Lock()
_cached_h = None
_cached_p = None


def _open_mahm():
    global _cached_h, _cached_p
    with _mapping_lock:
        if _cached_p:
            return _cached_h, _cached_p
        h = _kernel32.OpenFileMappingW(_FILE_MAP_READ, False, _MAHM_MAP_NAME)
        if not h:
            return None, None
        p = _kernel32.MapViewOfFile(h, _FILE_MAP_READ, 0, 0, 0)
        if not p:
            _kernel32.CloseHandle(h)
            return None, None
        _cached_h, _cached_p = h, p
        return h, p


def _invalidate_mapping():
    global _cached_h, _cached_p
    with _mapping_lock:
        if _cached_p:
            _kernel32.UnmapViewOfFile(_cached_p)
        if _cached_h:
            _kernel32.CloseHandle(_cached_h)
        _cached_h, _cached_p = None, None


def _read_cstr(base: int, offset: int) -> str:
    raw = ctypes.string_at(base + offset, _MAX_PATH)
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="ignore")


def _read_sources() -> Tuple[dict, dict]:
    """Reads the whole MAHM shared memory and returns:
       - sources: {szSrcName_lower: {"data": float, "gpu": int, "units": str}}
       - gpus: {gpu_index: {"device": str, "mem_total_mb": int}}
       Returns ({}, {}) if Afterburner / shared memory isn't available.
    """
    h, p = _open_mahm()
    if not p:
        return {}, {}
    try:
        header = ctypes.string_at(p, 32)
        signature, version, header_size, num_entries, entry_size, _time, num_gpu, gpu_entry_size = \
            struct.unpack_from("<8I", header, 0)
        if signature != _MAHM_SIGNATURE:
            _invalidate_mapping()
            return {}, {}

        sources = {}
        for i in range(num_entries):
            base = p + header_size + i * entry_size
            name = _read_cstr(base, 0)
            # Layout: szSrcName[260], szSrcUnits[260], szLocalizedSrcName[260],
            # szLocalizedSrcUnits[260], szRecommendedFormat[260], then data/limits/flags.
            data_off = _MAX_PATH * 5
            data, min_limit, max_limit = struct.unpack_from("<3f", ctypes.string_at(base + data_off, 12), 0)
            flags, gpu_idx, src_id = struct.unpack_from("<3I", ctypes.string_at(base + data_off + 12, 12), 0)
            if name:
                sources[name.lower()] = {"data": data, "gpu": gpu_idx, "src_id": src_id}

        gpus = {}
        gpu_array_base = p + header_size + num_entries * entry_size
        for g in range(num_gpu):
            base = gpu_array_base + g * gpu_entry_size
            device = _read_cstr(base, _MAX_PATH * 2)  # szGpuId, szFamily, szDevice
            (mem_amount,) = struct.unpack_from("<I", ctypes.string_at(base + _MAX_PATH * 5, 4), 0)
            gpus[g] = {"device": device, "mem_total_mb": mem_amount}

        return sources, gpus
    except Exception as e:
        logger.warning("MAHM read error (Afterburner closed/restarted?): %s", e)
        _invalidate_mapping()
        return {}, {}


def _find(sources: dict, candidates) -> float:
    """Returns the first matching source's value, trying each candidate name
    (case-insensitive substring match), or NaN if none is found/checked in
    Afterburner's Monitoring settings."""
    for cand in candidates:
        cand_l = cand.lower()
        for name, entry in sources.items():
            if cand_l in name:
                return float(entry["data"])
    return math.nan


# Candidate names: MSI Afterburner labels vary slightly by version/language,
# hence multiple alternatives per metric. Run debug_dump_sources() to see
# exactly what your install exposes if a value stays stuck at NaN.
_CPU_USAGE = ["CPU usage"]
_CPU_TEMP = ["CPU temperature"]
_CPU_CLOCK = ["CPU clock", "CPU Core Clock"]
_CPU_POWER = ["CPU power"]
_GPU_USAGE = ["GPU usage", "GPU1 usage"]
_GPU_TEMP = ["GPU temperature", "GPU1 temperature"]
_GPU_MEM_PCT = ["Memory usage", "GPU1 memory usage"]
_GPU_CORE_CLOCK = ["Core clock", "GPU1 core clock"]
_GPU_POWER = ["Power", "GPU1 power", "Power consumption %"]
_GPU_FAN = ["Fan speed", "GPU1 fan speed"]
_RAM_USAGE = ["RAM usage", "Physical memory usage"]


class Cpu(sensors.Cpu):
    @staticmethod
    def percentage(interval: float) -> float:
        sources, _ = _read_sources()
        return _find(sources, _CPU_USAGE)

    @staticmethod
    def frequency() -> float:
        sources, _ = _read_sources()
        return _find(sources, _CPU_CLOCK)

    @staticmethod
    def load() -> Tuple[float, float, float]:
        # Not tracked by Afterburner; psutil's 1/5/15min load avg is the
        # same fallback sensors_librehardwaremonitor.py already uses.
        try:
            return psutil.getloadavg()
        except Exception:
            return math.nan, math.nan, math.nan

    @staticmethod
    def temperature() -> float:
        sources, _ = _read_sources()
        return _find(sources, _CPU_TEMP)

    @staticmethod
    def fan_percent(fan_name: str = None) -> float:
        # Afterburner doesn't track case/CPU fan headers, only GPU fan(s).
        return math.nan

    @staticmethod
    def power() -> float:
        sources, _ = _read_sources()
        return _find(sources, _CPU_POWER)


class Gpu(sensors.Gpu):
    @staticmethod
    def stats() -> Tuple[float, float, float, float, float]:
        sources, gpus = _read_sources()
        if not sources:
            return math.nan, math.nan, math.nan, math.nan, math.nan

        load = _find(sources, _GPU_USAGE)
        mem_percent = _find(sources, _GPU_MEM_PCT)
        temp = _find(sources, _GPU_TEMP)

        total_mem_mb = math.nan
        if gpus:
            total_mem_mb = float(gpus[min(gpus.keys())]["mem_total_mb"])
        used_mem_mb = (mem_percent / 100.0 * total_mem_mb) if not math.isnan(mem_percent) and not math.isnan(
            total_mem_mb) else math.nan

        return load, mem_percent, used_mem_mb, total_mem_mb, temp

    @staticmethod
    def fps() -> int:
        # FPS still comes from RTSS's own shared memory - MAHM doesn't have it.
        try:
            return int(_read_rtss_fps())
        except Exception:
            return 0

    @staticmethod
    def fan_percent() -> float:
        sources, _ = _read_sources()
        return _find(sources, _GPU_FAN)

    @staticmethod
    def frequency() -> float:
        sources, _ = _read_sources()
        return _find(sources, _GPU_CORE_CLOCK)

    @staticmethod
    def power() -> float:
        sources, _ = _read_sources()
        val = _find(sources, _GPU_POWER)
        if not math.isnan(val) and (val < 0 or val > 1000):
            return math.nan
        return val

    @staticmethod
    def is_available() -> bool:
        sources, gpus = _read_sources()
        return bool(sources) and bool(gpus)


class Memory(sensors.Memory):
    @staticmethod
    def swap_percent() -> float:
        # Not tracked by Afterburner; psutil fallback.
        try:
            return psutil.swap_memory().percent
        except Exception:
            return math.nan

    @staticmethod
    def virtual_percent() -> float:
        sources, _ = _read_sources()
        return _find(sources, _RAM_USAGE)

    @staticmethod
    def virtual_used() -> int:  # bytes
        percent = Memory.virtual_percent()
        if math.isnan(percent):
            return 0
        total = psutil.virtual_memory().total
        return int(total * percent / 100.0)

    @staticmethod
    def virtual_free() -> int:  # bytes
        total = psutil.virtual_memory().total
        return total - Memory.virtual_used()


# Disk and Net aren't part of Afterburner's hardware monitor: keep psutil,
# same as sensors_python.py's implementation.
class Disk(sensors.Disk):
    @staticmethod
    def disk_usage_percent() -> float:
        try:
            return psutil.disk_usage("/").percent
        except Exception:
            return math.nan

    @staticmethod
    def disk_used() -> int:
        try:
            return psutil.disk_usage("/").used
        except Exception:
            return 0

    @staticmethod
    def disk_free() -> int:
        try:
            return psutil.disk_usage("/").free
        except Exception:
            return 0


class Net(sensors.Net):
    _last = {}

    @staticmethod
    def stats(if_name, interval) -> Tuple[int, int, int, int]:
        try:
            import time
            counters = psutil.net_io_counters(pernic=True).get(if_name)
            if not counters:
                return 0, 0, 0, 0
            now = time.time()
            prev = Net._last.get(if_name)
            Net._last[if_name] = (now, counters.bytes_sent, counters.bytes_recv)
            if not prev:
                return 0, counters.bytes_sent, 0, counters.bytes_recv
            dt = max(now - prev[0], 0.001)
            up_rate = int((counters.bytes_sent - prev[1]) / dt)
            dl_rate = int((counters.bytes_recv - prev[2]) / dt)
            return up_rate, counters.bytes_sent, dl_rate, counters.bytes_recv
        except Exception:
            return 0, 0, 0, 0


def debug_dump_sources() -> None:
    """Run this once from a Python shell (with Afterburner running) to print
    every source name your install actually exposes, e.g.:
        python -c "import library.sensors.sensors_mahm as m; m.debug_dump_sources()"
    Use the printed names to adjust the _NAME_CANDIDATES lists above if a
    stat isn't showing up.
    """
    sources, gpus = _read_sources()
    if not sources:
        print("No data - is MSI Afterburner running with Hardware Monitor items checked?")
        return
    print(f"GPUs found: {gpus}")
    print(f"{len(sources)} sources:")
    for name, entry in sorted(sources.items()):
        print(f"  {name!r:45s} data={entry['data']:.2f} gpu={entry['gpu']} src_id={entry['src_id']}")
