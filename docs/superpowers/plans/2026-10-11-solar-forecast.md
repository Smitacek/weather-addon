# Solar Forecast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development if the user selects delegation. Steps use checkbox syntax.

**Goal:** Předpověď dostupného DC výkonu dvou FV polí na 72 hodin, archiv vydání a skutečných průběhů včetně napětí a proudů.

**Architecture:** Výpočet a SQLite archiv vlastní Weather. MQTT přenáší profil a souhrn hodnocení do stávajícího Weather Dashboard. Sběr EASUN/BMS pouze čte MQTT, řízení měniče se nepřidává.

**Tech Stack:** Python 3.11, requests, Astral, paho-mqtt, SQLite, zoneinfo, FastAPI, unittest; žádné numpy/scipy.

**Spec:** `docs/superpowers/specs/2026-10-11-solar-forecast-design.md` (uživatelem schváleno 11. 10. 2026).

## Global Constraints

- Weather i Dashboard plánované verze 0.2.0; slugy a existující unique_id zachovat.
- Kapacity 3,5 + 3,5 kWp, návrhové azimuty 202,5° a 135° od severu.
- Sklon 90° explicitně nepotvrzený; mapování FV1/FV2 nepotvrzené.
- Europe/Prague pro dny, UTC pro uložené intervaly a vydání.
- Předpověď není naměřená energie: kWh s energy, bez state_class.
- Nový archiv `/data/solar.sqlite3`, retence 400 dní; původní logy 90 dní.
- Chybějící/stará telemetrie není nula; neintegrovat přes výpadek.
- Bez automatické kalibrace, řízení nabíjení a změn HomeKitu či HA Energy.
- Zpětná konfigurace bez zapnutého PV modelu zachová počasí.

## Review Focus

1. Krátké či poškozené pole z API: nevyrobit neúplný den jako platné kWh (Task 1/2).
2. Nesoulad GTI odpovědí dvou požadavků: spojovat podle intervalu, ne indexu (Task 1).
3. Retained MQTT a pořadí zpráv: nenazvat staré hodnoty čerstvým vzorkem (Task 3).
4. Selhání archivu nebo plný disk: předpověď pokračuje s viditelnou chybou sběru (Task 2/4).
5. Dřívější předpověď a novější revize: hodnocení nikdy nepoužije budoucí informaci (Task 2).

## Ověřovací prostředí

Příkazy z kořene repo; izolované testové prostředí `.venv` a fixtures bez souřadnic domácnosti.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r weather/requirements.txt -r weather-dashboard/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q weather weather-dashboard
git diff --check
```

Testy modelu a archivu mohou běžet bez síťových závislostí systémovým Pythonem.
`tests/__init__.py` a `tests/helpers.py` připraví importy souborů doplňků bez
spuštění jejich main loop; všechny cesty `/data` se v testech nahrazují dočasnými.

### Task 1: Konfigurace a fyzikální profil

**Files:** Modify `weather/addon_config.py`, `weather/config.yaml`,
`weather/providers/open_meteo.py`; create `weather/solar_model.py`,
`tests/test_solar_model.py`, `tests/test_solar_provider.py`, `tests/test_config.py`.

**Interfaces:** `normalize_arrays(options: dict) -> list[dict]`;
`dc_power_w(poa_w_m2: float, temp_c: float, array: dict) -> float`;
`build_profile(hourly: list[dict], arrays: list[dict], issued_at: datetime,
timezone: str, horizon_h: int = 72) -> dict`.
Provider returns UTC interval boundaries, SI weather and GTI keyed by array ID.
Array dict includes id, capacity_kw, tilt_deg, azimuth_deg, gamma_per_c,
noct_c, loss_fraction, shading_factor and geometry_confirmed.

- [ ] Write failing unit tests, including this fixed physical case:

```python
def test_dc_stc_case(self):
    a = dict(capacity_kw=3.5, gamma_per_c=-0.004, noct_c=20,
             loss_fraction=0.14, shading_factor=1)
    self.assertAlmostEqual(dc_power_w(1000, 25, a), 3010)
