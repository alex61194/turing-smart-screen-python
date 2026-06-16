## RTSS FPS support via LibreHardwareMonitor + suspend/resume handling

### 1. RTSS FPS reading added to LHM mode

Adds **RTSS (RivaTuner Statistics Server) shared memory FPS reading** to the existing `sensors_librehardwaremonitor.py` module. No new config options or files needed — just use `HW_SENSORS: LHM` (or `AUTO` on Windows) as before.

**How it works:**
- `Gpu.fps()` now reads from RTSS shared memory (`RTSSSharedMemoryV2`) first
- Falls back to LHM's built-in `SensorType.Factor` FPS sensor if RTSS is not available
- RTSS works with any GPU vendor (NVIDIA, AMD, Intel) and hooks into DirectX/OpenGL/Vulkan

The existing LHM FPS reading via `Hardware.SensorType.Factor` is unreliable — it depends on the GPU model and driver.

### 2. Suspend/Resume & Session Lock handling (`power_handler.py`)

A standalone Windows process that manages the system monitor, handling:
- **System suspend/resume** — gracefully stops the monitor before sleep, restarts on wake
- **Session lock/unlock** — stops the monitor on session lock, restarts on unlock
- **System shutdown** — ensures clean shutdown via a `.shutdown_signal` file

The `main.py` event loop checks for a `.shutdown_signal` file at each iteration and exits cleanly when detected.

No mandatory changes — existing behavior is preserved.
