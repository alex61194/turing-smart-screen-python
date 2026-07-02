# Turing Smart Screen - Python System Monitor (Fork ampliado)

Fork optimizado del proyecto original [mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) con varias integraciones extra: **FPS vía RTSS**, **control de aire acondicionado Midea**, **monitor de energía solar FusionSolar (Huawei)**, **auto-switch de tema GamingOverlay** y manejo de **suspensión/reanudación/bloqueo de sesión**.

## Características añadidas respecto al original

### 1. RTSS FPS en modo LHM
`sensors_librehardwaremonitor.py` lee FPS desde **RTSS (RivaTuner Statistics Server)** como fuente principal; si RTSS no está disponible, vuelve al sensor FPS nativo de LHM. Funciona con cualquier GPU (NVIDIA, AMD, Intel).

### 2. Auto-switch de tema GamingOverlay (`main.py`)
Cuando RTSS reporta FPS > 0 durante unas iteraciones, el tema cambia automáticamente a `GamingOverlay`. Al dejar de detectar juego, vuelve al tema original. El cambio está protegido por un lock para evitar lecturas a medias del scheduler.

### 3. Suspend/Resume y Session Lock (`power_handler.py`)
Proceso independiente que gestiona el ciclo de vida del monitor:
- **Suspender/Reanudar** — detiene el monitor antes de dormir, lo rearranca al despertar
- **Bloqueo de sesión** — detiene el monitor al bloquear (Win+L), lo rearranca al desbloquear
- **Apagado del sistema** — parada limpia vía archivo `.shutdown_signal`

### 4. Control de AC Midea (`ac_web.py`)
Interfaz web (FastAPI) para controlar un aire acondicionado Midea por LAN mediante `msmart-ng`, con control por voz (Web Speech API) en español.
- **Seguridad**: requiere token Bearer (`AC_WEB_TOKEN`); todas las mutaciones son POST (CSRF-safe)
- **Bind**: por defecto `127.0.0.1:8080`. Exponerlo a Internet (túnel) **solo** con token

### 5. Monitor solar FusionSolar (`sensors_custom.py`)
Lee generación/consumo/excedentes de un inversor Huawei SUN2000 vía la web de FusionSolar con Playwright (headless). Habilita los sensores `SolarGeneration`, `SolarSurplus`, `SolarMoney`, etc.

## Requisitos
1. Python 3.9+ en Windows
2. Ejecutar como administrador (requerido por LHM)
3. RTSS corriendo en segundo plano (viene con MSI Afterburner) para FPS en juegos
4. Pantalla USB-C compatible (Turing Smart Screen, TURZX, XuanFang, etc.)

## Instalación

```bash
pip install -r requirements.txt
# Solo si usas el monitor solar FusionSolar:
playwright install chromium
```

Copia `config.yaml.example` a `config.yaml` y ajusta tus valores (puerto COM, tema, interfaces de red, etc.).

## Uso

```bash
# Monitor principal
python main.py

# Con manejo de suspensión/bloqueo de sesión
python power_handler.py
```

### Control web del AC

```bash
# Genera un token y expórtalo
python -c "import secrets; print(secrets.token_urlsafe(24))"
# En PowerShell:  $env:AC_WEB_TOKEN = "<el-token>"
# En bash:        export AC_WEB_TOKEN="<el-token>"

python ac_web.py
# Abre http://localhost:8080  (pedirá el token en el navegador)
```

Para acceso remoto a través de un túnel (`start_tunnel.py` / `run_tunnel.py`), define `AC_WEB_HOST=0.0.0.0` — siempre con un token.

## Credenciales y secretos

Las credenciales del AC y de FusionSolar **nunca deben commitearse**. Están en `.gitignore`. Cárgalas de una de estas dos formas:

| Integración | Variables de entorno | Alternativa (JSON, no commitear) |
|---|---|---|
| AC Midea | `AC_IP`, `AC_PORT`, `AC_DEVICE_ID`, `AC_TOKEN`, `AC_KEY` | `library/midea_ac_credentials.json` |
| FusionSolar | `FUSIONSOLAR_USER`, `FUSIONSOLAR_PASS` | `library/fusionsolar_credentials.json` |
| AC Web | `AC_WEB_TOKEN`, `AC_WEB_HOST`, `AC_WEB_PORT` | — |

**Recomendado**: variables de entorno (los JSON quedan como fallback para desarrollo).

## Configuración (`config.yaml`)

```yaml
config:
  HW_SENSORS: AUTO    # LHM + RTSS FPS en Windows
  THEME: RoomStatus   # carpeta de res/themes/
```
Consulta `config.yaml.example` para ver todas las opciones.

## Estructura del fork

```
main.py                 # Monitor + auto-switch GamingOverlay (loop de Windows)
power_handler.py        # Supervisor: suspend/resume/lock/shutdown
ac_web.py               # API web del AC (FastAPI, auth Bearer)
templates/ac_index.html # UI del control web del AC
library/
  sensors_custom.py     # Sensores personalizados: Midea AC + FusionSolar
  rtss_osd.py           # Lectura de FPS/OSD vía RTSS shared memory
  log.py                # Logging con rotación
```