```

- [ ] Run `python3 -m unittest tests.test_solar_model -v`; verify missing implementation failure.
- [ ] Add new optional `solar_enabled`, `pv_arrays`, `solar_retention_days`,
  `conservative_factor` and MQTT telemetry options; validate finite numbers,
  latitude/longitude, timezone, horizon and unique array IDs. Read options through
  an injectable file path. Old options leave solar disabled; never invent an azimuth.
- [ ] Implement the documented DC equation, NOCT approximation and north/south azimuth conversion.
  API calls remain in provider, pure model functions have no network side effects.
- [ ] Replace horizontal-direct-as-DNI mapping with true DNI, request GTI separately
  per geometry, normalize SI and use explicit interval-end radiation semantics.
  Reject malformed lengths, nonfinite values or unsupported provider/model settings.
- [ ] Test missing GTI, shifted timestamps between responses, null/NaN, night zero,
  valid super-STC input, west/east conversion, HTTP timeout and invalid options.
  Daily splitting uses UTC boundary instants derived with zoneinfo; test Prague
  2026-03-29 = 23 h and 2026-10-25 = 25 h, midnight and partial current hour.
- [ ] Run Task 1 tests and commit model/provider/config changes.

### Task 2: Trvalý archiv a hodnocení vydání

**Files:** Create `weather/solar_archive.py`, `tests/test_solar_archive.py`;
modify `weather/Dockerfile` to include new modules.

**Interfaces:** `SolarArchive(path: str)` exposes `save_forecast(profile: dict)`,
`save_observation(sample: dict)`, `forecast_before(start_utc: str, lead_h: int) -> dict | None`,
`hourly_actual(start_utc: str, end_utc: str) -> dict`,
`evaluation_summary(now_utc: str) -> dict`, `cleanup(now_utc: str, retention_days: int)`.
All timestamps are timezone-aware UTC. The archive owns transactions and schema version.

- [ ] Write failing test for historical selection:

```python
def test_no_future_revision_leak(self):
    self.archive.save_forecast(profile('2026-10-11T08:00:00Z', 1000))
    self.archive.save_forecast(profile('2026-10-11T11:00:00Z', 3000))
    f = self.archive.forecast_before('2026-10-11T10:00:00Z', lead_h=1)
    self.assertEqual(f['arrays']['jjz']['power_w'], 1000)
```

Here fixture `profile(issued_at, power_w)` returns a complete profile with target
interval `[10:00Z,11:00Z)` and both arrays; it is defined in `tests/helpers.py`.

- [ ] Run archive tests; verify missing class failure.
- [ ] Create schema metadata, forecast issues/intervals and observation tables.
  Use SQLite WAL, bounded connection timeout, transactions and foreign keys.
  Store complete immutable configuration snapshots with each issue.
- [ ] Implement earliest appropriate historical issue selection for each lead bucket;
  independently integrate left-held measured power with capped valid intervals.
  Track time coverage per metric/array, never extrapolate through stale gaps.
- [ ] Test restarts, atomic failed writes, duplicate issue IDs, retention boundaries,
  corrupt/wrong schema, database write error, partial-hour observation coverage and
  loss of one PV input. Errors propagate to coordinator diagnostics.
- [ ] Run archive tests and commit persistence.

### Task 3: MQTT telemetrie a kvalita vzorků

**Files:** Create `weather/solar_telemetry.py`, `tests/test_solar_telemetry.py`;
modify `weather/mqtt_helper.py` only to wire MQTT reception.

**Interfaces:** `TelemetryCollector(topic_map: dict, max_age_s: int = 90)` exposes
`ingest(topic: str, payload: bytes, received_at: datetime, retained: bool = False)`
and `snapshot(now: datetime) -> dict`. Snapshot includes values, per-field ages,
availability, reception timestamps, quality and reasons. Explicit topic_map avoids
guessing names from display entity labels.

- [ ] Write and run failing test that retained scalar PV power after startup gives
  `values['pv1_power_w'] is None` until a fresh non-retained update arrives.
- [ ] Implement ingestion of PV1/PV2 voltage/current/power, AC power, BMS SoC/power,
  inverter mode/charge stage and all relevant connection/device availability topics.
  Validate numeric finite values; tolerate unknown fields without executing payloads.
- [ ] Test offline availability invalidating values, disconnect, malformed bytes,
  stale source timestamp, out-of-order data, partial BMS bank and 60-second sampling.
- [ ] Implement cautious classification. Missing essential data -> missing;
  explicit curtailment -> confirmed_curtailed; high SoC + negligible charge with
  low load -> suspected_curtailed; incomplete operating-limit evidence -> ambiguous.
  Eligible requires explicit configured operating limits and adequate telemetry
  evidence; default unknown limits never imply eligible. No forecast-error criterion.
- [ ] Test low load plus active charging is not curtailed, and high PV voltage
  alone is not proof. Keep reported power authoritative until current semantics are
  checked; do not reconstruct power from an unverified protocol field.
- [ ] Run tests and commit telemetry collection.

### Task 4: Forecast lifecycle, HA discovery a migrační kontrakt

**Files:** Modify `weather/main.py`, `weather/mqtt_helper.py`, `weather/compute.py`,
`weather/CONTRACT.md`, schemas, Dockerfile and docs;
create `weather/solar_service.py`, `tests/test_solar_service.py`, `tests/test_solar_mqtt.py`.

**Interfaces:** `SolarService(config, publisher, archive, collector)` exposes
`update_forecast(now: datetime)`, `sample(now: datetime)`, `health(now: datetime) -> dict`.
Main schedules weather acquisition at existing cadence and sampling every 60 s.
`publish_solar(profile: dict, health: dict, evaluation: dict)` emits version 2 topics.

- [ ] Write failing MQTT discovery test:

```python
def test_forecast_energy_is_not_total(self):
    cfg = solar_discovery('tomorrow_energy_kwh', site_id='default', ttl_s=900)
    self.assertEqual(cfg['device_class'], 'energy')
    self.assertEqual(cfg['unit_of_measurement'], 'kWh')
    self.assertNotIn('state_class', cfg)
