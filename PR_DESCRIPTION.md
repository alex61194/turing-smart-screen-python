## RTSS FPS sensor & suspend/resume support

### 1. RTSS FPS support via new `HW_SENSORS: RTSS` backend

Adds a new sensor backend (`sensors_rtss.py`) that reads in-game FPS from **RTSS (RivaTuner Statistics Server) shared memory** (`RTSSSharedMemoryV2`), while using **LibreHardwareMonitor WMI** for all other hardware readings (CPU, GPU temps/freqs, etc.).

**Why RTSS:** RTSS hooks into any DirectX/OpenGL/Vulkan game and reports real-time framerate regardless of GPU vendor (NVIDIA, AMD, Intel). The existing LHM FPS reading via `Hardware.SensorType.Factor` is unreliable — it depends on the GPU model and driver.

**Fallback chain:**
1. RTSS shared memory for FPS
2. LibreHardwareMonitor WMI for all other sensors
3. Python libraries (psutil) as final fallback

**New config option in `config.yaml`:**
```yaml
# - RTSS  use LHM WMI for hardware sensors + RTSS for GPU FPS (Windows only)
```

### 2. Suspend/Resume & Graceful Shutdown (`power_handler.py`)

A lightweight file-based signaling mechanism that allows external scripts (e.g. Windows Task Scheduler on suspend/resume events) to signal the main process to **pause sensor polling** during sleep and **resume** after wake.

The main loop in `main.py` now checks for a `.shutdown_signal` file instead of looping infinitely, so it can break out cleanly when signaled.

**Example usage (Task Scheduler on Suspend):**
```python
from power_handler import signal_shutdown
signal_shutdown()  # creates .shutdown_signal, main loop exits cleanly
```

**Example usage (Task Scheduler on Resume):**
```python
from power_handler import clear_shutdown
clear_shutdown()  # removes .shutdown_signal, main loop can restart
```

No mandatory changes — existing behavior is preserved when `HW_SENSORS: AUTO` (the default).
