# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# This file allows to add custom data source as sensors and display them in System Monitor themes
# There is no limitation on how much custom data source classes can be added to this file
# See CustomDataExample theme for the theme implementation part

import math
import platform
from abc import ABC, abstractmethod
from typing import List
from urllib.parse import parse_qs, urlparse


# Custom data classes must be implemented in this file, inherit the CustomDataSource and implement its 2 methods
class CustomDataSource(ABC):
    @abstractmethod
    def as_numeric(self) -> float:
        # Numeric value will be used for graph and radial progress bars
        # If there is no numeric value, keep this function empty
        pass

    @abstractmethod
    def as_string(self) -> str:
        # Text value will be used for text display and radial progress bar inner text
        # Numeric value can be formatted here to be displayed as expected
        # It is also possible to return a text unrelated to the numeric value
        # If this function is empty, the numeric value will be used as string without formatting
        pass

    @abstractmethod
    def last_values(self) -> List[float]:
        # List of last numeric values will be used for plot graph
        # If you do not want to draw a line graph or if your custom data has no numeric values, keep this function empty
        pass


# Example for a custom data class that has numeric and text values
class ExampleCustomNumericData(CustomDataSource):
    # This list is used to store the last 10 values to display a line graph
    last_val = [math.nan] * 10  # By default, it is filed with math.nan values to indicate there is no data stored

    def as_numeric(self) -> float:
        # Numeric value will be used for graph and radial progress bars
        # Here a Python function from another module can be called to get data
        # Example: self.value = my_module.get_rgb_led_brightness() / audio.system_volume() ...
        self.value = 75.845

        # Store the value to the history list that will be used for line graph
        self.last_val.append(self.value)
        # Also remove the oldest value from history list
        self.last_val.pop(0)

        return self.value

    def as_string(self) -> str:
        # Text value will be used for text display and radial progress bar inner text.
        # Numeric value can be formatted here to be displayed as expected
        # It is also possible to return a text unrelated to the numeric value
        # If this function is empty, the numeric value will be used as string without formatting
        # Example here: format numeric value: add unit as a suffix, and keep 1 digit decimal precision
        return f'{self.value:>5.1f}%'
        # Important note! If your numeric value can vary in size, be sure to display it with a default size.
        # E.g. if your value can range from 0 to 9999, you need to display it with at least 4 characters every time.
        # --> return f'{self.as_numeric():>4}%'
        # Otherwise, part of the previous value can stay displayed ("ghosting") after a refresh

    def last_values(self) -> List[float]:
        # List of last numeric values will be used for plot graph
        return self.last_val


# Example for a custom data class that only has text values
class ExampleCustomTextOnlyData(CustomDataSource):
    def as_numeric(self) -> float:
        # If there is no numeric value, keep this function empty
        pass

    def as_string(self) -> str:
        # If a custom data class only has text values, it won't be possible to display graph or radial bars
        return "Python: " + platform.python_version()

    def last_values(self) -> List[float]:
        # If a custom data class only has text values, it won't be possible to display line graph
        pass


# ---------------------------------------------------------------------------
# Midea AC Integration via msmart-ng
# ---------------------------------------------------------------------------
# Runs a background thread with asyncio event loop to periodically refresh
# AC data over LAN. Saved token/key used for local-only auth (no cloud login).
# ---------------------------------------------------------------------------

import asyncio
import json
import logging
import os
import threading

_AC_LOGGER = logging.getLogger(__name__)

_CREDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "midea_ac_credentials.json")


def _load_midea_creds() -> dict:
    """Carga credenciales del AC: variables de entorno primero, luego JSON.

    Prioriza AC_IP/AC_PORT/AC_DEVICE_ID/AC_TOKEN/AC_KEY; si faltan, usa el JSON.
    Asi se puede evitar dejar secretos en disco (y el JSON queda solo para dev).
    """
    env = {k: os.environ.get(k)
           for k in ("AC_IP", "AC_PORT", "AC_DEVICE_ID", "AC_TOKEN", "AC_KEY")}
    if all(env.values()):
        _AC_LOGGER.info("Midea AC: credenciales desde variables de entorno")
        return {
            "ip": env["AC_IP"],
            "port": int(env["AC_PORT"]),
            "device_id": int(env["AC_DEVICE_ID"]),
            "token": env["AC_TOKEN"],
            "key": env["AC_KEY"],
        }
    try:
        with open(_CREDS_PATH) as f:
            _AC_LOGGER.info("Midea AC: credenciales desde %s", _CREDS_PATH)
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}  # manejado por el llamador


