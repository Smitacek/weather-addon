# Weather Dashboard 0.2.1

Existing HA ingress application for Weather forecasts and observed PV telemetry.
Uses the existing MQTT broker and site topics; no external chart CDN.

## Solar overview

- Hourly available DC power forecast for up to 72 hours, separate PV planes and sum.
- Tomorrow/day-after-tomorrow kWh and conservative scenario; missing data shows —.
- Remaining today is calculated from now to local midnight, not a full-day total.
- Last six hours of measured FV1/FV2 power or voltage, plus current voltage/current.
- Forecast age, archive health, unconfirmed geometry and physical-plane mapping.
- Quality and previous-issue comparison coverage. No automatic battery charge control.

`GET /api/solar` returns profile, health, observations, six-hour series and evaluation.
Stale retained forecast profiles are rejected as live even when broker connection works.
The actual UI is `web/index.html` + `web/dashboard.js`, served at relative `static/`
URLs compatible with HA ingress. Existing `/api/now` and `/api/daily` remain.

PV plane azimuths are expressed clockwise from north in Weather configuration.
FV1/FV2 are physical inverter inputs, not automatically equivalent to JJZ/JV.
