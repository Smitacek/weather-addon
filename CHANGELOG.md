# 0.2.1 — 2026-10-11

- Retain timestamped hourly weather in MQTT so a restarted Dashboard immediately receives the last valid issue. Existing freshness expiry continues to reject stale weather.
- Verified during HA deployment; regression test reproduces the missing restart data.

# 0.2.0 — 2026-10-11

- Existing Weather + Dashboard extended for multiple PV planes and 72-hour available DC production forecasts.
- Correct DNI, preceding-hour radiation intervals, local daily totals and DST.
- Immutable SQLite forecast vintages, minute observations including PV voltage/current, six-hour charts and coverage-aware evaluation.
- HA forecast sensors use correct energy/power semantics; actual Energy meters unchanged.
- Stale forecasts, MQTT outages, rejected retained telemetry and independent archive health diagnostics.
- Independent review findings fixed with regression tests. No inverter command/control or automatic calibration.
- New solar functionality is opt-in with explicit PV plane configuration; legacy weather identities preserved.
