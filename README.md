# Turing Smart Screen - Python System Monitor (RTSS FPS + Suspend/Resume Fork)

Fork optimizado del proyecto original [mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) con soporte de FPS via RTSS y manejo de suspensión/reanudación del sistema.

## Cambios respecto al original

### 1. RTSS FPS en modo LHM

El módulo `sensors_librehardwaremonitor.py` ahora lee FPS desde **RTSS (RivaTuner Statistics Server)** como fuente principal. Si RTSS no está disponible, vuelve al sensor FPS nativo de LHM.

- Sin archivos nuevos, sin opciones de configuración nuevas
- Usa `HW_SENSORS: LHM` o `AUTO` como siempre
- Funciona con cualquier GPU (NVIDIA, AMD, Intel)
- RTSS hookea DirectX/OpenGL/Vulkan y reporta el framerate real

### 2. Suspend/Resume y Session Lock (`power_handler.py`)

Proceso independiente que gestiona el monitor del sistema:

- **Suspender/Reanudar** — detiene el monitor antes de dormir, lo rearranca al despertar
- **Bloqueo de sesión** — detiene el monitor al bloquear (Win+L), lo rearranca al desbloquear
- **Apagado del sistema** — parada limpia via archivo `.shutdown_signal`

`main.py` comprueba `.shutdown_signal` en cada iteración del bucle principal para salir limpiamente.

## Requisitos

1. Python 3.9+ en Windows
2. Ejecutar como administrador (requerido por LHM)
3. RTSS corriendo en segundo plano (viene con MSI Afterburner) para FPS en juegos
4. Pantalla USB-C compatible (Turing Smart Screen, TURZX, XuanFang, etc.)

## Instalación

```bash
pip install -r requirements.txt
python main.py
```

Para ejecución automática con manejo de suspensión:

```bash
python power_handler.py
```

## Configuración (`config.yaml`)

```yaml
HW_SENSORS: LHM      # Usa LHM + RTSS FPS (Windows, requiere admin)
# HW_SENSORS: AUTO   # Equivalente a LHM en Windows, Python en Linux/Mac
```
