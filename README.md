# Turing Smart Screen - Python System Monitor (Fork ampliado)

Fork del proyecto [mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) con sensor MSI Afterburner (MAHM), control de AC Midea, monitor solar FusionSolar (Huawei), auto-switch GamingOverlay, temas nuevos y más.

Ejecutable en **Windows sin administrador** gracias a MAHM.

## Diferencias principales respecto al original

### Sensores
- **MAHM (MSI Afterburner)** como backend por defecto (`HW_SENSORS: AUTO` en Windows) — no requiere privilegios de administrador, a diferencia de LHM. Afterburner debe estar corriendo
- **VRAM**: lee MB usados, total y porcentaje (como RAM), con lookup table para GPUs conocidas
- **GPU Power**: lectura desde MAHM, con manejo de NaN y umbral de 20W
- **CPU/GPU Clock**: frecuencias desde MAHM

### AC Midea (`sensors_custom.py`)
- Control local por LAN vía `msmart-ng` (sin cloud)
- Sensores: temperatura interior/exterior, modo (FRÍO/CALOR/VENTILADOR...), fan speed (SILENCIOSO/BAJA/MEDIA/ALTA/MÁX/AUTO), ECO, TURBO, error
- **Potencia derivada**: el modelo EU-OSK105/ELUXE Amber 2 no reporta `real_time_power` por LAN (siempre 0). El fork calcula los W a partir del contador `total_energy` (saltos de 0.01 kWh) usando un **ring buffer de 3 ticks** para suavizar el efecto escalera
- **Refresh cada 10s** (original: 30s)
- Control web via FastAPI con token Bearer (`ac_web.py`)

### FusionSolar (`sensors_custom.py`)
- Scraping de la web FusionSolar con Playwright (headless)
- Sensores: generación (W), consumo (W), excedente (W), producción hoy/total, ahorro/gasto €/h
- Precios configurables: `SURPLUS_PRICE` (0.06€/kWh exportado), `GRID_PRICE` (0.13€/kWh importado)
- Label dinámico: "AHORRO" (excedente ≥ 0) / "GASTO" (excedente < 0, número en rojo)

### Temas nuevos
| Tema | Descripción |
|---|---|
| `RoomStatus` | Panel AC web style con paleta Dracula, bandas card oscuras. Muestra AC, solar, GPU, CPU, RAM, VRAM, FPS |
| `GamingOverlay` | Overlay para juegos con FPS, GPU, VRAM, CPU, RAM. Layout rework: font Regular, tamaños reducidos, reposicionado |
| `Cyberdeck` | Tema cyberdeck con power, FPS y todos los sensores |
| `CyberDecimorLandscape` | Landscape 480×320 |
| `EVA-01` | Tema NERV terminal |
| `TaskManager` | FPS reemplaza disk, power info |

### Auto-switch GamingOverlay (`main.py`)
Cuando RTSS reporta FPS > 0, cambia automáticamente al tema `GamingOverlay`. Al dejar de detectar juego, vuelve al tema original. Protegido con lock para evitar lecturas a medias del scheduler.

### Suspend/Resume y Session Lock (`power_handler.py`)
Proceso independiente que gestiona suspender/reanudar, bloqueo de sesión (Win+L) y apagado del sistema.

### Línea gráfica (line graph)
Soporte para fill y antialias en gráficos de línea (PR #946).

## Requisitos
1. Python 3.12+ en Windows
2. MSI Afterburner corriendo (para sensores MAHM y FPS vía RTSS)
3. Pantalla USB-C compatible (Turing Smart Screen 3.5", revisión A)
4. Solo si usas AC Midea: `msmart-ng`
5. Solo si usas FusionSolar: Playwright (`playwright install chromium`)

## Instalación

```bash
pip install -r requirements.txt
# Solo si usas monitor solar FusionSolar:
playwright install chromium
```

Copia `config.yaml.example` a `config.yaml` y ajusta valores.

## Uso

```bash
# Monitor principal (sin administrador gracias a MAHM)
python main.py

# Con manejo de suspensión/bloqueo de sesión
python power_handler.py
```

### Control web del AC

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
$env:AC_WEB_TOKEN = "<el-token>"
python ac_web.py
# Abre http://localhost:8080
```

## Credenciales y secretos

| Integración | Variables de entorno | Alternativa (JSON) |
|---|---|---|
| AC Midea | `AC_IP`, `AC_PORT`, `AC_DEVICE_ID`, `AC_TOKEN`, `AC_KEY` | `library/midea_ac_credentials.json` |
| FusionSolar | `FUSIONSOLAR_USER`, `FUSIONSOLAR_PASS` | `library/fusionsolar_credentials.json` |
| AC Web | `AC_WEB_TOKEN`, `AC_WEB_HOST`, `AC_WEB_PORT` | — |

## Estructura del fork

```
main.py                 # Monitor + auto-switch GamingOverlay
power_handler.py        # Supervisor: suspend/resume/lock/shutdown
ac_web.py               # API web del AC (FastAPI, auth Bearer)
templates/ac_index.html # UI del control web del AC
library/
  sensors_custom.py     # Sensores: Midea AC + FusionSolar
  sensors_mahm.py       # Backend MAHM (MSI Afterburner)
  sensors_rtss.py       # Lectura FPS vía RTSS shared memory
  stats.py              # Renderizado con colores condicionales
  scheduler.py          # Planificador de sensores
```
