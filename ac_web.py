#!/usr/bin/env python
"""AC Midea Web Control - interfaz web para controlar el aire acondicionado via msmart-ng"""

import asyncio
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from msmart.device import AirConditioner

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger("ac_web")

CREDS_PATH = Path(__file__).parent / "library" / "midea_ac_credentials.json"

app = FastAPI(title="AC Midea Control")
_device = None
_device_lock = asyncio.Lock()

MODE_NAMES = {
    1: "AUTO", 2: "FRÍO", 3: "SECO",
    4: "CALOR", 5: "VENT", 6: "S.DRY",
}
MODE_VALUES = {v: k for k, v in MODE_NAMES.items()}

FAN_NAMES = {
    20: "SILEN", 40: "BAJO", 60: "MEDIO",
    80: "ALTO", 100: "MÁX", 102: "AUTO",
}


async def _get_device() -> AirConditioner:
    global _device
    async with _device_lock:
        if _device is None:
            with open(CREDS_PATH) as f:
                creds = json.load(f)
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


@app.get("/")
async def index():
    html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>AC Midea Control</title>
<style>
  :root {
    --bg: #0f0f1a;
    --card: #1a1a2e;
    --card2: #16213e;
    --accent: #00d4ff;
    --accent2: #7c3aed;
    --green: #22c55e;
    --red: #ef4444;
    --text: #e2e8f0;
    --dim: #64748b;
    --glass: rgba(255,255,255,0.04);
    --radius: 20px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 16px;
    background-image: radial-gradient(ellipse at 50% 0%, #1a1a3e 0%, transparent 60%);
  }
  .container { width: 100%; max-width: 400px; }

  /* HEADER */
  .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
  .header h1 { font-size: 16px; font-weight: 600; color: var(--dim); letter-spacing: 1px; text-transform: uppercase; }
  .header .status-led {
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; font-weight: 500; color: var(--dim);
  }
  .led { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .led.on { background: var(--green); box-shadow: 0 0 8px var(--green); }
  .led.off { background: var(--dim); }

  /* TEMP DIAL */
  .dial-wrap {
    background: var(--card);
    border-radius: var(--radius);
    padding: 32px 24px 24px;
    text-align: center;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
  }
  .dial-wrap::before {
    content: '';
    position: absolute;
    top: -50%;
    left: 50%;
    transform: translateX(-50%);
    width: 200%;
    height: 100%;
    background: radial-gradient(ellipse at center, rgba(0,212,255,0.06) 0%, transparent 60%);
    pointer-events: none;
  }
  .temp-indoor {
    font-size: 56px;
    font-weight: 300;
    line-height: 1;
    color: var(--text);
    position: relative;
  }
  .temp-indoor .deg { font-size: 24px; color: var(--accent); vertical-align: super; }
  .temp-label { font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

  /* TEMP TARGET ROW */
  .target-row {
    display: flex; justify-content: center; align-items: center; gap: 16px;
    margin-top: 16px;
  }
  .target-row .target-label { font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.5px; }
  .target-row .target-val { font-size: 24px; font-weight: 600; color: var(--accent); }
  .target-row .target-val.off { color: var(--dim); }
  .target-arrows { display: flex; gap: 4px; }
  .arrow-btn {
    width: 36px; height: 36px; border-radius: 50%;
    border: none; background: var(--glass); color: var(--accent);
    font-size: 18px; cursor: pointer; transition: .2s;
    display: flex; align-items: center; justify-content: center;
  }
  .arrow-btn:hover { background: rgba(0,212,255,0.12); }
  .arrow-btn:active { transform: scale(0.9); }
  .arrow-btn:disabled { opacity: 0.3; cursor: default; }

  /* GRID CARDS */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
  .info-card {
    background: var(--card);
    border-radius: 16px;
    padding: 14px;
    text-align: center;
  }
  .info-card .icon { font-size: 18px; margin-bottom: 4px; }
  .info-card .val { font-size: 18px; font-weight: 600; }
  .info-card .lbl { font-size: 10px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }

  /* MIC */
  .mic-wrap { display: flex; justify-content: center; margin: 8px 0; }
  .mic-btn {
    background: var(--card);
    border: 1px solid var(--dim);
    color: var(--text);
    width: 44px; height: 44px;
    border-radius: 50%;
    font-size: 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: .25s;
    position: relative;
  }
  .mic-btn:hover { border-color: var(--accent); }
  .mic-btn.listening {
    border-color: var(--green);
    box-shadow: 0 0 14px var(--green);
    animation: mPulse 1s infinite;
  }
  .mic-btn .mic-tip {
    display: none;
    position: absolute;
    top: 48px; left: 50%;
    transform: translateX(-50%);
    background: var(--card2);
    border: 1px solid var(--dim);
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 11px;
    white-space: nowrap;
    color: var(--text);
    z-index: 10;
  }
  .mic-btn.listening .mic-tip { display: block; }
  .mic-cmd {
    text-align: center;
    font-size: 12px;
    color: var(--accent);
    min-height: 18px;
    margin: 4px 0 8px;
    transition: .2s;
  }
  @keyframes mPulse {
    0%,100% { box-shadow: 0 0 8px var(--green); }
    50% { box-shadow: 0 0 22px var(--green); }
  }

  /* SECTION */
  .section-label {
    font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: 1px;
    margin: 12px 0 8px; display: flex; align-items: center; gap: 6px;
  }

  /* MODE GRID */
  .mode-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 8px; }
  .mode-btn {
    background: var(--card); border: 2px solid transparent;
    border-radius: 14px; padding: 10px 4px;
    text-align: center; cursor: pointer; transition: .2s;
    font-size: 11px; font-weight: 600; color: var(--dim);
  }
  .mode-btn .mode-icon { font-size: 20px; display: block; margin-bottom: 4px; }
  .mode-btn:hover { border-color: rgba(0,212,255,0.3); }
  .mode-btn.active {
    border-color: var(--accent); color: var(--accent);
    background: rgba(0,212,255,0.08);
    box-shadow: 0 0 20px rgba(0,212,255,0.1);
  }

  /* FAN GRID */
  .fan-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; margin-bottom: 16px; }
  .fan-btn {
    background: var(--card); border: 2px solid transparent;
    border-radius: 12px; padding: 8px 2px;
    text-align: center; cursor: pointer; transition: .2s;
    font-size: 10px; font-weight: 600; color: var(--dim);
  }
  .fan-btn .fan-icon { font-size: 16px; display: block; margin-bottom: 2px; }
  .fan-btn:hover { border-color: rgba(124,58,237,0.3); }
  .fan-btn.active {
    border-color: var(--accent2); color: var(--accent2);
    background: rgba(124,58,237,0.08);
  }

  /* POWER BUTTONS */
  .power-row { display: flex; gap: 10px; margin-bottom: 0; }
  .power-btn {
    flex: 1; padding: 14px; border: none; border-radius: 14px;
    font-size: 14px; font-weight: 600; cursor: pointer; transition: .2s;
  }
  .power-btn:active { transform: scale(0.97); }
  .power-btn.on { background: linear-gradient(135deg, #22c55e, #16a34a); color: #fff; }
  .power-btn.off { background: linear-gradient(135deg, #ef4444, #dc2626); color: #fff; }
  .power-btn.on.active { box-shadow: 0 0 24px rgba(34,197,94,0.3); }

  /* STATUS BAR */
  .status-bar {
    display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px;
    font-size: 11px; color: var(--dim);
  }
  .status-bar span { background: var(--glass); padding: 4px 10px; border-radius: 20px; }

  .error {
    color: var(--red); text-align: center; font-size: 12px;
    padding: 8px; margin-top: 8px; display: none;
    background: rgba(239,68,68,0.1); border-radius: 10px;
  }

  @media (max-width: 380px) {
    .temp-indoor { font-size: 44px; }
    .mode-grid { gap: 4px; }
    .fan-grid { gap: 4px; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>AC Midea</h1>
    <div class="status-led">
      <span class="led" id="power-led"></span>
      <span id="power-text">APAGADO</span>
    </div>
  </div>

  <!-- VOICE -->
  <div class="mic-wrap">
    <button class="mic-btn" id="mic-btn" title="Control por voz">
      🎤
      <span class="mic-tip" id="mic-tip">Escuchando...</span>
    </button>
  </div>
  <div class="mic-cmd" id="mic-cmd"></div>

  <!-- TEMP DIAL -->
  <div class="dial-wrap">
    <div class="temp-indoor" id="indoor-temp">--<span class="deg">°</span></div>
    <div class="temp-label">Temperatura ambiente</div>
    <div class="target-row">
      <span class="target-label">Objetivo</span>
      <div class="target-arrows">
        <button class="arrow-btn" id="temp-down">−</button>
      </div>
      <span class="target-val" id="target-temp">--°</span>
      <div class="target-arrows">
        <button class="arrow-btn" id="temp-up">+</button>
      </div>
    </div>
  </div>

  <!-- INFO CARDS -->
  <div class="grid-2">
    <div class="info-card">
      <div class="icon">🌡️</div>
      <div class="val" id="info-mode">--</div>
      <div class="lbl">Modo</div>
    </div>
    <div class="info-card">
      <div class="icon">💨</div>
      <div class="val" id="info-fan">--</div>
      <div class="lbl">Ventilador</div>
    </div>
    <div class="info-card">
      <div class="icon">🪟</div>
      <div class="val" id="info-outdoor">--°</div>
      <div class="lbl">Exterior</div>
    </div>
    <div class="info-card">
      <div class="icon">⚡</div>
      <div class="val" id="info-swing">--</div>
      <div class="lbl">Oscilación</div>
    </div>
  </div>

  <div class="error" id="error"></div>

  <!-- CONSUMPTION -->
  <div class="grid-2">
    <div class="info-card">
      <div class="icon">⚡</div>
      <div class="val" id="info-total-energy">--</div>
      <div class="lbl">Consumo total</div>
    </div>
    <div class="info-card">
      <div class="icon">🔌</div>
      <div class="val" id="info-power-now">--</div>
      <div class="lbl">Potencia ahora</div>
    </div>
  </div>

  <!-- MODE -->
  <div class="section-label">Modo</div>
  <div class="mode-grid" id="mode-grid">
    <div class="mode-btn" data-mode="AUTO"><span class="mode-icon">🔄</span>AUTO</div>
    <div class="mode-btn" data-mode="FRÍO"><span class="mode-icon">❄️</span>FRÍO</div>
    <div class="mode-btn" data-mode="SECO"><span class="mode-icon">💧</span>SECO</div>
    <div class="mode-btn" data-mode="CALOR"><span class="mode-icon">🔥</span>CALOR</div>
    <div class="mode-btn" data-mode="VENT"><span class="mode-icon">🌀</span>VENT</div>
  </div>

  <!-- FAN -->
  <div class="section-label">Ventilador</div>
  <div class="fan-grid" id="fan-grid">
    <div class="fan-btn" data-fan="20"><span class="fan-icon">🍃</span>SILEN</div>
    <div class="fan-btn" data-fan="40"><span class="fan-icon">🌿</span>BAJO</div>
    <div class="fan-btn" data-fan="60"><span class="fan-icon">🌬️</span>MEDIO</div>
    <div class="fan-btn" data-fan="80"><span class="fan-icon">💨</span>ALTO</div>
    <div class="fan-btn" data-fan="100"><span class="fan-icon">🌪️</span>MÁX</div>
    <div class="fan-btn" data-fan="102"><span class="fan-icon">🤖</span>AUTO</div>
  </div>

  <!-- POWER -->
  <div class="power-row">
    <button class="power-btn on" id="btn-on">Encender</button>
    <button class="power-btn off" id="btn-off">Apagar</button>
  </div>

  <!-- STATUS -->
  <div class="status-bar" id="status-bar"></div>
</div>
<script>
let state = {};

async function api(method, params={}) {
  const url = '/api/' + method + '?' + new URLSearchParams(params);
  try {
    const r = await fetch(url);
    const data = await r.json();
    if (data.error) {
      document.getElementById('error').textContent = data.error;
      document.getElementById('error').style.display = 'block';
    } else {
      document.getElementById('error').style.display = 'none';
    }
    if (data.status) updateUI(data.status);
    return data;
  } catch(e) {
    document.getElementById('error').textContent = 'Error de conexión';
    document.getElementById('error').style.display = 'block';
  }
}

function updateUI(s) {
  state = s;
  const on = s.power;

  // LED
  const led = document.getElementById('power-led');
  led.className = 'led ' + (on ? 'on' : 'off');
  document.getElementById('power-text').textContent = on ? 'ENCENDIDO' : 'APAGADO';

  // Indoor temp
  const it = s.indoor_temp;
  document.getElementById('indoor-temp').innerHTML = (it != null ? it.toFixed(1) : '--') + '<span class="deg">°</span>';

  // Target temp
  const tt = s.target_temp;
  const ttv = document.getElementById('target-temp');
  ttv.textContent = (tt != null ? tt + '\u00b0' : '--\u00b0');
  ttv.className = 'target-val' + (on ? '' : ' off');

  // Info cards
  document.getElementById('info-mode').textContent = on ? (s.mode || '--') : '--';
  document.getElementById('info-fan').textContent = on ? (s.fan_speed || '--') : '--';
  document.getElementById('info-outdoor').textContent = (s.outdoor_temp != null ? s.outdoor_temp.toFixed(1) + '\u00b0' : '--\u00b0');
  document.getElementById('info-swing').textContent = on ? (s.swing || '--') : '--';

  // Energy
  document.getElementById('info-total-energy').textContent = (s.total_energy != null ? s.total_energy.toFixed(1) + ' kWh' : '--');
  document.getElementById('info-power-now').textContent = (s.real_time_power != null && s.real_time_power > 0 ? s.real_time_power.toFixed(0) + ' W' : 'N/A');

  // Mode buttons
  document.querySelectorAll('.mode-btn').forEach(b => {
    b.classList.toggle('active', on && b.dataset.mode === s.mode);
  });

  // Fan buttons
  document.querySelectorAll('.fan-btn').forEach(b => {
    b.classList.toggle('active', on && parseInt(b.dataset.fan) === s.fan_speed_code);
  });

  // Power buttons
  document.getElementById('btn-on').classList.toggle('active', on);
  document.getElementById('btn-off').classList.toggle('active', !on);

  // Status bar
  const bar = document.getElementById('status-bar');
  bar.innerHTML = '';
  if (s.eco) bar.innerHTML += '<span>ECO</span>';
  if (s.turbo) bar.innerHTML += '<span>TURBO</span>';
  if (s.error) bar.innerHTML += '<span style="color:var(--red)">ERROR: ' + s.error + '</span>';
}

// HANDLERS
document.querySelectorAll('.mode-btn').forEach(b => {
  b.addEventListener('click', () => api('mode', {mode: b.dataset.mode}));
});
document.querySelectorAll('.fan-btn').forEach(b => {
  b.addEventListener('click', () => api('fan', {speed: b.dataset.fan}));
});
document.getElementById('btn-on').addEventListener('click', () => api('power', {on: true}));
document.getElementById('btn-off').addEventListener('click', () => api('power', {on: false}));

// Temp arrows
document.getElementById('temp-up').addEventListener('click', () => {
  const cur = state.target_temp || 24;
  if (cur < 30) api('temp', {temp: cur + 1});
});
document.getElementById('temp-down').addEventListener('click', () => {
  const cur = state.target_temp || 24;
  if (cur > 16) api('temp', {temp: cur - 1});
});

// VOICE CONTROL
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let micListening = false;
let micTimer = null;

function micLog(msg) {
  document.getElementById('mic-cmd').textContent = msg;
}
function micClear() {
  if (micTimer) { clearTimeout(micTimer); micTimer = null; }
  micListening = false;
  document.getElementById('mic-btn').classList.remove('listening');
}

function startMic() {
  if (!SpeechRecognition) {
    micLog('❌ El navegador no soporta control por voz');
    return;
  }
  if (recognition) recognition.abort();
  recognition = new SpeechRecognition();
  recognition.lang = 'es-ES';
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 3;

  recognition.onstart = () => {
    micListening = true;
    document.getElementById('mic-btn').classList.add('listening');
    micLog('🎤 Escuchando...');
    // Timeout: auto-stop after 10s of silence
    micTimer = setTimeout(() => {
      if (micListening) {
        micLog('⏱️ Tiempo agotado, tocá 🎤 para hablar');
        micClear();
      }
    }, 10000);
  };
  recognition.onerror = (e) => {
    if (e.error === 'not-allowed') {
      micLog('❌ Micrófono bloqueado - permitilo en el navegador');
    } else if (e.error === 'no-speech') {
      micLog('🔇 No escuché nada, intentá de nuevo');
    } else if (e.error !== 'aborted') {
      micLog('❌ Error: ' + e.error);
    }
    micClear();
  };
  recognition.onend = () => {
    micClear();
  };
  recognition.onresult = (e) => {
    const cmds = [];
    for (let i = 0; i < e.results[0].length; i++) {
      cmds.push(e.results[0][i].transcript.toLowerCase().trim());
    }
    const transcript = cmds[0];
    micClear();
    micLog('🗣️ "' + transcript + '"');
    processVoice(transcript, cmds);
    // Restart listening after a short delay so user can speak again
    setTimeout(() => {
      if (document.getElementById('mic-btn').classList.contains('listening')) return;
      // Don't auto-restart, user clicks mic again
    }, 100);
  };
  try {
    recognition.start();
  } catch(e) {
    micLog('❌ Error al iniciar: ' + e.message);
    micClear();
  }
}

function stopMic() {
  if (recognition) { try { recognition.abort(); } catch(e) {} recognition = null; }
  micClear();
}

document.getElementById('mic-btn').addEventListener('click', () => {
  if (micListening) { stopMic(); micLog('🎤 Micrófono apagado'); }
  else startMic();
});

const MODE_MAP = {
  'frío': 'FRÍO', 'frio': 'FRÍO', 'calor': 'CALOR',
  'seco': 'SECO', 'auto': 'AUTO', 'ventilador': 'VENT',
  'vent': 'VENT', 'solo ventilador': 'VENT', 'solo vent': 'VENT'
};
const FAN_MAP = {
  'silencioso': '20', 'silen': '20', 'bajo': '40', 'medio': '60',
  'alto': '80', 'máximo': '100', 'maximo': '100', 'max': '100',
  'auto': '102'
};

function processVoice(text, allTexts) {
  // Power on/off
  if (text.includes('encender') || text.includes('prender') || text.includes('activa')) {
    api('power', {on: true});
    return;
  }
  if (text.includes('apagar') || text.includes('desactiv') || text.includes('apaga')) {
    api('power', {on: false});
    return;
  }

  // Temperature
  const nums = text.match(/\d+/g);
  if (text.includes('temperatura') && nums) {
    const t = parseInt(nums[0]);
    if (t >= 16 && t <= 30) { api('temp', {temp: t}); return; }
  }
  if ((text.includes('subir') || text.includes('aument') || text.includes('más calor')) && state.target_temp) {
    if (state.target_temp < 30) api('temp', {temp: state.target_temp + 1});
    return;
  }
  if ((text.includes('bajar') || text.includes('reduc') || text.includes('más frío')) && state.target_temp) {
    if (state.target_temp > 16) api('temp', {temp: state.target_temp - 1});
    return;
  }
  // "a X grados"
  if (nums && text.includes('grado')) {
    const t = parseInt(nums[0]);
    if (t >= 16 && t <= 30) { api('temp', {temp: t}); return; }
  }

  // Mode
  if (text.includes('modo')) {
    for (const [key, val] of Object.entries(MODE_MAP)) {
      if (text.includes(key)) { api('mode', {mode: val}); return; }
    }
  }

  // Fan
  if (text.includes('ventilador') || text.includes('velocidad')) {
    for (const [key, val] of Object.entries(FAN_MAP)) {
      if (text.includes(key)) { api('fan', {speed: val}); return; }
    }
  }

  // Direct shortcuts
  for (const [key, val] of Object.entries(MODE_MAP)) {
    if (text === key || text.includes('pon ' + key) || text.includes('ponga ' + key)) {
      api('mode', {mode: val}); return;
    }
  }

  document.getElementById('mic-cmd').textContent += ' ❌ No entendí';
}

// Init
api('status');
setInterval(() => api('status'), 10000);
</script>
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/api/status")
async def api_status():
    try:
        dev = await _refresh()
        return {"status": _status_dict(dev)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/power")
async def api_power(on: bool = Query(...)):
    try:
        dev = await _get_device()
        dev.power_state = on
        await _apply()
        await dev.refresh()
        return {"status": _status_dict(dev)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/mode")
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


@app.get("/api/temp")
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


@app.get("/api/fan")
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
    import uvicorn
    print("=== AC Midea Web Control ===")
    print("Abrir http://localhost:8080 en el navegador")
    uvicorn.run(app, host="0.0.0.0", port=8080)
