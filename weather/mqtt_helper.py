#!/usr/bin/env python3
import json
import time
from typing import Optional

import paho.mqtt.client as mqtt


class MQTTPublisher:
    def __init__(self, host: str, port: int, username: str = "", password: str = "", topic_prefix: str = "weather", site_id: str = "default"):
        self.host = host
        self.port = port
        self.username = username or None
        self.password = password or None
        self.topic_prefix = topic_prefix.rstrip("/")
        self.site_id = site_id
        self.client: Optional[mqtt.Client] = None
        self.connected: bool = False

    def connect(self, timeout: int = 10, retries: int = 3) -> bool:
        self.client = mqtt.Client()
        if self.username:
            self.client.username_pw_set(self.username, self.password or "")
        will_topic = f"{self.topic_prefix}/{self.site_id}/availability"
        self.client.will_set(will_topic, payload="offline", qos=1, retain=True)

        def on_connect(client, userdata, flags, rc, properties=None):
            self.connected = (rc == 0)
        def on_disconnect(client, userdata, rc, properties=None):
            self.connected = False

        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect

        attempt = 0
        while attempt < max(1, retries):
            attempt += 1
            try:
                self.client.connect(self.host, self.port, keepalive=30)
                self.client.loop_start()
                # wait for connection
                waited = 0
                while not self.connected and waited < timeout:
                    time.sleep(0.2)
                    waited += 0.2
                if self.connected:
                    # publish online
                    self.publish_raw(will_topic, "online", retain=True)
                    return True
            except Exception:
                pass
            time.sleep(1.0)
        return False

    def ensure_connected(self, timeout: int = 5) -> bool:
        if self.connected:
            return True
        if self.client is None:
            return False
        waited = 0
        while not self.connected and waited < timeout:
            time.sleep(0.2)
            waited += 0.2
        return self.connected

    def publish_json(self, topic_suffix: str, payload: dict, retain: bool = False, qos: int = 0) -> bool:
        topic = f"{self.topic_prefix}/{self.site_id}/{topic_suffix.lstrip('/')}"
        try:
            s = json.dumps(payload, separators=(",", ":"))
            self.client.publish(topic, payload=s, qos=qos, retain=retain)
            return True
        except Exception:
            return False

    def publish_raw(self, topic: str, payload: str, retain: bool = False, qos: int = 0) -> bool:
        try:
            self.client.publish(topic, payload=payload, qos=qos, retain=retain)
            return True
        except Exception:
            return False

    def publish_ha_sensor_config(self, unique_id: str, name: str, state_topic_suffix: str, unit: str = None, device_class: str = None, state_class: str = "measurement") -> bool:
        if not self.client:
            return False
        topic = f"homeassistant/sensor/{unique_id}/config"
        availability = f"{self.topic_prefix}/{self.site_id}/availability"
        state_topic = f"{self.topic_prefix}/{self.site_id}/{state_topic_suffix.lstrip('/')}"
        device = {
            "identifiers": [f"weather_addon_{self.site_id}"],
            "name": f"Weather {self.site_id}",
            "manufacturer": "Weather Add-on",
            "model": "Solar Forecast",
            "sw_version": "0.1.1"
        }
        payload = {
            "name": name,
            "unique_id": unique_id,
            "state_topic": state_topic,
            "availability_topic": availability,
            "device": device,
            "value_template": "{{ value_json.value }}",
        }
        if unit:
            payload["unit_of_measurement"] = unit
        if device_class:
            payload["device_class"] = device_class
        if state_class:
            payload["state_class"] = state_class
        try:
            self.client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=1, retain=True)
            return True
        except Exception:
            return False

    def publish_ha_discovery_minimal(self):
        """Publish minimal set of HA sensors via MQTT discovery."""
        # GHI now
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_ghi",
            name=f"Weather {self.site_id} GHI",
            state_topic_suffix="hourly/ghi_w_m2",
            unit="W/m²",
            device_class="irradiance",
        )
        # Sun elevation now
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_sun_elevation",
            name=f"Weather {self.site_id} Sun Elevation",
            state_topic_suffix="hourly/sun_elevation_deg",
            unit="°",
        )
        # Cloud cover now
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_cloud_cover",
            name=f"Weather {self.site_id} Cloud Cover",
            state_topic_suffix="hourly/cloud_cover_pct",
            unit="%",
        )

    def publish_ha_discovery_extended(self):
        """Publish extended set of HA sensors via MQTT discovery."""
        self.publish_ha_discovery_minimal()
        # DNI now
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_dni",
            name=f"Weather {self.site_id} DNI",
            state_topic_suffix="hourly/dni_w_m2",
            unit="W/m²",
            device_class="irradiance",
        )
        # DHI now
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_dhi",
            name=f"Weather {self.site_id} DHI",
            state_topic_suffix="hourly/dhi_w_m2",
            unit="W/m²",
            device_class="irradiance",
        )
        # k_GHI now
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_k_ghi",
            name=f"Weather {self.site_id} k_GHI",
            state_topic_suffix="hourly/k_ghi",
        )
        # Sun azimuth now
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_sun_azimuth",
            name=f"Weather {self.site_id} Sun Azimuth",
            state_topic_suffix="hourly/sun_azimuth_deg",
            unit="°",
        )
        # Sunshine duration (hour)
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_sunshine_hour",
            name=f"Weather {self.site_id} Sunshine (hour)",
            state_topic_suffix="hourly/sunshine_duration_s_hour",
            unit="s",
        )
        # Temperature 2m
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_temp2m",
            name=f"Weather {self.site_id} Temperature",
            state_topic_suffix="hourly/temp_2m_c",
            unit="°C",
            device_class="temperature",
        )
        # Wind speed 10m
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_wind10m",
            name=f"Weather {self.site_id} Wind 10m",
            state_topic_suffix="hourly/wind_speed_10m_ms",
            unit="m/s",
        )
        # Precipitation
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_precip",
            name=f"Weather {self.site_id} Precipitation",
            state_topic_suffix="hourly/precip_mm",
            unit="mm",
        )
        # Precipitation probability
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_precip_prob",
            name=f"Weather {self.site_id} Precip Probability",
            state_topic_suffix="hourly/precip_probability_pct",
            unit="%",
        )
        # Daily today & tomorrow summaries
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_ghi_today",
            name=f"Weather {self.site_id} GHI Today",
            state_topic_suffix="daily/today/ghi_daily_total_mj_m2",
            unit="MJ/m²",
        )
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_sunshine_today",
            name=f"Weather {self.site_id} Sunshine Today",
            state_topic_suffix="daily/today/sunshine_duration_s",
            unit="s",
        )
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_precip_today",
            name=f"Weather {self.site_id} Precip Today",
            state_topic_suffix="daily/today/precip_day_total_mm",
            unit="mm",
        )
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_tmax_today",
            name=f"Weather {self.site_id} Temp Max Today",
            state_topic_suffix="daily/today/temp_day_max_c",
            unit="°C",
            device_class="temperature",
        )
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_ghi_tomorrow",
            name=f"Weather {self.site_id} GHI Tomorrow",
            state_topic_suffix="daily/tomorrow/ghi_daily_total_mj_m2",
            unit="MJ/m²",
        )
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_sunshine_tomorrow",
            name=f"Weather {self.site_id} Sunshine Tomorrow",
            state_topic_suffix="daily/tomorrow/sunshine_duration_s",
            unit="s",
        )
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_precip_tomorrow",
            name=f"Weather {self.site_id} Precip Tomorrow",
            state_topic_suffix="daily/tomorrow/precip_day_total_mm",
            unit="mm",
        )
        self.publish_ha_sensor_config(
            unique_id=f"weather_{self.site_id}_tmax_tomorrow",
            name=f"Weather {self.site_id} Temp Max Tomorrow",
            state_topic_suffix="daily/tomorrow/temp_day_max_c",
            unit="°C",
            device_class="temperature",
        )

    def disconnect(self):
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
        except Exception:
            pass