class _MideaACMonitor:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._loop = None
        self._thread = None
        self._running = False

        self._cache = {
            "power_state": False,
            "indoor_temperature": None,
            "outdoor_temperature": None,
            "target_temperature": None,
            "operational_mode": None,
            "fan_speed": None,
            "eco": False,
            "turbo": False,
            "error_code": 0,
            "total_energy": None,
            "current_energy": None,
            "real_time_power": None,
            # Potencia instantanea calculada a partir del contador acumulado.
            # Muchos splits Midea no exponen real_time_power por LAN, asi que
            # derivamos los W midiendo cuánto sube total_energy entre lecturas.
            "derived_power_w": 0.0,
        }
        self._cache_lock = threading.Lock()
        self._ready = threading.Event()
        # Estado para el calculo de potencia derivada.
        self._prev_total_energy = None
        self._prev_energy_ts = None
        self._accum_ts = None
        self._power_w = 0.0
        self._zero_since = None  # timestamp: desde cuando el AC lleva en 0 W

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _update_cache(self, device):
        import time as _time
        with self._cache_lock:
            power_on = device.power_state
            self._cache["power_state"] = power_on
            self._cache["indoor_temperature"] = device.indoor_temperature
            self._cache["outdoor_temperature"] = device.outdoor_temperature
            self._cache["target_temperature"] = device.target_temperature
            self._cache["operational_mode"] = device.operational_mode
            self._cache["fan_speed"] = device.fan_speed
            self._cache["eco"] = device.eco
            self._cache["turbo"] = device.turbo
            self._cache["error_code"] = device.error_code
            total = device.get_total_energy_usage()
            self._cache["total_energy"] = total
            self._cache["current_energy"] = device.get_current_energy_usage()
            self._cache["real_time_power"] = device.get_real_time_power_usage()

            # --- Potencia derivada (W) a partir del contador acumulado ---
            # El contador del AC avanza en saltos discretos (~10 Wh), asi que
            # usamos una ventana deslizante: acumulamos tiempo/energia hasta el
            # proximo salto del contador, calculamos la media, y repetimos.
            now = _time.time()
            if not power_on:
                self._cache["derived_power_w"] = 0.0
                self._power_w = 0.0
                self._zero_since = now
                self._prev_total_energy = total
                self._prev_energy_ts = now
                self._accum_ts = None
            else:
                # AC encendido: al primer refresh tras encendido, inicializamos.
                if self._accum_ts is None:
                    self._accum_ts = now
                    self._prev_total_energy = total
                    self._prev_energy_ts = now
                    # Si habia un valor previo valido, lo mostramos mientras
                    # el contador arranca; si no, 0 es correcto.
                    self._cache["derived_power_w"] = self._power_w

                # Incremento del contador desde la lectura anterior.
                if total is not None and self._prev_total_energy is not None:
                    delta = total - self._prev_total_energy
                    if delta > 0:
                        # El contador salto: calcular potencia media de esta
                        # ventana y reiniciar.
                        window_dt = now - self._accum_ts
                        if window_dt > 0:
                            self._power_w = max(0.0, round(
                                delta * 3600.0 * 1000.0 / window_dt))
                            self._cache["derived_power_w"] = self._power_w
                            self._zero_since = None  # hay consumo
                        self._accum_ts = now
                    else:
                        # delta == 0: el contador aun no avanzo. Si llevamos mas de
                        # 90 s sin consumo, forzamos 0 (compresor parado por termostato).
                        if (self._zero_since is None
                                and self._power_w > 0
                                and (now - self._accum_ts) > 90):
                            self._power_w = 0.0
                            self._cache["derived_power_w"] = 0.0
                            self._zero_since = now
                            # Reiniciar tambien el inicio de la ventana: si no,
                            # la proxima vez que el contador avance, window_dt
                            # incluira todo este tiempo inactivo y diluira el
                            # calculo, mostrando una potencia artificialmente
                            # baja en el primer salto tras la inactividad.
                            self._accum_ts = now

                self._prev_total_energy = total
                self._prev_energy_ts = now

    def get(self, key):
        with self._cache_lock:
            return self._cache.get(key)

    async def _refresh_loop(self):
        try:
            from msmart.device import AirConditioner
        except ImportError as e:
            _AC_LOGGER.error("msmart library not installed: %s", e)
            self._ready.set()
            return

        creds = _load_midea_creds()
        if not creds or not all(creds.get(k) for k in ("ip", "port", "device_id", "token", "key")):
            _AC_LOGGER.error("Midea AC credentials not found (define env vars "
                             "AC_IP/AC_PORT/AC_DEVICE_ID/AC_TOKEN/AC_KEY or create %s)", _CREDS_PATH)
            self._ready.set()
            return

        device = AirConditioner(
            ip=creds["ip"],
            device_id=creds["device_id"],
            port=creds["port"],
        )

        try:
            await device.authenticate(token=creds["token"], key=creds["key"])
            device.enable_energy_usage_requests = True
            await device.refresh()
            self._update_cache(device)
            self._ready.set()
            _AC_LOGGER.info("Midea AC authenticated: indoor=%.1fC, total=%.1fkWh",
                            device.indoor_temperature,
                            device.get_total_energy_usage() or 0)
        except Exception as e:
            _AC_LOGGER.error("Midea AC auth failed: %s", e)
            self._ready.set()
            return

        while self._running:
            try:
                await device.refresh()
                self._update_cache(device)
            except Exception as e:
                _AC_LOGGER.warning("Midea AC refresh error: %s", e)

            await asyncio.sleep(30)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._refresh_loop())

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def ready(self):
        return self._ready.is_set()


