"""Persistent forecast vintages and minute observations, compressed for year retention."""
import datetime as dt
import json
import sqlite3
import zlib
from pathlib import Path
from solar_model import timestamp,iso

def encode(value):
    return zlib.compress(json.dumps(value,separators=(',',':'),allow_nan=False).encode(),6)

def decode(value):
    return json.loads(zlib.decompress(value))

class SolarArchive:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.connection=sqlite3.connect(path,timeout=5)
        try:
            version=self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1): raise ValueError('Unsupported solar archive schema')
            self.connection.execute('PRAGMA journal_mode=WAL')
            self.connection.execute('PRAGMA foreign_keys=ON')
            self.connection.executescript('''CREATE TABLE IF NOT EXISTS forecasts (
              issue_id TEXT PRIMARY KEY, issued_at TEXT NOT NULL, payload BLOB NOT NULL);
              CREATE INDEX IF NOT EXISTS forecast_time ON forecasts(issued_at);
              CREATE TABLE IF NOT EXISTS observations (ts_utc TEXT PRIMARY KEY, payload BLOB NOT NULL);
              PRAGMA user_version=1;''')
        except Exception:
            self.connection.close();raise
    def close(self):
        self.connection.close()
    def save_forecast(self,profile):
        with self.connection:
            self.connection.execute('INSERT OR IGNORE INTO forecasts VALUES (?,?,?)',
              (profile['issue_id'],iso(profile['issued_at_utc']),encode(profile)))
    def save_observation(self,sample):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO observations VALUES (?,?)',
              (iso(sample['ts_utc']),encode(sample)))
    def latest_forecast(self):
        row=self.connection.execute('SELECT payload FROM forecasts ORDER BY issued_at DESC LIMIT 1').fetchone()
        return decode(row[0]) if row else None
    def forecast_before(self,start_utc,lead_h=0):
        start=timestamp(start_utc)
        cutoff=iso(start-dt.timedelta(hours=lead_h))
        cursor=self.connection.execute('SELECT payload FROM forecasts WHERE issued_at<=? ORDER BY issued_at DESC LIMIT 100',(cutoff,))
        for row in cursor:
            profile=decode(row[0])
            if any(timestamp(r['interval_start_utc'])<=start<timestamp(r['interval_end_utc'])
                   for r in profile['intervals']): return profile
        return None
    def recent_observations(self,start_utc,end_utc):
        # Include one predecessor for correct boundary integration.
        predecessor=self.connection.execute('SELECT payload FROM observations WHERE ts_utc<? ORDER BY ts_utc DESC LIMIT 1',(iso(start_utc),)).fetchone()
        rows=self.connection.execute('SELECT payload FROM observations WHERE ts_utc>=? AND ts_utc<=? ORDER BY ts_utc',(iso(start_utc),iso(end_utc))).fetchall()
        return ([decode(predecessor[0])] if predecessor else [])+[decode(r[0]) for r in rows]
    def hourly_actual(self,start_utc,end_utc):
        start,end=timestamp(start_utc),timestamp(end_utc)
        if end<=start: raise ValueError('Invalid observation interval')
        samples=self.recent_observations(start,end)
        metrics=['pv1_power_w','pv2_power_w','ac_power_w']
        energy={key:0.0 for key in metrics};coverage={key:0.0 for key in metrics}
        both=0;eligible=0;joint_energy=0.0
        for first,second in zip(samples,samples[1:]):
            fs,se=timestamp(first['ts_utc']),timestamp(second['ts_utc'])
            if (se-fs).total_seconds()>90: continue
            segment_start=max(start,fs)
            vals=first.get('values',{})
            durations={}
            for key in metrics:
                segment_end=min(end,se)
                expires=first.get('valid_until_utc',{}).get(key)
                if expires: segment_end=min(segment_end,timestamp(expires))
                invalidated=second.get('invalidated_at_utc',{}).get(key)
                if invalidated and fs<timestamp(invalidated)<se:
                    segment_end=min(segment_end,timestamp(invalidated))
                seconds=max(0,(segment_end-segment_start).total_seconds())
                v=vals.get(key)
                durations[key]=seconds if isinstance(v,(int,float)) else 0
                if isinstance(v,(int,float)):
                    energy[key]+=max(0,v)*seconds/3600000
                    coverage[key]+=seconds
            seconds=min(durations[k] for k in metrics[:2])
            if seconds:
                both+=seconds
                joint_energy+=(max(0,vals['pv1_power_w'])+max(0,vals['pv2_power_w']))*seconds/3600000
                if first.get('quality')=='eligible': eligible+=seconds
        total_seconds=(end-start).total_seconds()
        return {'interval_start_utc':iso(start),'interval_end_utc':iso(end),
            'arrays':{key:{'energy_kwh':energy[key+'_power_w'] if coverage[key+'_power_w'] else None,
                          'coverage_fraction':coverage[key+'_power_w']/total_seconds} for key in ['pv1','pv2']},
            'energy_kwh':joint_energy if both else None,
            'coverage_fraction':both/total_seconds,'eligible_fraction':eligible/total_seconds,
            'ac_energy_kwh':energy['ac_power_w'] if coverage['ac_power_w'] else None}
    def evaluation_summary(self,now_utc):
        end=timestamp(now_utc).replace(minute=0,second=0,microsecond=0)
        results=[]
        for offset in range(24,0,-1):
            start=end-dt.timedelta(hours=offset)
            actual=self.hourly_actual(start,start+dt.timedelta(hours=1))
            forecast=self.forecast_before(start,1)
            predicted=None
            if forecast:
                row=next((r for r in forecast['intervals'] if timestamp(r['interval_start_utc'])==start),None)
                if row: predicted=row['energy_kwh']
            comparable=actual['coverage_fraction']>=0.95 and predicted is not None
            results.append({**actual,'predicted_energy_kwh':predicted,
                'issue_id':forecast['issue_id'] if forecast else None,
                'lead_hours':(start-timestamp(forecast['issued_at_utc'])).total_seconds()/3600 if forecast else None,
                'error_kwh':actual['energy_kwh']-predicted if comparable else None,
                'calibration_eligible':comparable and actual['eligible_fraction']>=0.95})
        return {'hours':results,'comparable_hours':sum(r['error_kwh'] is not None for r in results),
                'eligible_hours':sum(r['calibration_eligible'] for r in results)}
    def cleanup(self,now_utc,retention_days):
        cutoff=iso(timestamp(now_utc)-dt.timedelta(days=retention_days))
        with self.connection:
            self.connection.execute('DELETE FROM forecasts WHERE issued_at<?',(cutoff,))
            self.connection.execute('DELETE FROM observations WHERE ts_utc<?',(cutoff,))
