"""Backward compatible weather MQTT topics, corrected local daily accounting."""
import datetime as dt
from zoneinfo import ZoneInfo
from solar_model import timestamp,iso,day_bounds
from compute import derive_hourly_features
from log_writer import append_jsonl

HOURLY=['ghi_w_m2','dni_w_m2','dhi_w_m2','k_ghi','sun_elevation_deg','sun_azimuth_deg',
        'cloud_cover_pct','temp_2m_c','wind_speed_10m_ms','precip_mm',
        'precip_probability_pct','sunshine_duration_s_hour']
DAILY=['ghi_daily_total_mj_m2','sunshine_duration_s','precip_day_total_mm',
       'temp_day_max_c','cloud_cover_day_mean_pct']

def daily_weather(rows,provider_days,timezone):
    tz=ZoneInfo(timezone)
    dates=sorted({timestamp(r['interval_start_utc']).astimezone(tz).date() for r in rows})
    out=[]
    for day in dates:
        start,end=day_bounds(day,tz)
        records=[r for r in rows if timestamp(r['interval_start_utc'])>=start and timestamp(r['interval_end_utc'])<=end]
        expected=(end-start).total_seconds()/3600
        valid=[r for r in records if r.get('ghi_w_m2') is not None]
        complete=len(valid)==expected
        cloud=[r['cloud_cover_pct'] for r in records if r.get('cloud_cover_pct') is not None]
        provider=next((r for r in provider_days if r['date_local']==day.isoformat()),{})
        out.append({**provider,'date_local':day.isoformat(),'date_utc':day.isoformat(),
            'timezone':timezone,'complete':complete,
            'ghi_daily_total_mj_m2':sum(r['ghi_w_m2']*3600/1e6 for r in valid) if complete else None,
            'cloud_cover_day_mean_pct':sum(cloud)/len(cloud) if len(cloud)==expected else None})
    return out

def publish_weather(forecast,config,publisher,now):
    rows=[]
    log_error=None
    def log(prefix,record,field='ts_utc'):
        nonlocal log_error
        if log_error is not None: return
        try: append_jsonl(prefix,record,field)
        except OSError as exc: log_error=str(exc)
    for h in forecast['hourly']:
        # Solar geometry aligned with preceding-hour average radiation.
        mid=timestamp(h['interval_start_utc'])+dt.timedelta(minutes=30)
        derived=derive_hourly_features(latitude=config.latitude,longitude=config.longitude,
                                      ts_utc=mid,cfg={},raw=h)
        rec={**h,**derived,'data_version':'2.0','fetched_at_utc':forecast['issue_time_utc'],
             'site_id':config.site_id,'provider':'open-meteo','timezone':config.timezone}
        rows.append(rec)
        if config.log_raw or config.log_features: log('hourly',rec)
    days=daily_weather(rows,forecast.get('daily',[]),config.timezone)
    if config.log_raw or config.log_features:
        for d in days: log('daily',{**d,'data_version':'2.0','site_id':config.site_id},'date_local')
    if not publisher or not publisher.connected: return log_error
    current=next((r for r in rows if timestamp(r['interval_start_utc'])<=timestamp(now)<timestamp(r['interval_end_utc'])),None)
    if current:
        for metric in HOURLY:
            publisher.publish_json('hourly/'+metric,dict(ts_utc=iso(now),value=current.get(metric)))
    publisher.publish_json('daily/ghi_daily_total_mj_m2',{'series':[
        dict(date_utc=d['date_local'],date_local=d['date_local'],value=d['ghi_daily_total_mj_m2']) for d in days]},retain=True)
    today=timestamp(now).astimezone(ZoneInfo(config.timezone)).date()
    for offset,label in [(0,'today'),(1,'tomorrow')]:
        day=next((d for d in days if d['date_local']==(today+dt.timedelta(days=offset)).isoformat()),None)
        for metric in DAILY:
            publisher.publish_json(f'daily/{label}/{metric}',{'date_local':day['date_local'] if day else None,
                'date_utc':day['date_local'] if day else None,'value':day.get(metric) if day else None},retain=True)

    return log_error