class _MideaACBase(CustomDataSource):
    _monitor_started = False

    def __init__(self):
        super().__init__()
        if not _MideaACBase._monitor_started:
            monitor = _MideaACMonitor.get_instance()
            monitor.start()
            _MideaACBase._monitor_started = True

    @property
    def _monitor(self):
        return _MideaACMonitor.get_instance()

    def last_values(self) -> List[float]:
        pass


class MideaACIndoorTemp(_MideaACBase):
    def as_numeric(self) -> float:
        return self._monitor.get("indoor_temperature") or 0.0

    def as_string(self) -> str:
        val = self._monitor.get("indoor_temperature")
        if val is None:
            return "--°C"
        return f"{val:.0f}°C"


class MideaACOutdoorTemp(_MideaACBase):
    def as_numeric(self) -> float:
        val = self._monitor.get("outdoor_temperature")
        return float(val) if val is not None else 0.0

    def as_string(self) -> str:
        val = self._monitor.get("outdoor_temperature")
        if val is None:
            return "--°C"
        return f"{val:.0f}°C"

class MideaACTargetTemp(_MideaACBase):
    def as_numeric(self) -> float:
        return self._monitor.get("target_temperature") or 0.0

    def as_string(self) -> str:
        val = self._monitor.get("target_temperature")
        if val is None:
            return "--°C"
        return f"{val:.0f}°C"


class MideaACMode(_MideaACBase):
    _MODE_NAMES = {
        1: "AUTO", 2: "FRÍO", 3: "SECO",
        4: "CALOR", 5: "VENT", 6: "S.DRY",
    }

    def as_numeric(self) -> float:
        val = self._monitor.get("operational_mode")
        return float(val.value) if val else 0.0

    def as_string(self) -> str:
        val = self._monitor.get("operational_mode")
        if val is None:
            return "--"
        return self._MODE_NAMES.get(val.value, str(val.name))


class MideaACPower(_MideaACBase):
    def as_numeric(self) -> float:
        return 1.0 if self._monitor.get("power_state") else 0.0

    def as_string(self) -> str:
        return "ENCENDIDO" if self._monitor.get("power_state") else "APAGADO"


class MideaACFanSpeed(_MideaACBase):
    _FAN_NAMES = {
        0: "AUTO", 1: "BAJA", 2: "MEDIA",
        3: "ALTA", 4: "MÁX",
    }

    def as_numeric(self) -> float:
        val = self._monitor.get("fan_speed")
        return float(val.value) if val else 0.0

    def as_string(self) -> str:
        val = self._monitor.get("fan_speed")
        if val is None:
            return "--"
        return self._FAN_NAMES.get(val.value, str(val.name))


class MideaACEco(_MideaACBase):
    def as_numeric(self) -> float:
        return 1.0 if self._monitor.get("eco") else 0.0

    def as_string(self) -> str:
        # Usamos el espacio ideográfico completo de ancho fijo que genera altura limpia e invisible
        return "ECO" if self._monitor.get("eco") else "\u3000"


