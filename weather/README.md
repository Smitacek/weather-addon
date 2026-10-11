# Weather Add-on (Skeleton)

This is a Home Assistant add-on for weather + solar forecast data, modeled after the structure of `bms-reader-addon`. It targets PV yield optimization via derived solar features and daily/hourly logs. Panel azimuth is intentionally excluded and should be inferred by downstream modeling.

- Multi-arch builds via `build.yaml`
- Python-based container with `Dockerfile`
- Configurable options and schema via `config.yaml`
- Python entrypoint `main.py` with config reader `addon_config.py`
- Data contract and schemas under `CONTRACT.md` and `weather/schemas/`
- MQTT autodiscovery (extended): hourly now sensors (GHI/DNI/DHI, k_GHI, sun elevation/azimuth, cloud cover, temp, wind, precip, precip prob) and daily today/tomorrow summaries (GHI total, sunshine, precip total, temp max, cloud cover mean)

## Changelog

- 0.1.2
  - Add daily cloud_cover_day_mean_pct publication for Today/Tomorrow
  - Minor fixes and docs updates; tz-aware datetime handling
- 0.1.1
  - Extended MQTT autodiscovery and runtime publication
  - Orientation-agnostic design (removed panel azimuth from config/logs)
  - Open‑Meteo fetch + derived features + JSONL logging

Usage: install as a local add-on repository, configure options (provider, location, PV params, horizons), and start. Implementation of real weather fetching/publishing is intentionally left as TODO.

## Version 0.2.0: PV forecasts and observations

Enable `solar_enabled` and configure `pv_arrays` (id, capacity_kw, tilt_deg,
azimuth_deg clockwise from north). Optional fields: gamma_per_c=-0.004,
noct_c=45, loss_fraction=0.14, shading_factor=1, geometry_confirmed=false.
Old options keep solar disabled; legacy PV defaults are not silently migrated.

The model estimates available DC production using Open-Meteo plane irradiance,
PVWatts DC and a NOCT temperature approximation. It does not predict AC delivery
or constrain all DC production to the AC inverter limit. Configure real geometry
and losses; unconfirmed settings are shown in Dashboard. `conservative_factor`
is a scenario adjustment, not a confidence percentile.

Set timezone for local daily totals (e.g. Europe/Prague). Separate `telemetry_topics`
map MQTT scalar topics to pv1/pv2_power_w, voltage_v, current_a, ac_power_w,
battery1/battery2_soc and power_w, plus inverter/battery availability/connection.
Signed BMS power is positive when charging. Samples are saved every minute;
missing/stale/retained scalars are not valid measurements. Default unknown
operating limits and unknown plane mapping prevent automatic calibration.

SQLite `/data/solar.sqlite3` stores compressed forecast vintages and observations;
`solar_retention_days` defaults to 400. Preserve the database when backing up.
Weather JSONL retention remains separately configured. New HA kWh sensors are
forecasts, not cumulative meters, and must not be added as actual Energy production.
No night-tariff control or automatic battery charging is implemented.

Run tests: `python -m unittest discover -s tests -v` from repository root with
Weather, Dashboard and test requirements installed. See CONTRACT.md for v2 topics.
