#!/usr/bin/env python3
"""
Simplified configuration loader for Weather Add-on
Mirrors structure from bms-reader-addon (reads /data/options.json)
"""

import json
from pathlib import Path


class Config:
    def __init__(self):
        self.load_config()

    def load_config(self):
        options = self.load_addon_options()

        # Identity & location
        self.site_id = options.get("site_id", "default")
        self.latitude = float(options.get("latitude", 0.0))
        self.longitude = float(options.get("longitude", 0.0))
        self.elevation_m = float(options.get("elevation_m", 0.0))
        self.timezone = options.get("timezone", "UTC")

        # Provider
        self.provider = options.get("provider", "open-meteo")
        self.provider_model = options.get("provider_model", "auto")
        self.api_key = options.get("api_key", "")
        self.units = options.get("units", "metric")

        # PV system parameters
        self.pv_capacity_kw = float(options.get("pv_capacity_kw", 3.0))
        self.tilt_deg = float(options.get("tilt_deg", 35.0))
        self.albedo = float(options.get("albedo", 0.20))
        self.gamma_p_pct_per_c = float(options.get("gamma_p_pct_per_c", -0.4))
        self.noct_cell_temp_c = float(options.get("noct_cell_temp_c", 45.0))
        self.inverter_ac_limit_kw = float(options.get("inverter_ac_limit_kw", self.pv_capacity_kw))

        # Horizons & cadence
        self.forecast_days = int(options.get("forecast_days", 7))
        self.hourly_horizon_h = int(options.get("hourly_horizon_h", 72))
        self.nowcast_enabled = bool(options.get("nowcast_enabled", False))
        self.nowcast_step_s = int(options.get("nowcast_step_s", 900))

        # App & logging
        self.update_interval = int(options.get("update_interval", 300))
        self.log_level = str(options.get("log_level", "INFO")).upper()
        self.log_raw = bool(options.get("log_raw", True))
        self.log_features = bool(options.get("log_features", True))
        self.log_retention_days = int(options.get("log_retention_days", 90))
        self.log_format = options.get("log_format", "jsonl")
        self.data_version = options.get("data_version", "1.0")

        # MQTT
        self.mqtt_enabled = bool(options.get("mqtt_enabled", True))
        self.mqtt_host = options.get("mqtt_host", "core-mosquitto")
        self.mqtt_port = int(options.get("mqtt_port", 1883))
        self.mqtt_username = options.get("mqtt_username", "")
        self.mqtt_password = options.get("mqtt_password", "")
        self.mqtt_topic_prefix = options.get("mqtt_topic_prefix", "weather")
        self.ha_discovery_enabled = bool(options.get("ha_discovery_enabled", False))

    def load_addon_options(self):
        options_file = Path("/data/options.json")
        if options_file.exists():
            try:
                with open(options_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}


def get_config() -> Config:
    return Config()
