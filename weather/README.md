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
