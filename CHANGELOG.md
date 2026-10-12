# Weather and Dashboard 0.4.0 — 2026-10-12

- Show interval-average expected DC power from now until local midnight, with remaining energy and the highest future hourly average. Missing intervals stay gaps; step segments preserve energy.
- Compare D−1/D−2/D−3 previous-evening22:00 forecasts against the same measured local day and its hours. Default/deployed horizon96h covers the full third day.
- Add hourly MAE/bias/sample counts and advisory correction factors, with conservative quality gating and evaluation on later, disjoint days. No automatic calibration or charging changes.
- Preserve existing archived measurements and upgrade daily caches; retain400-day daily analysis and keep full hourly data in SQLite, limiting MQTT/UI hourly detail to31 days.

# Weather and Dashboard 0.3.0 — 2026-10-12

- Add Odhad vs. skutečnost panel with day, ISO week and calendar month navigation.
- Freeze each day against the last archived forecast before 22:00 on the previous local evening; later revisions never replace its baseline.
- Compare today's elapsed interval, expose missing history, coverage, net error and daily MAE. Zero forecast does not generate a percentage.
- Flag suspected/confirmed curtailment independently from measured error; calibration eligibility remains conservative.
- Preserve DST 23/25-hour days and cache closed daily comparisons without changing existing archive schema version or measurement sensor identities.

# Dashboard 0.2.2 — 2026-10-11

- Reduce chart time-axis labels on narrow mobile screens to prevent overlapping dates. Weather remains 0.2.1.

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
