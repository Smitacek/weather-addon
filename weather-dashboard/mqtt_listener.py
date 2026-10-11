#!/usr/bin/env python3
import json
import threading
import copy
import datetime as dt
import math
from typing import Dict, Any, Optional, List

import paho.mqtt.client as mqtt


class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.now: Dict[str, Any] = {}
        self.daily_series: List[Dict[str, Any]] = []  # list of {date_utc, value}
        self.daily_today: Dict[str, Any] = {}
        self.daily_tomorrow: Dict[str, Any] = {}
        self.solar = {}
        self.solar_health = {}
        self.solar_evaluation = {}
        self.solar_observed = {}
        self.solar_observed_series = []

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

    def update_solar(self, metric, payload):
        if not isinstance(payload, dict): return False
        try:
            json.dumps(payload, allow_nan=False)
            if metric == 'profile':
                if payload.get('schema_version') != 2 or not isinstance(payload.get('intervals'),list) or len(payload['intervals']) > 169:
                    return False
                issued = parse_time(payload['issued_at_utc'])
                if not isinstance(payload.get('array_config'),list) or len(payload['array_config'])>8:
                    return False
                if not isinstance(payload.get('daily'),list) or len(payload['daily'])>12: return False
                for array in payload['array_config']:
                    if not isinstance(array,dict) or not isinstance(array.get('id'),str) or not isinstance(array.get('capacity_kw'),(int,float)):
                        return False
                for day in payload['daily']:
                    if not isinstance(day,dict) or not isinstance(day.get('date_local'),str): return False
                    dt.date.fromisoformat(day['date_local'])
                    if day.get('energy_kwh') is not None and not isinstance(day['energy_kwh'],(int,float)): return False
                prev=None
                for row in payload['intervals']:
                    if not isinstance(row,dict): return False
                    start,end=parse_time(row['interval_start_utc']),parse_time(row['interval_end_utc'])
                    if not 0 < (end-start).total_seconds() <= 3600 or (prev and start<prev): return False
                    prev=end
                    if row['power_w'] is not None and (not isinstance(row['power_w'],(int,float)) or row['power_w']<0): return False
                    if not isinstance(row.get('arrays'),dict): return False
            elif metric == 'observed_series':
                if not isinstance(payload.get('samples'),list) or len(payload['samples'])>400: return False
            elif metric == 'evaluation':
                if not isinstance(payload.get('hours',[]),list) or len(payload.get('hours',[]))>48: return False
            elif metric not in ('health','observed'): return False
            with self.lock:
                if metric == 'profile':
                    if self.solar and issued < parse_time(self.solar['issued_at_utc']): return False
                    self.solar = copy.deepcopy(payload)
                elif metric == 'health': self.solar_health = copy.deepcopy(payload)
                elif metric == 'evaluation': self.solar_evaluation = copy.deepcopy(payload)
                elif metric == 'observed': self.solar_observed = copy.deepcopy(payload)
                elif metric == 'observed_series': self.solar_observed_series = copy.deepcopy(payload['samples'])
            return True
        except (ValueError,KeyError,TypeError): return False

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "solar": copy.deepcopy(self.solar),
                "solar_health": copy.deepcopy(self.solar_health),
                "solar_evaluation": copy.deepcopy(self.solar_evaluation),
                "solar_observed": copy.deepcopy(self.solar_observed),
                "solar_observed_series": copy.deepcopy(self.solar_observed_series),
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
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if self.username:
            self.client.username_pw_set(self.username, self.password or "")

        def on_connect(client, userdata, flags, rc, properties=None):
            # Subscribe to relevant topics
            base = f"{self.prefix}/{self.site_id}"
            subs = [
                (f"{base}/solar/+", 1),
                (f"{base}/hourly/+", 0),
                (f"{base}/daily/ghi_daily_total_mj_m2", 0),
                (f"{base}/daily/today/+", 0),
                (f"{base}/daily/tomorrow/+", 0),
            ]
            for t, q in subs:
                client.subscribe(t, qos=q)

        def on_message(client, userdata, msg):
            topic = msg.topic
            if len(msg.payload)>1048576: return
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except Exception:
                return
            base = f"{self.prefix}/{self.site_id}/"
            if not isinstance(payload,dict): return
            if topic.startswith(base + "solar/"):
                self.store.update_solar(topic[len(base + "solar/"):],payload)
            elif topic.startswith(base + "hourly/"):
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



def parse_time(value):
    if not isinstance(value,str): raise ValueError('Timestamp must be a string')
    t = dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None: raise ValueError('Timezone missing')
    return t.astimezone(dt.timezone.utc)
