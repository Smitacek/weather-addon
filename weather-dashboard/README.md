# Weather Dashboard 0.2.2

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

## Odhad vs. skutečnost (0.3.0)
Switch to the comparison panel and choose day/week/month and a date. Weeks start Monday and months follow the local calendar. Energy cards show available measurements and corresponding elapsed forecasts, while error and MAE use only comparable days. Missing days are explicit. The API `/api/comparison?period=day|week|month&date=YYYY-MM-DD` serves these aggregates from the retained archive report. Historical comparisons are marked stale after 15 minutes without a new report. No measured energy sensor identities or charging controls are changed.

## Today's remaining power (0.4.0)
The new power graph clips forecast intervals to the current instant and the next local midnight, with timezone/DST boundaries. Hourly means are displayed as horizontal steps, preserving integrated energy; missing values break lines and incomplete coverage keeps the remaining energy unknown. It shows availableDC power, not guaranteed inverter output. Comparison accepts `lead=1|2|3`, exposes per-horizon hourly errors/counts and advisory recommendations, and preserves D−1 compatibility.

### Dashboard 0.4.1

Versioned script URLs invalidate browser caches on upgrade, so the remaining-day graph and forecast lead controls load immediately.
