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

    def _update_cache(self, device):
        with self._cache_lock:
            self._cache["power_state"] = device.power_state
            self._cache["indoor_temperature"] = device.indoor_temperature
            self._cache["outdoor_temperature"] = device.outdoor_temperature
            self._cache["target_temperature"] = device.target_temperature
            self._cache["operational_mode"] = device.operational_mode
            self._cache["fan_speed"] = device.fan_speed
            self._cache["eco"] = device.eco
            self._cache["turbo"] = device.turbo
            self._cache["error_code"] = device.error_code
            self._cache["total_energy"] = device.get_total_energy_usage()
            self._cache["current_energy"] = device.get_current_energy_usage()
            self._cache["real_time_power"] = device.get_real_time_power_usage()

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

        try:
            with open(_CREDS_PATH) as f:
                creds = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            _AC_LOGGER.error("Midea AC credentials not found at %s: %s",
                             _CREDS_PATH, e)
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
        return self._monitor.get("outdoor_temperature") or 0.0

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
        return "ECO" if self._monitor.get("eco") else None


class MideaACTurbo(_MideaACBase):
    def as_numeric(self) -> float:
        return 1.0 if self._monitor.get("turbo") else 0.0

    def as_string(self) -> str:
        return "TURBO" if self._monitor.get("turbo") else None


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


# ---------------------------------------------------------------------------
# FusionSolar (Huawei SUN2000) Integration via internal REST API
# ---------------------------------------------------------------------------
# Uses Playwright to log in once, then calls the same REST API that the
# FusionSolar web portal uses internally to get real-time data:
#   - currentPower (kW) → generation_w
#   - dailyEnergy (kWh) → generation_today_kwh
#   - cumulativeEnergy (kWh) → generation_total_kwh
#   - dailyUseEnergy (kWh) → consumption_today_kwh
#
# Credentials file: library/fusionsolar_credentials.json
#   { "username": "tu@email.com", "password": "tu_contraseña" }
# ---------------------------------------------------------------------------

_FUSION_CREDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "fusionsolar_credentials.json")


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

        try:
            with open(_FUSION_CREDS_PATH) as f:
                creds = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            _AC_LOGGER.warning("FusionSolar credentials not found (%s)", e)
            self._ready.set()
            return

        username = creds.get("username", "")
        password = creds.get("password", "")
        if not username or not password:
            _AC_LOGGER.error("FusionSolar credentials incomplete")
            self._ready.set()
            return

        _AC_LOGGER.info("Starting FusionSolar monitor...")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                viewport={"width": 1280, "height": 800}, locale="es-ES",
            )
            page = context.new_page()
            station_dn = None

            try:
                page.goto("https://eu5.fusionsolar.huawei.com", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)

                # Register response handler to capture dashboard API calls after login
                def _capture_dn(response):
                    nonlocal station_dn
                    if 'station-real-kpi' in response.url and station_dn is None:
                        parsed = urlparse(response.url)
                        params = parse_qs(parsed.query)
                        dn = params.get('stationDn', [None])[0]
                        if dn:
                            station_dn = dn
                            _AC_LOGGER.info("FusionSolar station DN: %s", station_dn)

                page.on("response", _capture_dn)

                # Login
                inputs = page.locator("input.right_name_textfield").all()
                inputs[0].fill(username)
                inputs[1].fill(password)
                page.wait_for_timeout(500)
                page.locator("div.loginBtn:has-text('Iniciar sesión')").first.click()
                page.wait_for_timeout(10000)
                page.wait_for_load_state("networkidle", timeout=20000)

                if "login" in page.url.lower():
                    _AC_LOGGER.error("FusionSolar login failed")
                    self._ready.set()
                    browser.close()
                    return

                _AC_LOGGER.info("FusionSolar login OK")

                # Wait for dashboard to fully load and make its API calls
                page.wait_for_timeout(8000)
                page.wait_for_load_state("networkidle", timeout=20000)

                if not station_dn:
                    _AC_LOGGER.warning("Could not get station DN from page, trying station-list API")
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
                        _AC_LOGGER.warning("station-list API failed: %s", e)

                self._ready.set()

                while self._running:
                    try:
                        if not station_dn:
                            _AC_LOGGER.warning("No station DN, skipping poll")
                            import time as _time
                            _time.sleep(60)
                            continue

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
                                self._cache["generation_today_kwh"] = float(
                                    data.get("dailyEnergy") or 0)
                                self._cache["generation_total_kwh"] = float(
                                    data.get("cumulativeEnergy") or 0)
                                self._cache["consumption_today_kwh"] = float(
                                    data.get("dailyUseEnergy") or 0)

                            _AC_LOGGER.debug(
                                "FusionSolar: gen=%.0fW daily=%.1fkWh total=%.1fkWh cons=%.1fkWh",
                                kw * 1000,
                                float(data.get("dailyEnergy") or 0),
                                float(data.get("cumulativeEnergy") or 0),
                                float(data.get("dailyUseEnergy") or 0),
                            )
                        else:
                            _AC_LOGGER.warning("FusionSolar API error: %s", resp)

                        # Also fetch energy-flow for real-time consumption
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
                                    if nid == "5" and val is not None:  # Load
                                        load_w = float(val) * 1000
                                    elif nid == "0" and val is not None:  # PV
                                        pv_w = float(val) * 1000
                                with self._cache_lock:
                                    self._cache["consumption_w"] = load_w
                                    self._cache["surplus_w"] = pv_w - load_w
                        except Exception:
                            pass

                    except Exception as e:
                        _AC_LOGGER.warning("FusionSolar API call failed: %s", e)
                        # Relogin on failure
                        try:
                            page.goto("https://eu5.fusionsolar.huawei.com",
                                      timeout=30000)
                            page.wait_for_load_state("networkidle", timeout=15000)
                            inputs = page.locator("input.right_name_textfield").all()
                            inputs[0].fill(username)
                            inputs[1].fill(password)
                            page.locator(
                                "div.loginBtn:has-text('Iniciar sesión')"
                            ).first.click()
                            page.wait_for_timeout(10000)
                            page.wait_for_load_state("networkidle", timeout=20000)
                            # Re-capture station DN after relogin
                            station_dn = None
                            page.on("response", _capture_dn)
                            page.wait_for_timeout(5000)
                            page.wait_for_load_state("networkidle", timeout=20000)
                        except Exception:
                            pass

                    import time as _time
                    _time.sleep(60)

            except Exception as e:
                _AC_LOGGER.error("FusionSolar error: %s", e)
                if not self._ready.is_set():
                    self._ready.set()
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

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


class SolarSurplus(_FusionSolarBase):
    SURPLUS_PRICE = 0.06
    GRID_PRICE = 0.13

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
    SURPLUS_PRICE = 0.06
    GRID_PRICE = 0.13

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

        # Real-time hourly rate
        surplus_kw = (gen_w - load_w) / 1000.0
        if surplus_kw > 0:
            earn_ph = surplus_kw * self.SURPLUS_PRICE
            return f"+{earn_ph:.2f}€/h"
        elif surplus_kw < 0:
            cost_ph = -surplus_kw * self.GRID_PRICE
            return f"-{cost_ph:.2f}€/h"
        return "0.00€/h"