class MideaACTurbo(_MideaACBase):
    def as_numeric(self) -> float:
        return 1.0 if self._monitor.get("turbo") else 0.0

    def as_string(self) -> str:
        # Usamos el espacio ideográfico completo de ancho fijo que genera altura limpia e invisible
        return "TURBO" if self._monitor.get("turbo") else "\u3000"


class MideaACTotalEnergy(_MideaACBase):
    def as_numeric(self) -> float:
        return self._monitor.get("total_energy") or 0.0

    def as_string(self) -> str:
        val = self._monitor.get("total_energy")
        if val is None:
            return "-- kWh"
        return f"{val:.1f} kWh"


class MideaACCurrentEnergy(_MideaACBase):
    def as_numeric(self) -> float:
        return self._monitor.get("current_energy") or 0.0

    def as_string(self) -> str:
        val = self._monitor.get("current_energy")
        if val is None:
            return "-- kWh"
        return f"{val:.1f} kWh"


class MideaACRealTimePower(_MideaACBase):
    """Potencia instantanea del AC en W.

    Este modelo de AC no expone potencia en tiempo real por LAN
    (get_real_time_power_usage() siempre devuelve 0). La calculamos a partir
    de cuánto avanza el contador acumulado (total_energy_usage) entre dos
    lecturas del monitor, que se actualiza cada ~30 s.
    """

    def as_numeric(self) -> float:
        # Preferimos la lectura nativa si el AC la soporta (distinta de 0);
        # si no, usamos la potencia derivada del contador.
        native = self._monitor.get("real_time_power")
        if native:
            return float(native)
        return float(self._monitor.get("derived_power_w") or 0.0)

    def as_string(self) -> str:
        w = self.as_numeric()
        if w <= 0:
            return "0 W"
        if w < 1000:
            return f"{w:.0f} W"
        return f"{w / 1000:.2f} kW"


# ---------------------------------------------------------------------------
# FusionSolar (Huawei SUN2000) Integration via internal REST API
# ---------------------------------------------------------------------------
_FUSION_CREDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "fusionsolar_credentials.json")