```

`solar_discovery(metric: str, site_id: str, ttl_s: int) -> dict` is defined in MQTT helper.

- [ ] Run failing tests, then wire acquisition -> model -> archive -> MQTT using
  explicit quality statuses. Use a monotonic sampling schedule; never lock the MQTT
  callback during DB work. Restore current historical forecast metadata on startup.
- [ ] Weather acquisition timeout must not indefinitely block telemetry sampling.
  Use a bounded single acquisition worker while main owns archive writes; snapshots
  pass through a synchronized queue. One in-flight acquisition, no accumulating jobs.
- [ ] Implement solar-specific availability, TTL = 3 × update_interval, retained
  profile with immutable issue ID, local daily fields and diagnostics. Refresh
  discovery after `homeassistant/status=online`; check publish rc, not just exceptions.
- [ ] Keep existing weather unique IDs; correct DNI semantics and local daily GHI
  explicitly in contract v2, distinguish remaining-today vs full-day estimate.
  Serialize strict JSON (`allow_nan=False`). Configure paho compatible APIs and pin
  dependency ranges rather than relying on unbounded breaking upgrades.
- [ ] Test provider failure while MQTT stays online, recovery, fresh scalar but stale
  profile, archive failure, worker timeout, sampling persistence, and optional PV off.
- [ ] Run full suite and commit service/contracts.

### Task 5: Dashboard se skutečnými daty

**Files:** Modify `weather-dashboard/main.py`, `weather-dashboard/mqtt_listener.py`,
`weather-dashboard/web/dashboard.js`, `weather-dashboard/web/index.html`,
`weather-dashboard/README.md`; create `tests/test_solar_dashboard.py`.

**Interfaces:** Store snapshot gains `solar`, `solar_health`, `solar_evaluation`;
`GET /api/solar` returns those fields. Serve one actual UI source; remove disconnected
duplicate chart logic rather than documenting an unused JS file as working.

- [ ] Write and run failing API test using an injected DataStore with stale solar
  profile; response identifies stale status and UI must not show it as fresh.
- [ ] Subscribe to documented solar topics, validate JSON/schema and bound series
  length. Store lock protects coherent snapshots. Existing weather API remains usable.
- [ ] Implement two-array + sum chart, daily cards, actual observed output and
  diagnostics for mapping/geometry assumptions, quality, archive and forecast age.
  Render labels through textContent; no payload HTML injection. Use relative ingress
  paths and bundled graph rendering without a new external CDN dependency.
- [ ] Test empty store, malformed/oversized profile, older issue arriving after newer,
  unconfirmed mapping and no observation coverage. Check desktop/mobile in browser
  against deterministic fixture and real MQTT, never substitute demo results for live.
- [ ] Run suite, capture browser proof and commit dashboard.

### Task 6: Vydání a ověřené nasazení

**Files:** Both config.yaml/version/readme files; original source release notes;
`/home/smetalaj/projects/home/house/HA_MAP.md` and deployment evidence.

- [ ] Run full deterministic suite, compileall and diff check; record logs.
- [ ] Review whole diff against approved spec; reproduce substantive findings.
  External GLM review cannot currently run: `codex-glm doctor` fails sandbox process
  spawning (EPERM); no project opt-in and no private repository data was exported.
  Resolve review locally or request explicit scope for external review if needed.
- [ ] Set Weather/Weather Dashboard 0.2.0 consistently after tests, including startup
  log and discovery version. Build compatible images for HA architecture.
- [ ] Back up deployed options and data, inspect concrete MQTT source topics and
  enable 3.5/3.5 kWp configuration. Preserve geometry/mapping uncertainty flags.
- [ ] Publish tested origin changes, update repository in HA and update both existing
  addons. Confirm fresh forecast, sample append, hourly coverage and persistence
  after addon restart; no core restart solely for forecast activation.
- [ ] Capture Dashboard and HA entity proof. Update map with actual installed versions,
  assumptions, source paths, backup/rollback location and history start time.
- [ ] If startup/regression fails, restore prior version/options and preserve new
  archive for investigation. Declare success only after end-to-end verification.

## Execution Handoff

Recommendation: native execution in this chat, because model, archive, telemetry and
MQTT lifecycle share interfaces and deployment needs one owner. The user must review
this written plan and choose native execution or delegated task execution before code
implementation, per writing-plans. No product code has been changed at this stage.
