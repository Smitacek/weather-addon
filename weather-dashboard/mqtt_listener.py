#!/usr/bin/env python3
import json
import threading
from typing import Dict, Any, Optional, List

import paho.mqtt.client as mqtt


class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.now: Dict[str, Any] = {}
        self.daily_series: List[Dict[str, Any]] = []  # list of {date_utc, value}
        self.daily_today: Dict[str, Any] = {}
        self.daily_tomorrow: Dict[str, Any] = {}

    def update_now(self, metric: str, payload: Dict[str, Any]):
        with self.lock:
            self.now[metric] = payload

    def set_daily_series(self, series: List[Dict[str, Any]]):
        with self.lock:
            self.daily_series = series

    def update_daily_bucket(self, bucket: str, payload: Dict[str, Any]):
        with self.lock:
            if bucket == "today":
                self.daily_today.update(payload)
            elif bucket == "tomorrow":
                self.daily_tomorrow.update(payload)

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "now": dict(self.now),
                "daily_series": list(self.daily_series),
                "daily_today": dict(self.daily_today),
                "daily_tomorrow": dict(self.daily_tomorrow),
            }


class MQTTIngest:
    def __init__(self, host: str, port: int, username: str, password: str, prefix: str, site_id: str, store: DataStore):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.prefix = prefix.rstrip("/")
        self.site_id = site_id
        self.store = store
        self.client: Optional[mqtt.Client] = None

    def start(self):
        self.client = mqtt.Client()
        if self.username:
            self.client.username_pw_set(self.username, self.password or "")

        def on_connect(client, userdata, flags, rc, properties=None):
            # Subscribe to relevant topics
            base = f"{self.prefix}/{self.site_id}"
            subs = [
                (f"{base}/hourly/+", 0),
                (f"{base}/daily/ghi_daily_total_mj_m2", 0),
                (f"{base}/daily/today/+", 0),
                (f"{base}/daily/tomorrow/+", 0),
            ]
            for t, q in subs:
                client.subscribe(t, qos=q)

        def on_message(client, userdata, msg):
            topic = msg.topic
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except Exception:
                return
            base = f"{self.prefix}/{self.site_id}/"
            if topic.startswith(base + "hourly/"):
                metric = topic[len(base + "hourly/"):]
                self.store.update_now(metric, payload)
            elif topic == base + "daily/ghi_daily_total_mj_m2":
                series = payload.get("series", [])
                if isinstance(series, list):
                    self.store.set_daily_series(series)
            elif topic.startswith(base + "daily/today/"):
                m = topic[len(base + "daily/today/"):]
                self.store.update_daily_bucket("today", {m: payload})
            elif topic.startswith(base + "daily/tomorrow/"):
                m = topic[len(base + "daily/tomorrow/"):]
                self.store.update_daily_bucket("tomorrow", {m: payload})

        self.client.on_connect = on_connect
        self.client.on_message = on_message
        self.client.connect(self.host, self.port, keepalive=30)
        self.client.loop_start()