def _load_fusion_creds() -> dict:
    """Carga credenciales de FusionSolar: variables de entorno primero, luego JSON.

    Variables: FUSIONSOLAR_USER y FUSIONSOLAR_PASS. Si faltan, usa el JSON.
    """
    user = os.environ.get("FUSIONSOLAR_USER")
    password = os.environ.get("FUSIONSOLAR_PASS")
    if user and password:
        _AC_LOGGER.info("FusionSolar: credenciales desde variables de entorno")
        return {"username": user, "password": password}
    try:
        with open(_FUSION_CREDS_PATH) as f:
            _AC_LOGGER.info("FusionSolar: credenciales desde %s", _FUSION_CREDS_PATH)
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class _FusionSolarMonitor:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._running = False
        self._cache = {
            "generation_w": 0,
            "generation_today_kwh": 0,
            "generation_total_kwh": 0,
            "consumption_today_kwh": 0,
            "consumption_w": 0,
            "surplus_w": 0,
        }
        self._cache_lock = threading.Lock()
        self._ready = threading.Event()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get(self, key):
        with self._cache_lock:
            return self._cache.get(key)

    def _run(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            _AC_LOGGER.error("playwright not installed")
            self._ready.set()
            return

        creds = _load_fusion_creds()
        if not creds:
            _AC_LOGGER.warning("FusionSolar credentials not found (define env vars "
                               "FUSIONSOLAR_USER/FUSIONSOLAR_PASS o crea %s)", _FUSION_CREDS_PATH)
            self._ready.set()
            return

        username = creds.get("username", "")
        password = creds.get("password", "")
        if not username or not password:
            _AC_LOGGER.error("FusionSolar credentials incomplete")
            self._ready.set()
            return

        _AC_LOGGER.info("Starting FusionSolar monitor...")

        while self._running:
            browser = None
            pw = None
            try:
                pw = sync_playwright().start()
                # Ocultamos rastro de automatización básico pasando un User-Agent común
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800}, 
                    locale="es-ES",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                station_dn = None

                def _capture_dn(response):
                    nonlocal station_dn
                    if 'station-real-kpi' in response.url and station_dn is None:
                        from urllib.parse import urlparse, parse_qs
                        parsed = urlparse(response.url)
                        params = parse_qs(parsed.query)
                        dn = params.get('stationDn', [None])[0]
                        if dn:
                            station_dn = dn
                            _AC_LOGGER.info("FusionSolar station DN: %s", station_dn)

                page.on("response", _capture_dn)

                # Ir a la web e iniciar sesión
                page.goto("https://eu5.fusionsolar.huawei.com", timeout=45000)
                page.wait_for_load_state("networkidle", timeout=20000)

                inputs = page.locator("input.right_name_textfield").all()
                if len(inputs) < 2:
                    raise Exception("No se encontraron los campos de Login en el portal")
                    
                inputs[0].fill(username)
                inputs[1].fill(password)
                page.wait_for_timeout(1000)
                page.locator("div.loginBtn:has-text('Iniciar sesión')").first.click()
                page.wait_for_timeout(12000)
                page.wait_for_load_state("networkidle", timeout=25000)

                if "login" in page.url.lower():
                    _AC_LOGGER.error("FusionSolar login fallido en credenciales")
                    self._ready.set()
                    break # Detener si las credenciales son erróneas

                _AC_LOGGER.info("FusionSolar login exitoso, obteniendo estación...")
                page.wait_for_timeout(8000)

                if not station_dn:
                    try:
                        sl = page.evaluate("""
                            async () => {
                                const r = await fetch(
                                    '/rest/pvms/web/station/v1/station/station-list',
                                    { credentials: 'include' }
                                );
                                return await r.json();
                            }
                        """)
                        if sl and sl.get("data") and sl["data"].get("list"):
                            station_dn = sl["data"]["list"][0]["dn"]
                            _AC_LOGGER.info("FusionSolar station DN (list): %s", station_dn)
                    except Exception as e:
                        _AC_LOGGER.warning("station-list API falló de inicio: %s", e)

                # Si logramos autenticar la primera vez, el monitor está listo para entregar datos antiguos/caché
                self._ready.set()

                # Bucle de consulta interno (mantenimiento de sesión viva)
                # Durará hasta que ocurra un fallo de fetch o desconexión, forzando un ciclo limpio
                while self._running:
                    if not station_dn:
                        _AC_LOGGER.warning("Esperando Station DN válido... reintentando sesión completa.")
                        break

                    # Consulta 1: KPI Principal
                    resp = page.evaluate("""
                        async (dn) => {
                            const r = await fetch(
                                '/rest/pvms/web/station/v1/overview/station-real-kpi?stationDn='
                                + encodeURIComponent(dn) + '&_=' + Date.now(),
                                { credentials: 'include' }
                            );
                            return await r.json();
                        }
                    """, station_dn)

                    if resp and resp.get("success") and resp.get("data"):
                        data = resp["data"]
                        with self._cache_lock:
                            kw = float(data.get("currentPower") or 0)
                            self._cache["generation_w"] = kw * 1000
                            self._cache["generation_today_kwh"] = float(data.get("dailyEnergy") or 0)
                            self._cache["generation_total_kwh"] = float(data.get("cumulativeEnergy") or 0)
                            self._cache["consumption_today_kwh"] = float(data.get("dailyUseEnergy") or 0)
                    else:
                        _AC_LOGGER.warning("FusionSolar KPI devuelto con error de estructura, reiniciando sesión.")
                        break

                    # Consulta 2: Flujo de Energía (Inversor / Casa / Excedentes)
                    try:
                        eflow = page.evaluate("""
                            async (dn) => {
                                const r = await fetch(
                                    '/rest/pvms/web/station/v3/overview/energy-flow?stationDn='
                                    + encodeURIComponent(dn) + '&featureId=aifc&_=' + Date.now(),
                                    { credentials: 'include' }
                                );
                                return await r.json();
                            }
                        """, station_dn)
                        if eflow and eflow.get("success") and eflow.get("data"):
                            flow_data = eflow["data"]["flow"]
                            load_w = 0
                            pv_w = 0
                            for node in flow_data.get("nodes", []):
                                nid = node.get("id")
                                val = node.get("value")
                                if nid == "5" and val is not None:
                                    load_w = float(val) * 1000
                                elif nid == "0" and val is not None:
                                    pv_w = float(val) * 1000
                            with self._cache_lock:
                                self._cache["consumption_w"] = load_w
                                self._cache["surplus_w"] = pv_w - load_w
                    except Exception:
                        pass # Si falla el flujo de energía puntualmente, no tiramos la sesión entera abajo

                    # Espera de 60 segundos entre lecturas estándar
                    import time as _time
                    _time.sleep(60)

            except Exception as e:
                _AC_LOGGER.error("Error crítico en monitor FusionSolar: %s. Reabriendo instancia...", e)
                if not self._ready.is_set():
                    self._ready.set()
            finally:
                # Cierre absoluto y limpio de Playwright para evitar procesos zombis en RAM
                try:
                    if browser:
                        browser.close()
                    if pw:
                        pw.stop()
                except Exception:
                    pass
            
            # Pequeña pausa de seguridad antes de levantar el nuevo navegador limpio (evita spam si cae internet)
            import time as _time
            _time.sleep(10)

        _AC_LOGGER.info("FusionSolar monitor stopped")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def ready(self):
        return self._ready.is_set()


