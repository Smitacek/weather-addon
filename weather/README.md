# Weather Add-on (Skeleton)

This is a skeleton Home Assistant add-on for weather + solar forecast data, modeled after the structure of `bms-reader-addon`. It targets PV yield optimization via derived solar features and daily/hourly logs. Panel azimuth is intentionally excluded and should be inferred by downstream modeling.

- Multi-arch builds via `build.yaml`
- Python-based container with `Dockerfile`
- Configurable options and schema via `config.yaml`
- Python entrypoint `main.py` with config reader `addon_config.py`
- Data contract and schemas under `CONTRACT.md` and `weather/schemas/`
- MQTT autodiscovery (extended): hourly now sensors (GHI/DNI/DHI, k_GHI, sun elevation/azimuth, cloud cover, temp, wind, precip, precip prob) and daily today/tomorrow summaries

Usage: install as a local add-on repository, configure options (provider, location, PV params, horizons), and start. Implementation of real weather fetching/publishing is intentionally left as TODO.
