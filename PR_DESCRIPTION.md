## HWiNFO sensor integration & suspend/resume support

### 1. HWiNFO + RTSS Hybrid Sensor (`HW_SENSORS: HWINFO`)

Adds a new sensor backend that reads hardware data from **HWiNFO's shared memory** and **in-game FPS from RTSS (RivaTuner Statistics Server) shared memory**.

**CPU readings** come from HWiNFO shared memory (`Global\HWiNFO_SENS_SM2`), with fallback chain:
1. HWiNFO shared memory (per-P-core/E-core clocks on hybrid CPUs)
2. LibreHardwareMonitor WMI (`root\LibreHardwareMonitor`)
3. Python libraries (psutil)

**GPU FPS** comes from RTSS shared memory (`RTSSSharedMemoryV2`), which is the most reliable way to get per-game FPS on any GPU vendor (NVIDIA, AMD, Intel). RTSS hooks into any DirectX/OpenGL/Vulkan game and reports real-time framerate.

**New config option in `config.yaml`:**
```yaml
# - HWINFO  use HWiNFO for CPU sensors + RTSS for GPU FPS (Windows only), fallback to LHM WMI / Python libs
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
