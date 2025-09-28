#!/usr/bin/env python3
import logging
import os
import sys
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from mqtt_listener import DataStore, MQTTIngest


def get_options() -> Dict[str, Any]:
    # Home Assistant add-on options
    import json
    opts_path = "/data/options.json"
    try:
        with open(opts_path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def create_app(store: DataStore) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(content=INDEX_HTML, status_code=200)

    @app.get("/api/now")
    def api_now():
        snap = store.snapshot()
        return JSONResponse({"now": snap["now"]})

    @app.get("/api/daily")
    def api_daily():
        snap = store.snapshot()
        return JSONResponse({
            "series": snap["daily_series"],
            "today": snap["daily_today"],
            "tomorrow": snap["daily_tomorrow"],
        })

    return app


def main():
    opts = get_options()
    log_level = str(opts.get("log_level", "INFO")).upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format='[%(levelname)s] %(message)s', stream=sys.stdout)

    host = opts.get("mqtt_host", "core-mosquitto")
    port = int(opts.get("mqtt_port", 1883))
    username = opts.get("mqtt_username", "")
    password = opts.get("mqtt_password", "")
    prefix = opts.get("topic_prefix", "weather")
    site_id = opts.get("site_id", "default")

    store = DataStore()
    ing = MQTTIngest(host, port, username, password, prefix, site_id, store)
    ing.start()

    app = create_app(store)
    port = int(os.getenv("PORT", 8099))
    uvicorn.run(app, host="0.0.0.0", port=port)


INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Weather Dashboard</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 0; padding: 0; background: #111; color: #eee; }
      header { padding: 12px 16px; background: #222; border-bottom: 1px solid #333; }
      .container { padding: 16px; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
      .card { background: #1b1b1b; border: 1px solid #2a2a2a; border-radius: 8px; padding: 12px; }
      h1 { font-size: 18px; margin: 0; }
      h2 { font-size: 16px; margin: 0 0 8px; }
      table { width: 100%; border-collapse: collapse; }
      td { padding: 4px 0; border-bottom: 1px dashed #333; }
      td.key { color: #aaa; width: 60%; }
      td.val { text-align: right; }
      small { color: #888; }
      .icon { display: flex; align-items: center; justify-content: center; margin-bottom: 8px; }
      canvas { width: 100%; height: 180px; background: #161616; border-radius: 6px; border: 1px solid #2a2a2a; }
    </style>
  </head>
  <body>
    <header>
      <h1>Weather Dashboard</h1>
    </header>
    <div class="container">
      <div class="grid">
        <div class="card">
          <h2>Now</h2>
          <div id="now-icon" class="icon"></div>
          <table id="now-table"></table>
          <small id="now-ts"></small>
        </div>
        <div class="card">
          <h2>Today</h2>
          <div id="today-icon" class="icon"></div>
          <table id="today-table"></table>
        </div>
        <div class="card">
          <h2>Tomorrow</h2>
          <div id="tomorrow-icon" class="icon"></div>
          <table id="tomorrow-table"></table>
        </div>
        <div class="card">
          <h2>Daily GHI (MJ/m²)</h2>
          <canvas id="series-canvas" width="640" height="180"></canvas>
          <table id="series-table"></table>
        </div>
      </div>
    </div>
    <script>
      const fmt = (v) => (v === null || v === undefined) ? '-' : (typeof v === 'number' ? v.toFixed(2) : String(v));

      function iconSvg(kind) {
        // Minimal inline SVGs: clear, partly, cloudy, rain
        if (kind === 'clear') {
          return `<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="32" cy="32" r="14" fill="#FDB813"/>
            <g stroke="#FDB813" stroke-width="3">
              <line x1="32" y1="6" x2="32" y2="16"/>
              <line x1="32" y1="48" x2="32" y2="58"/>
              <line x1="6" y1="32" x2="16" y2="32"/>
              <line x1="48" y1="32" x2="58" y2="32"/>
              <line x1="12" y1="12" x2="19" y2="19"/>
              <line x1="45" y1="45" x2="52" y2="52"/>
              <line x1="12" y1="52" x2="19" y2="45"/>
              <line x1="45" y1="19" x2="52" y2="12"/>
            </g>
          </svg>`;
        }
        if (kind === 'partly') {
          return `<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
            <circle cx="22" cy="22" r="10" fill="#FDB813"/>
            <ellipse cx="38" cy="38" rx="16" ry="10" fill="#9AA4AD"/>
            <ellipse cx="26" cy="40" rx="12" ry="8" fill="#B3BDC6"/>
          </svg>`;
        }
        if (kind === 'cloudy') {
          return `<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
            <ellipse cx="38" cy="36" rx="18" ry="12" fill="#9AA4AD"/>
            <ellipse cx="24" cy="40" rx="14" ry="10" fill="#B3BDC6"/>
          </svg>`;
        }
        // rain
        return `<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
          <ellipse cx="38" cy="28" rx="18" ry="12" fill="#9AA4AD"/>
          <ellipse cx="24" cy="32" rx="14" ry="10" fill="#B3BDC6"/>
          <g stroke="#4FC3F7" stroke-width="3">
            <line x1="22" y1="44" x2="18" y2="56"/>
            <line x1="32" y1="46" x2="28" y2="58"/>
            <line x1="42" y1="44" x2="38" y2="56"/>
          </g>
        </svg>`;
      }

      function classifyNow(now) {
        const cc = now.cloud_cover_pct?.value ?? null;
        const pr = now.precip_probability_pct?.value ?? null;
        const pm = now.precip_mm?.value ?? null;
        if ((pm !== null && pm > 0.1) || (pr !== null && pr >= 50)) return 'rain';
        if (cc === null) return 'cloudy';
        if (cc < 20) return 'clear';
        if (cc < 60) return 'partly';
        return 'cloudy';
      }

      function classifyDay(day) {
        const pm = day.precip_day_total_mm?.value ?? null;
        const cc = day.cloud_cover_day_mean_pct?.value ?? null;
        if (pm !== null && pm > 0.1) return 'rain';
        if (cc === null) return 'cloudy';
        if (cc < 20) return 'clear';
        if (cc < 60) return 'partly';
        return 'cloudy';
      }
      function renderNow(now) {
        const keys = [
          ['ghi_w_m2', 'GHI (W/m²)'],
          ['dni_w_m2', 'DNI (W/m²)'],
          ['dhi_w_m2', 'DHI (W/m²)'],
          ['k_ghi', 'k_GHI'],
          ['sun_elevation_deg', 'Sun Elevation (°)'],
          ['sun_azimuth_deg', 'Sun Azimuth (°)'],
          ['cloud_cover_pct', 'Cloud Cover (%)'],
          ['temp_2m_c', 'Temp 2m (°C)'],
          ['wind_speed_10m_ms', 'Wind 10m (m/s)'],
          ['precip_mm', 'Precip (mm)'],
          ['precip_probability_pct', 'Precip Prob (%)'],
          ['sunshine_duration_s_hour', 'Sunshine (hour, s)'],
        ];
        const el = document.getElementById('now-table');
        el.innerHTML = '';
        let lastTs = '-';
        for (const [k, label] of keys) {
          const p = now[k] || {};
          const v = p.value;
          const ts = p.ts_utc || '-';
          if (p.ts_utc) lastTs = p.ts_utc;
          el.innerHTML += `<tr><td class="key">${label}</td><td class="val">${fmt(v)}</td></tr>`;
        }
        document.getElementById('now-ts').textContent = `Last update: ${lastTs}`;
      }
      function renderDay(tableId, day) {
        const map = {
          ghi_daily_total_mj_m2: 'GHI Total (MJ/m²)',
          sunshine_duration_s: 'Sunshine (s)',
          precip_day_total_mm: 'Precip Total (mm)',
          temp_day_max_c: 'Temp Max (°C)'
        };
        const el = document.getElementById(tableId);
        el.innerHTML = '';
        for (const key in map) {
          const p = day[key] || {};
          el.innerHTML += `<tr><td class="key">${map[key]}</td><td class="val">${fmt(p.value)}</td></tr>`;
        }
      }
      function renderSeries(series) {
        const el = document.getElementById('series-table');
        el.innerHTML = '';
        (series || []).forEach(row => {
          el.innerHTML += `<tr><td class="key">${row.date_utc}</td><td class="val">${fmt(row.value)}</td></tr>`;
        });
        // draw simple bar chart
        const canvas = document.getElementById('series-canvas');
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0,0,canvas.width,canvas.height);
        const W = canvas.width; const H = canvas.height; const pad = 24;
        const data = (series || []).map(s => +s.value || 0);
        if (!data.length) return;
        const maxV = Math.max(...data) || 1;
        const barW = (W - pad*2) / data.length;
        ctx.strokeStyle = '#333';
        ctx.strokeRect(0.5, 0.5, W-1, H-1);
        ctx.fillStyle = '#4FC3F7';
        data.forEach((v, i) => {
          const h = (H - pad*2) * (v / maxV);
          const x = pad + i * barW + 2;
          const y = H - pad - h;
          ctx.fillRect(x, y, Math.max(2, barW - 4), h);
        });
        // axes labels (min)
        ctx.fillStyle = '#aaa';
        ctx.font = '12px sans-serif';
        ctx.fillText('0', 4, H - pad + 12);
        ctx.fillText(maxV.toFixed(1), 4, pad);
      }
      async function refresh() {
        try {
          const [now, daily] = await Promise.all([
            fetch('api/now').then(r => r.json()),
            fetch('api/daily').then(r => r.json()),
          ]);
          const nowMap = now.now || {};
          renderNow(nowMap);
          const nowIcon = iconSvg(classifyNow(nowMap));
          document.getElementById('now-icon').innerHTML = nowIcon;

          const dToday = daily.today || {};
          renderDay('today-table', dToday);
          document.getElementById('today-icon').innerHTML = iconSvg(classifyDay(dToday));

          const dTom = daily.tomorrow || {};
          renderDay('tomorrow-table', dTom);
          document.getElementById('tomorrow-icon').innerHTML = iconSvg(classifyDay(dTom));
          renderSeries(daily.series || []);
        } catch (e) { console.error(e); }
      }
      refresh();
      setInterval(refresh, 30000);
    </script>
  </body>
  </html>
"""


if __name__ == "__main__":
    main()
