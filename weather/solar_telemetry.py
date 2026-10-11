"""Thread-safe read-only MQTT telemetry with conservative quality classification."""
import datetime as dt
import json
import math
import threading
from solar_model import timestamp,iso

class TelemetryCollector:
    def __init__(self,topic_map,max_age_s=90,operating_limits_confirmed=False):
        self.topic_map=dict(topic_map)
        if len(set(self.topic_map.values()))!=len(self.topic_map):
            raise ValueError('Telemetry topics must map to distinct fields')
        self.by_topic={v:k for k,v in self.topic_map.items() if v}
        self.max_age_s=max_age_s
        self.operating_limits_confirmed=operating_limits_confirmed
        self.lock=threading.Lock()
        self.fields={}
    def disconnected(self):
        with self.lock: self.fields.clear()
    def ingest(self,topic,payload,received_at,retained=False):
        key=self.by_topic.get(topic)
        if key is None or len(payload)>4096: return
        received_at=timestamp(received_at)
        try:
            raw=payload.decode('utf-8')
            source=received_at
            if raw.startswith('{'):
                parsed=json.loads(raw)
                source=timestamp(parsed['ts_utc']) if parsed.get('ts_utc') else received_at
                raw=parsed.get('value')
            if key.endswith('_connection') or key.endswith('_available'):
                value=str(raw)
                if value not in ('online','offline'): return
            elif key in ('inverter_mode','charge_stage','curtailment_active'):
                if retained: return
                value=str(raw)
            else:
                if retained: return
                value=float(raw)
                if not math.isfinite(value): raise ValueError('Invalid number')
                if key.endswith('_soc') and not 0<=value<=100: raise ValueError('Invalid SoC')
                if key.startswith('pv') and value<0: raise ValueError('Negative PV value')
            if source>received_at+dt.timedelta(seconds=5): return
            with self.lock:
                previous=self.fields.get(key)
                if previous and source<previous[1]: return
                self.fields[key]=(value,source,received_at)
        except (UnicodeError,ValueError,TypeError,KeyError):
            # Invalid fresh value invalidates prior data instead of silently holding it.
            with self.lock: self.fields.pop(key,None)
    def snapshot(self,now):
        now=timestamp(now)
        with self.lock: fields=dict(self.fields)
        def valid(key):
            record=fields.get(key)
            return record and 0<=(now-record[1]).total_seconds()<=self.max_age_s
        def group_online(keys):
            return all(fields.get(k,('offline',))[0]=='online' for k in keys if k in self.topic_map)
        values={};ages={};received={}
        for key in self.topic_map:
            row=fields.get(key)
            is_availability=key.endswith('_available') or key.endswith('_connection')
            value=row[0] if row and (valid(key) or is_availability) else None
            if not is_availability:
                if key.startswith(('pv','ac_','inverter_','charge_')):
                    online=group_online(['inverter_connection','inverter_available'])
                elif key.startswith('battery1_'):
                    online=group_online(['bms_connection','battery1_available'])
                elif key.startswith('battery2_'):
                    online=group_online(['bms_connection','battery2_available'])
                else: online=True
                if not online: value=None
            values[key]=value
            ages[key]=(now-row[1]).total_seconds() if row else None
            received[key]=iso(row[2]) if row else None
        essential=['pv1_power_w','pv2_power_w','ac_power_w','battery1_soc','battery2_soc',
                   'battery1_power_w','battery2_power_w']
        missing=[key for key in essential if values.get(key) is None]
        quality='ambiguous';reasons=['operating limits or unrestricted operation not established']
        if missing:
            quality='missing';reasons=missing
        elif values.get('curtailment_active')=='true':
            quality='confirmed_curtailed';reasons=['explicit curtailment telemetry']
        elif min(values['battery1_soc'],values['battery2_soc'])>=95 and values['ac_power_w']<100 and abs(values['battery1_power_w'])+abs(values['battery2_power_w'])<50:
            quality='suspected_curtailed';reasons=['high SoC, little battery flow and low AC load']
        elif self.operating_limits_confirmed and min(values['battery1_soc'],values['battery2_soc'])<90 and sum(values[k] for k in ['battery1_power_w','battery2_power_w'])>100:
            # Requires an operator's prior confirmation of physical limits.
            quality='eligible';reasons=['confirmed limits, active charging and battery headroom']
        return dict(ts_utc=iso(now),values=values,ages_s=ages,received_at_utc=received,
                    quality=quality,reasons=reasons)
