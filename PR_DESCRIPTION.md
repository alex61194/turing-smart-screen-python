## HWiNFO sensor backend + suspend/resume support

### 1. New `HW_SENSORS: HWINFO` backend

Adds a new sensor backend (`sensors_hwinfo.py`) that uses **LibreHardwareMonitor (pythonnet/clr)** for all hardware sensors (CPU temp/freq, GPU stats, memory, disk, network) plus **RTSS (RivaTuner Statistics Server) shared memory** for in-game GPU FPS.

**Fallback chain for FPS:**
1. RTSS shared memory (`RTSSSharedMemoryV2`) — works with any GPU vendor (NVIDIA, AMD, Intel)
2. LibreHardwareMonitor's built-in FPS sensor via `SensorType.Factor`

The existing LHM FPS reading is unreliable — it depends on the GPU model and driver. RTSS hooks into any DirectX/OpenGL/Vulkan game and reports real-time framerate.

**New config option in `config.yaml`:**
```yaml
# - HWINFO  use LHM (pythonnet/clr) for hardware sensors + RTSS for GPU FPS (Windows only)
```

### 2. Suspend/Resume & Session Lock handling (`power_handler.py`)

A standalone process that manages the main system monitor, handling:
- **System suspend/resume** — gracefully stops the monitor before sleep, restarts on wake
- **Session lock/unlock** — stops the monitor when the user locks the session
- **System shutdown** — ensures clean shutdown via a signal file

The `main.py` event loop checks for a `.shutdown_signal` file and exits cleanly when detected, removing the file before stopping.

No mandatory changes — existing behavior is preserved when `HW_SENSORS: AUTO` (the default).
