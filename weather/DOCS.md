# Weather Add-on Docs (Skeleton)

This add-on mirrors the structure of `bms-reader-addon` and provides a starting point for a weather + solar forecast publisher aimed at PV yield optimization.

Key configuration options (see `config.yaml` for full schema):

```yaml
site_id: "default"
latitude: 50.1
longitude: 14.4
elevation_m: 250
timezone: "Europe/Prague"

provider: "open-meteo"           # or "openweathermap"
provider_model: "auto"
api_key: ""
units: "metric"

pv_capacity_kw: 3.0
tilt_deg: 35.0
albedo: 0.2
gamma_p_pct_per_c: -0.4
noct_cell_temp_c: 45.0
inverter_ac_limit_kw: 3.0

forecast_days: 7
hourly_horizon_h: 72
nowcast_enabled: false
nowcast_step_s: 900

update_interval: 300
log_level: info
log_raw: true
log_features: true
log_retention_days: 90
log_format: jsonl
data_version: "1.0"

mqtt_enabled: true
mqtt_host: "core-mosquitto"
mqtt_port: 1883
mqtt_username: ""
mqtt_password: ""
mqtt_topic_prefix: "weather"
ha_discovery_enabled: true
```

At this stage, `main.py` only logs cycles at the configured interval. Hook in real fetching and publishing logic as needed (e.g., MQTT publication and JSONL logging).

Note: panel azimuth is intentionally excluded from configuration and logs; downstream modeling will infer effective orientation from time series and yield.

See `CONTRACT.md` for the data contract (MQTT topics and JSONL schemas). Formal JSON Schemas are under `weather/schemas/`.

Autodiscovery
- Enable via `ha_discovery_enabled: true` (default).
- Sensors published (extended set):
  - Hourly now: GHI, DNI, DHI (W/m²), k_GHI, Sun Elevation (°), Sun Azimuth (°), Cloud Cover (%), Temp 2m (°C), Wind 10m (m/s), Precip (mm), Precip Prob (%)
  - Daily (single-value): Today/Tomorrow GHI total (MJ/m²), Sunshine (s), Precip total (mm), Temp Max (°C)
