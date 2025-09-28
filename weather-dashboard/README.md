# Weather Dashboard Add-on

Ingress UI that subscribes to MQTT topics published by the Weather add-on and shows a compact overview of current conditions and daily forecast, with icons and a simple GHI bar chart.

- Ingress: FastAPI on port 8099 (exposed via HA Ingress)
- Subscribes to `<topic_prefix>/<site_id>/*` topics
- Displays: hourly now metrics (GHI/DNI/DHI, k_GHI, sun elevation/azimuth, cloud cover, temp, wind, precip, precip prob) and daily GHI + today/tomorrow summaries
- Icons: clear / partly / cloudy / rain (heuristics from precip + cloud cover)
- Graphs: bar chart for daily GHI series

## Configuration

See `config.yaml` for options: MQTT host/port/credentials, `topic_prefix`, `site_id`, `log_level`.

## Notes

- Works best with the companion Weather add-on in this repository.
- No persistent storage; UI reflects latest MQTT values; daily series is taken from `daily/ghi_daily_total_mj_m2` series payload.

## Changelog

- 0.1.1: add bar chart and weather icons; today/tomorrow cloud cover consumption
- 0.1.0: initial version
