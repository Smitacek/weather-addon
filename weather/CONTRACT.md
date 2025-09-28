# Weather Add-on Data Contract

This document defines the MQTT topic naming and JSONL log record schemas used by the Weather add-on for PV yield optimization. It is provider-agnostic and designed to be stable for downstream model training and analytics.

## Identity and Conventions
- Time: `ts_utc` in ISO 8601 UTC (e.g., `2025-09-28T10:00:00Z`).
- Units: SI by default (W/m², m/s, °C, hPa). Energy in kWh, radiation integrals in MJ/m².
- Site identity: `site_id` (string), location `latitude`, `longitude`, optional `elevation_m`, `timezone`.
- Data versioning: `data_version` string for backward compatibility.

## MQTT Topics
- Base prefix: `<mqtt_topic_prefix>` (default: `weather`).
- Site prefix: `<mqtt_topic_prefix>/<site_id>`.

Published classes:
- Nowcast (5–15 min steps): `<prefix>/<site_id>/nowcast/<metric>`
- Hourly forecast: `<prefix>/<site_id>/hourly/<metric>`
- Daily forecast: `<prefix>/<site_id>/daily/<metric>`
- Meta (status/version): `<prefix>/<site_id>/meta/<key>`

Metric names (subset, extendable):
- Solar geometry: `sun_elevation_deg`, `sun_azimuth_deg`, `sun_zenith_deg`
- Radiation (global/direct/diffuse): `ghi_w_m2`, `dni_w_m2`, `dhi_w_m2`, `shortwave_radiation_w_m2`
- Clear-sky: `ghi_cs_w_m2`, `dni_cs_w_m2`, `dhi_cs_w_m2`, `k_ghi`, `k_dni`
- Weather: `cloud_cover_pct`, `temp_2m_c`, `dew_point_c`, `relative_humidity_pct`, `wind_speed_10m_ms`, `wind_gust_10m_ms`, `wind_dir_10m_deg`, `precip_mm`, `precip_probability_pct`, `mslp_hpa`, `visibility_m`
- Daily aggregates: `sunshine_duration_s`, `ghi_daily_total_mj_m2`, `temp_day_max_c`, `temp_day_min_c`, `cloud_cover_day_mean_pct`, `precip_day_total_mm`, `wind_day_max_ms`

Notes:
- For nowcast/hourly series, publish timestamped payloads containing value(s) and `ts_utc`. Retain is typically off; daily aggregates may use retain.
- Availability (LWT): `<prefix>/<site_id>/availability` with `online`/`offline`.
 - Convenience topics for HA sensors:
   - Hourly "now" metrics at `<prefix>/<site_id>/hourly/<metric>` with payload `{ts_utc, value}`
   - Daily single-values at `<prefix>/<site_id>/daily/{today|tomorrow}/<metric>` with payload `{date_utc, value}` (retained). Metrics include: `ghi_daily_total_mj_m2`, `sunshine_duration_s`, `precip_day_total_mm`, `temp_day_max_c`, `cloud_cover_day_mean_pct`.

## Log Files and Layout
- Directory: `/data/logs/`
- Files:
  - Nowcast: `nowcast_YYYYMMDD.jsonl`
  - Hourly: `hourly_YYYYMMDD.jsonl`
  - Daily: `daily_YYYY.jsonl`
- Rotation: configurable `log_retention_days` (default 90).

## JSONL Record Schemas
Formal JSON Schemas live in `weather/schemas/*.schema.json`. Summaries below.

### Nowcast Record (5–15 min)
Required fields:
- `ts_utc` (string, ISO 8601), `provider` (string), `site_id` (string), `latitude` (number), `longitude` (number), `timezone` (string), `data_version` (string)
- `issue_time_utc` (string, ISO 8601), `step_s` (integer), `lead_time_min` (integer)

Typical features:
- Solar geometry; GHI/DNI/DHI and clear-sky; POA; weather; PV estimates; quality flags: `source_quality` (string), `missing_fields` (array), `filled_by` (string)

### Hourly Record (intra-day to 72 h)
Required fields:
- `ts_utc`, `provider`, `site_id`, `latitude`, `longitude`, `timezone`, `data_version`
- `lead_time_min` (integer) or `forecast_hour` (integer)

Typical features:
- Same feature family as nowcast; optional `sunshine_duration_s_hour` (computed via thresholding GHI).

### Daily Record (aggregates 1 day)
Required fields:
- `date_utc` (string, `YYYY-MM-DD`), `provider`, `site_id`, `latitude`, `longitude`, `timezone`, `data_version`

Typical features:
- `sunshine_duration_s`, `ghi_daily_total_mj_m2`, `temp_day_max_c`, `temp_day_min_c`, `cloud_cover_day_mean_pct`, `precip_day_total_mm`, `wind_day_max_ms`

## PV System Metadata in Records
Embed PV config snapshot to ensure reproducibility (panel azimuth excluded by design):
- `pv_capacity_kw`, `tilt_deg`, `albedo`, `gamma_p_pct_per_c`, `noct_cell_temp_c`, `inverter_ac_limit_kw`

## Example Hourly Record
```json
{
  "ts_utc": "2025-09-28T10:00:00Z",
  "provider": "open-meteo",
  "site_id": "default",
  "latitude": 50.1,
  "longitude": 14.4,
  "timezone": "Europe/Prague",
  "data_version": "1.0",
  "lead_time_min": 60,
  "sun_elevation_deg": 32.5,
  "sun_azimuth_deg": 170.2,
  "ghi_w_m2": 540.0,
  "dni_w_m2": 680.0,
  "dhi_w_m2": 110.0,
  "ghi_cs_w_m2": 780.0,
  "k_ghi": 0.69,
  "temp_2m_c": 18.3,
  "wind_speed_10m_ms": 3.2,
  "cloud_cover_pct": 30.0,
  "pv_capacity_kw": 3.0,
  "tilt_deg": 35.0
}
```

## Backward/Forward Compatibility
- Increment `data_version` when changing field names or semantics.
- Prefer adding optional fields over changing existing ones.
