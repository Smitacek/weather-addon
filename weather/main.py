#!/usr/bin/env python3
import logging
import sys
import time
import json
import datetime as dt

from addon_config import get_config
from providers.open_meteo import fetch_open_meteo
from compute import derive_hourly_features
from mqtt_helper import MQTTPublisher
from log_writer import append_jsonl, cleanup_logs


def setup_logging(level: str = "INFO"):
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format='[%(levelname)s] %(message)s', stream=sys.stdout)


def main() -> int:
    setup_logging("INFO")
    logging.info("🌦️  Weather Add-on starting (v0.1.2)")

    try:
        config = get_config()
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        return 1

    # Adjust log level per config
    try:
        level = getattr(logging, config.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(level)
    except Exception:
        pass

    logging.info("🔧 ===== CONFIGURATION SUMMARY =====")
    logging.info(f"Site: {getattr(config, 'site_id', 'default')}")
    logging.info(f"Location: lat={config.latitude}, lon={config.longitude}, elev={getattr(config, 'elevation_m', 0.0)} m, tz={getattr(config, 'timezone', 'UTC')}")
    logging.info(f"Provider: {config.provider} (model={getattr(config, 'provider_model', 'auto')})")
    logging.info(f"Units: {config.units}")
    logging.info(f"PV: capacity={getattr(config, 'pv_capacity_kw', 0.0)} kW, tilt={getattr(config, 'tilt_deg', 0.0)}°, inverter_limit={getattr(config, 'inverter_ac_limit_kw', 0.0)} kW (azimuth excluded)")
    logging.info(f"Forecast: days={getattr(config, 'forecast_days', 0)}, hourly_h={getattr(config, 'hourly_horizon_h', 0)}, nowcast={getattr(config, 'nowcast_enabled', False)} step={getattr(config, 'nowcast_step_s', 0)}s")
    logging.info(f"MQTT: enabled={getattr(config, 'mqtt_enabled', False)} host={getattr(config, 'mqtt_host', '')}:{getattr(config, 'mqtt_port', 0)} prefix={getattr(config, 'mqtt_topic_prefix', '')}")
    logging.info(f"Logging: lvl={getattr(config, 'log_level', 'INFO')} fmt={getattr(config, 'log_format', 'jsonl')} raw={getattr(config, 'log_raw', True)} features={getattr(config, 'log_features', True)} retention={getattr(config, 'log_retention_days', 0)}d version={getattr(config, 'data_version', '1.0')}")
    logging.info("🔧 ================================")

    # MQTT init (optional)
    mqtt = None
    if getattr(config, 'mqtt_enabled', False):
        try:
            mqtt = MQTTPublisher(
                host=config.mqtt_host,
                port=config.mqtt_port,
                username=config.mqtt_username,
                password=config.mqtt_password,
                topic_prefix=config.mqtt_topic_prefix,
                site_id=config.site_id,
            )
            ok = mqtt.connect(timeout=10, retries=3)
            logging.info(f"MQTT connected: {ok}")
            if ok and getattr(config, 'ha_discovery_enabled', False):
                try:
                    mqtt.publish_ha_discovery_extended()
                    logging.info("Published HA MQTT autodiscovery (extended set)")
                except Exception as e:
                    logging.warning(f"HA discovery publish failed: {e}")
        except Exception as e:
            logging.warning(f"MQTT init failed: {e}")
            mqtt = None

    # Main loop
    cycle = 0
    while True:
        cycle += 1
        logging.info(f"⏱️  Cycle #{cycle}: fetch + compute + publish + log")
        try:
            # Fetch provider data
            try:
                fc = fetch_open_meteo(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    hourly_horizon_h=config.hourly_horizon_h,
                    forecast_days=config.forecast_days,
                    units=config.units,
                )
                logging.info(f"Fetched Open-Meteo: hourly={len(fc['hourly'])}, daily={len(fc['daily'])}")
            except Exception as e:
                logging.error(f"Provider fetch error: {e}")
                time.sleep(config.update_interval)
                continue

            # Prepare common cfg snapshot
            cfg = {
                "pv_capacity_kw": config.pv_capacity_kw,
                "tilt_deg": config.tilt_deg,
                "albedo": config.albedo,
                "gamma_p_pct_per_c": config.gamma_p_pct_per_c,
                "noct_cell_temp_c": config.noct_cell_temp_c,
                "inverter_ac_limit_kw": config.inverter_ac_limit_kw,
            }

            # Derived hourly + logging + MQTT current-hour publish
            upcoming_hourly = []
            for h in fc["hourly"]:
                ts = dt.datetime.fromisoformat(h["ts_utc"].replace("Z", "+00:00"))
                derived = derive_hourly_features(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    ts_utc=ts,
                    cfg=cfg,
                    raw=h,
                )

                rec = {
                    "ts_utc": h["ts_utc"],
                    "provider": "open-meteo",
                    "provider_model": getattr(config, 'provider_model', 'auto'),
                    "site_id": config.site_id,
                    "latitude": config.latitude,
                    "longitude": config.longitude,
                    "timezone": config.timezone,
                    "data_version": config.data_version,
                    # RAW
                    **h,
                    # Derived
                    **derived,
                }

                # Log JSONL (hourly)
                if config.log_raw or config.log_features:
                    append_jsonl("hourly", rec, ts_field="ts_utc")

                upcoming_hourly.append(rec)

            # Compute daily aggregates from hourly derived (orientation-agnostic)
            daily_out = []
            by_day = {}
            for r in upcoming_hourly:
                day = r["ts_utc"][0:10]
                by_day.setdefault(day, []).append(r)

            for day, recs in by_day.items():
                # Integrate POA and estimate kWh
                ghi_mj_m2 = 0.0
                cloud_sum = 0.0
                sunshine_s = 0.0
                for r in recs:
                    ghi = float(r.get("ghi_w_m2", 0.0))
                    # hour integration (W/m2 * 3600 / 1e6)
                    ghi_mj_m2 += ghi * 3600.0 / 1e6
                    cloud_sum += float(r.get("cloud_cover_pct", 0.0))
                    sunshine_s += float(r.get("sunshine_duration_s_hour", 0.0))

                cloud_mean = cloud_sum / max(1, len(recs))
                # Map daily provider info
                dprov = next((d for d in fc["daily"] if d["date_utc"] == day), {})
                daily_rec = {
                    "date_utc": day,
                    "provider": "open-meteo",
                    "provider_model": getattr(config, 'provider_model', 'auto'),
                    "site_id": config.site_id,
                    "latitude": config.latitude,
                    "longitude": config.longitude,
                    "timezone": config.timezone,
                    "data_version": config.data_version,
                    "sunrise": dprov.get("sunrise"),
                    "sunset": dprov.get("sunset"),
                    "sunshine_duration_s": dprov.get("sunshine_duration_s") or sunshine_s,
                    "ghi_daily_total_mj_m2": ghi_mj_m2,
                    "temp_day_max_c": dprov.get("temp_day_max_c"),
                    "temp_day_min_c": dprov.get("temp_day_min_c"),
                    "cloud_cover_day_mean_pct": cloud_mean,
                    "precip_day_total_mm": dprov.get("precip_day_total_mm"),
                    "wind_day_max_ms": dprov.get("wind_day_max_ms"),
                    # PV config snapshot (azimuth excluded)
                    "pv_capacity_kw": config.pv_capacity_kw,
                    "tilt_deg": config.tilt_deg,
                    "albedo": config.albedo,
                    "gamma_p_pct_per_c": config.gamma_p_pct_per_c,
                    "noct_cell_temp_c": config.noct_cell_temp_c,
                    "inverter_ac_limit_kw": config.inverter_ac_limit_kw,
                }
                if config.log_raw or config.log_features:
                    append_jsonl("daily", daily_rec, ts_field="date_utc")
                daily_out.append(daily_rec)

            # MQTT publish (subset): current hour key metrics and daily GHI series
            if mqtt and mqtt.connected:
                try:
                    # current hour (closest >= now)
                    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
                    cur = None
                    for r in upcoming_hourly:
                        ts = dt.datetime.fromisoformat(r["ts_utc"].replace("Z", "+00:00"))
                        if ts >= now:
                            cur = r
                            break
                    if cur:
                        # Hourly now metrics (extended)
                        publish = mqtt.publish_json
                        publish("hourly/ghi_w_m2", {"ts_utc": cur["ts_utc"], "value": cur.get("ghi_w_m2", 0.0)})
                        publish("hourly/dni_w_m2", {"ts_utc": cur["ts_utc"], "value": cur.get("dni_w_m2", 0.0)})
                        publish("hourly/dhi_w_m2", {"ts_utc": cur["ts_utc"], "value": cur.get("dhi_w_m2", 0.0)})
                        publish("hourly/k_ghi", {"ts_utc": cur["ts_utc"], "value": cur.get("k_ghi", 0.0)})
                        publish("hourly/sun_elevation_deg", {"ts_utc": cur["ts_utc"], "value": cur.get("sun_elevation_deg", 0.0)})
                        publish("hourly/sun_azimuth_deg", {"ts_utc": cur["ts_utc"], "value": cur.get("sun_azimuth_deg", 0.0)})
                        publish("hourly/cloud_cover_pct", {"ts_utc": cur["ts_utc"], "value": cur.get("cloud_cover_pct", 0.0)})
                        publish("hourly/temp_2m_c", {"ts_utc": cur["ts_utc"], "value": cur.get("temp_2m_c", 0.0)})
                        publish("hourly/wind_speed_10m_ms", {"ts_utc": cur["ts_utc"], "value": cur.get("wind_speed_10m_ms", 0.0)})
                        publish("hourly/precip_mm", {"ts_utc": cur["ts_utc"], "value": cur.get("precip_mm", 0.0)})
                        publish("hourly/precip_probability_pct", {"ts_utc": cur["ts_utc"], "value": cur.get("precip_probability_pct", 0.0)})
                        publish("hourly/sunshine_duration_s_hour", {"ts_utc": cur["ts_utc"], "value": cur.get("sunshine_duration_s_hour", 0.0)})

                    # daily GHI total as series (orientation-agnostic energy proxy)
                    series = [{"date_utc": d["date_utc"], "value": d.get("ghi_daily_total_mj_m2", 0.0)} for d in daily_out]
                    mqtt.publish_json("daily/ghi_daily_total_mj_m2", {"series": series}, retain=True)

                    # today/tomorrow single-value topics for HA sensors
                    today = dt.datetime.utcnow().date().isoformat()
                    tomorrow = (dt.datetime.utcnow().date() + dt.timedelta(days=1)).isoformat()
                    def find_day(key):
                        return next((x for x in daily_out if x["date_utc"] == key), None)
                    d_today = find_day(today)
                    d_tom = find_day(tomorrow)
                    def pub_day(prefix: str, d: dict):
                        if not d:
                            return
                        publish = mqtt.publish_json
                        publish(f"daily/{prefix}/ghi_daily_total_mj_m2", {"date_utc": d["date_utc"], "value": d.get("ghi_daily_total_mj_m2", 0.0)}, retain=True)
                        publish(f"daily/{prefix}/sunshine_duration_s", {"date_utc": d["date_utc"], "value": d.get("sunshine_duration_s", 0.0)}, retain=True)
                        publish(f"daily/{prefix}/precip_day_total_mm", {"date_utc": d["date_utc"], "value": d.get("precip_day_total_mm", 0.0)}, retain=True)
                        publish(f"daily/{prefix}/temp_day_max_c", {"date_utc": d["date_utc"], "value": d.get("temp_day_max_c", 0.0)}, retain=True)
                        publish(f"daily/{prefix}/cloud_cover_day_mean_pct", {"date_utc": d["date_utc"], "value": d.get("cloud_cover_day_mean_pct", 0.0)}, retain=True)
                    pub_day("today", d_today)
                    pub_day("tomorrow", d_tom)
                except Exception as e:
                    logging.warning(f"MQTT publish failed: {e}")

            # Cleanup logs periodically
            try:
                cleanup_logs(getattr(config, 'log_retention_days', 90))
            except Exception:
                pass

        except Exception as e:
            logging.error(f"Cycle error: {e}")

        time.sleep(config.update_interval)

    return 0


if __name__ == "__main__":
    sys.exit(main())
