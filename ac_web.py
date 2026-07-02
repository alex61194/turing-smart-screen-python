#!/usr/bin/env python
"""AC Midea Web Control - interfaz web para controlar el aire acondicionado via msmart-ng.

Seguridad:
  - Todas las mutaciones (power/mode/temp/fan) se hacen por POST (CSRF-safe).
  - Acceso protegido por token Bearer (variable de entorno AC_WEB_TOKEN).
    Si la variable no está definida, el servidor se niega a arrancar.
  - El bind por defecto es 127.0.0.1 (solo localhost). Para exponerlo a la LAN
    o a un tunel, define AC_WEB_HOST=0.0.0.0 — pero SIEMPRE con un token.
Credenciales del AC:
  - Se leen de library/midea_ac_credentials.json por defecto, o de variables de
    entorno (AC_IP, AC_PORT, AC_DEVICE_ID, AC_TOKEN, AC_KEY) si se prefieren.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import secrets
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from msmart.device import AirConditioner

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger("ac_web")

BASE_DIR = Path(__file__).resolve().parent
CREDS_PATH = BASE_DIR / "library" / "midea_ac_credentials.json"
TEMPLATE_PATH = BASE_DIR / "templates" / "ac_index.html"

# --- Authentication ---------------------------------------------------------
# The token authorizes every API call. MUST be set via env var to start.
AUTH_TOKEN = os.environ.get("AC_WEB_TOKEN")
if not AUTH_TOKEN:
    _LOGGER.error(
        "AC_WEB_TOKEN no definido. Genera uno con `python -c \"import secrets; print(secrets.token_urlsafe(24))\"` "
        "y exportalo antes de arrancar. El servidor no iniciará sin token."
    )

_security = HTTPBearer(auto_error=False)


def verify_token(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> str:
    """Valida el token Bearer en cada peticion. Aplica a TODOS los endpoints."""
    if not AUTH_TOKEN:
        raise HTTPException(status_code=503, detail="Servidor sin token configurado")
    provided = creds.credentials if creds else None
    # secrets.compare_digest evata timing attacks y nunca lanza con None.
    if not provided or not secrets.compare_digest(provided, AUTH_TOKEN):
        raise HTTPException(status_code=401, detail="Token invalido o ausente")
    return AUTH_TOKEN


app = FastAPI(title="AC Midea Control", dependencies=[Depends(verify_token)])

_device = None
_device_lock = None  # asyncio.Lock se crea en startup (necesita loop)

MODE_NAMES = {
    1: "AUTO", 2: "FRÍO", 3: "SECO",
    4: "CALOR", 5: "VENT", 6: "S.DRY",
}
MODE_VALUES = {v: k for k, v in MODE_NAMES.items()}

FAN_NAMES = {
    20: "SILEN", 40: "BAJO", 60: "MEDIO",
    80: "ALTO", 100: "MÁX", 102: "AUTO",
}


def _load_creds() -> dict:
    """Carga credenciales del AC: primero variables de entorno, luego JSON."""
    env = {k: os.environ.get(k) for k in ("AC_IP", "AC_PORT", "AC_DEVICE_ID", "AC_TOKEN", "AC_KEY")}
    if all(env.values()):
        _LOGGER.info("Credenciales AC cargadas desde variables de entorno")
        return {
            "ip": env["AC_IP"],
            "port": int(env["AC_PORT"]),
            "device_id": int(env["AC_DEVICE_ID"]),
            "token": env["AC_TOKEN"],
            "key": env["AC_KEY"],
        }
    try:
        with open(CREDS_PATH) as f:
            _LOGGER.info("Credenciales AC cargadas desde %s", CREDS_PATH)
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(
            f"No se encontraron credenciales del AC. Definelas por variables de entorno "
            f"(AC_IP, AC_PORT, AC_DEVICE_ID, AC_TOKEN, AC_KEY) o crea {CREDS_PATH}"
        )


@app.on_event("startup")
async def _startup():
    global _device_lock
    import asyncio
    _device_lock = asyncio.Lock()


async def _get_device() -> AirConditioner:
    global _device
    async with _device_lock:
        if _device is None:
            creds = _load_creds()
            _device = AirConditioner(
                ip=creds["ip"],
                device_id=creds["device_id"],
                port=creds["port"],
            )
            await _device.authenticate(token=creds["token"], key=creds["key"])
            _device.enable_energy_usage_requests = True
            _LOGGER.info("AC autenticado")
        return _device


async def _refresh():
    dev = await _get_device()
    async with _device_lock:
        await dev.refresh()
    return dev


async def _apply():
    dev = await _get_device()
    async with _device_lock:
        await dev.apply()


def _status_dict(dev):
    return {
        "power": dev.power_state,
        "mode": MODE_NAMES.get(dev.operational_mode.value, str(dev.operational_mode.name)),
        "mode_code": dev.operational_mode.value,
        "target_temp": dev.target_temperature,
        "indoor_temp": dev.indoor_temperature,
        "outdoor_temp": dev.outdoor_temperature,
        "fan_speed": FAN_NAMES.get(dev.fan_speed if isinstance(dev.fan_speed, int) else dev.fan_speed.value, str(dev.fan_speed)),
        "fan_speed_code": dev.fan_speed if isinstance(dev.fan_speed, int) else dev.fan_speed.value,
        "eco": dev.eco,
        "turbo": dev.turbo,
        "swing": dev.swing_mode.name,
        "error": dev.error_code,
        "display_on": dev.display_on,
        "total_energy": dev.get_total_energy_usage(),
        "current_energy": dev.get_current_energy_usage(),
        "real_time_power": dev.get_real_time_power_usage(),
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    """Devuelve la UI. El JS pide el token al usuario y lo envia como Bearer."""
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))


@app.get("/api/status")
async def api_status():
    try:
        dev = await _refresh()
        return {"status": _status_dict(dev)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/power")
async def api_power(on: bool = Query(...)):
    try:
        dev = await _get_device()
        dev.power_state = on
        await _apply()
        await dev.refresh()
        return {"status": _status_dict(dev)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/mode")
async def api_mode(mode: str = Query(...)):
    try:
        code = MODE_VALUES.get(mode.upper())
        if code is None:
            return {"error": f"Modo invalido: {mode}"}
        dev = await _get_device()
        dev.operational_mode = AirConditioner.OperationalMode(code)
        await _apply()
        await dev.refresh()
        return {"status": _status_dict(dev)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/temp")
async def api_temp(temp: float = Query(...)):
    try:
        if temp < 16 or temp > 30:
            return {"error": "Temperatura fuera de rango (16-30)"}
        dev = await _get_device()
        dev.target_temperature = temp
        await _apply()
        await dev.refresh()
        return {"status": _status_dict(dev)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/fan")
async def api_fan(speed: int = Query(...)):
    try:
        valid = [20, 40, 60, 80, 100, 102]
        if speed not in valid:
            return {"error": f"Velocidad invalida: {speed}"}
        dev = await _get_device()
        dev.fan_speed = speed
        await _apply()
        await dev.refresh()
        return {"status": _status_dict(dev)}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    if not AUTH_TOKEN:
        raise SystemExit(
            "AC_WEB_TOKEN no definido. Genera uno con:\n"
            '  python -c "import secrets; print(secrets.token_urlsafe(24))"\n'
            "y exportalo antes de arrancar."
        )
    host = os.environ.get("AC_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("AC_WEB_PORT", "8080"))
    print("=== AC Midea Web Control ===")
    print(f"Escuchando en http://{host}:{port} (requiere token Bearer)")
    uvicorn.run(app, host=host, port=port)