class _FusionSolarBase(CustomDataSource):
    _monitor_started = False

    def __init__(self):
        super().__init__()
        if not _FusionSolarBase._monitor_started:
            monitor = _FusionSolarMonitor.get_instance()
            monitor.start()
            _FusionSolarBase._monitor_started = True

    @property
    def _monitor(self):
        return _FusionSolarMonitor.get_instance()

    def last_values(self) -> List[float]:
        pass


class SolarGeneration(_FusionSolarBase):
    def as_numeric(self) -> float:
        return self._monitor.get("generation_w")

    def as_string(self) -> str:
        w = self._monitor.get("generation_w")
        if not self._monitor.ready:
            return "-- W"
        if w <= 0:
            return "0 W"
        if w < 1000:
            return f"{w:.0f} W"
        else:
            return f"{w / 1000:.2f} kW"


class SolarGenerationToday(_FusionSolarBase):
    def as_numeric(self) -> float:
        return self._monitor.get("generation_today_kwh")

    def as_string(self) -> str:
        kwh = self._monitor.get("generation_today_kwh")
        if not self._monitor.ready:
            return "-- kWh"
        return f"{kwh:.1f} kWh"


class HousePowerConsumption(_FusionSolarBase):
    def as_numeric(self) -> float:
        return self._monitor.get("consumption_today_kwh")

    def as_string(self) -> str:
        kwh = self._monitor.get("consumption_today_kwh")
        if not self._monitor.ready:
            return "-- kWh"
        return f"{kwh:.1f} kWh"


class SolarConsumption(_FusionSolarBase):
    def as_numeric(self) -> float:
        return self._monitor.get("consumption_w")

    def as_string(self) -> str:
        w = self._monitor.get("consumption_w")
        if not self._monitor.ready:
            return "-- W"
        if w <= 0:
            return "0 W"
        if w < 1000:
            return f"{w:.0f} W"
        else:
            return f"{w / 1000:.2f} kW"


# Tarifas electricas (EUR/kWh): vertido a red (excedente) y consumo de red.
SURPLUS_PRICE = 0.06  # precio por kWh excedente exportado a la red
GRID_PRICE = 0.13     # precio por kWh importado de la red


class SolarSurplus(_FusionSolarBase):
    def as_numeric(self) -> float:
        return self._monitor.get("surplus_w")

    def as_string(self) -> str:
        w = self._monitor.get("surplus_w")
        if not self._monitor.ready:
            return "-- W"
        if w > 0:
            return f"+{w:.0f} W"
        elif w < 0:
            return f"{w:.0f} W"
        return "0 W"


class SolarMoney(_FusionSolarBase):
    def as_numeric(self) -> float:
        return self._monitor.get("surplus_w")

    def as_string(self) -> str:
        mon = self._monitor
        if not mon.ready:
            return "--.--€"

        gen_w = mon.get("generation_w")
        load_w = mon.get("consumption_w")

        if gen_w is None or load_w is None:
            return "--.--€"

        surplus_kw = (gen_w - load_w) / 1000.0
        if surplus_kw > 0:
            earn_ph = surplus_kw * SURPLUS_PRICE
            return f"+{earn_ph:.2f}€/h"
        elif surplus_kw < 0:
            cost_ph = -surplus_kw * GRID_PRICE
            return f"-{cost_ph:.2f}€/h"
        return "0.00€/h"