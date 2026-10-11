"""Coordinates pure forecast computation, persisted observations and MQTT output."""
import datetime as dt
import logging
from zoneinfo import ZoneInfo
from solar_model import timestamp,iso,build_profile

class SolarService:
    def __init__(self,config,publisher,archive,collector):
        self.config,self.publisher,self.archive,self.collector=config,publisher,archive,collector
        self.profile=None;self.forecast_archive_error=None;self.observation_archive_error=None;self.provider_error=None;self.weather_log_error=None
        self.evaluation={};self.last_evaluation=None;self.last_cleanup=None
        self.observed_series=[]
        try: self.profile=archive.latest_forecast() if archive else None
        except Exception as exc: self.forecast_archive_error=str(exc)
    @property
    def archive_error(self):
        return self.forecast_archive_error or self.observation_archive_error
    def record_error(self,error):
        self.provider_error=str(error)
    def accept_forecast(self,forecast,now):
        cfg=self.config
        profile=build_profile(forecast['hourly'],cfg.pv_arrays,now,cfg.timezone,
                              cfg.hourly_horizon_h,cfg.conservative_factor)
        profile['fetched_at_utc']=forecast.get('issue_time_utc',iso(now))
        profile['pv_mapping_confirmed']=getattr(cfg,'pv_mapping_confirmed',False)
        profile['assumptions']+=['NOCT temperature approximation','constant losses; local shading not calibrated']
        self.profile=profile;self.provider_error=None
        try:
            if self.archive is None: raise OSError('Archive not initialized')
            self.archive.save_forecast(profile)
            self.forecast_archive_error=None
        except Exception as exc:
            self.forecast_archive_error=str(exc);logging.error('Solar archive write failed: %s',exc)
    def sample(self,now):
        sample=self.collector.snapshot(now)
        try:
            if self.archive is None: raise OSError('Archive not initialized')
            self.archive.save_observation(sample)
            self.observation_archive_error=None
            recent=self.archive.recent_observations(timestamp(now)-dt.timedelta(hours=6),now)
            self.observed_series=[{'ts_utc':r['ts_utc'],'values':r['values'],'quality':r['quality']} for r in recent[-400:]]
            if not self.last_cleanup or timestamp(now)-self.last_cleanup>=dt.timedelta(days=1):
                self.archive.cleanup(now,self.config.solar_retention_days)
                self.last_cleanup=timestamp(now)
            if not self.last_evaluation or timestamp(now)-self.last_evaluation>=dt.timedelta(minutes=5):
                self.evaluation=self.archive.evaluation_summary(now)
                self.last_evaluation=timestamp(now)
        except Exception as exc:
            self.observation_archive_error=str(exc);logging.error('Solar observation archive failed: %s',exc)
        if self.publisher: self.publisher.publish_json('solar/observed',sample,retain=True,qos=1)
        return sample
    def health(self,now):
        age=(timestamp(now)-timestamp(self.profile['issued_at_utc'])).total_seconds() if self.profile else None
        valid=age is not None and 0<=age<=self.config.update_interval*3 and bool(self.profile['intervals'])
        return dict(ts_utc=iso(now),forecast_valid=valid,age_s=age,archive_ok=self.archive_error is None and self.archive is not None,
                    archive_error=self.archive_error,provider_error=self.provider_error,weather_log_error=self.weather_log_error,
                    mapping_confirmed=getattr(self.config,'pv_mapping_confirmed',False),ttl_s=self.config.update_interval*3)
    def publish(self,now):
        if not self.publisher: return
        health=self.health(now)
        base=f'{self.config.mqtt_topic_prefix}/{self.config.site_id}'
        self.publisher.publish_raw(base+'/solar/availability','online' if health['forecast_valid'] else 'offline',retain=True,qos=1)
        self.publisher.publish_json('solar/health',health,retain=True,qos=1)
        self.publisher.publish_json('solar/evaluation',self.evaluation,retain=True,qos=1)
        self.publisher.publish_json('solar/observed_series',{'samples':self.observed_series},retain=True,qos=1)
        if not self.profile: return
        self.publisher.publish_json('solar/profile',self.profile,retain=True,qos=1)
        today=timestamp(now).astimezone(ZoneInfo(self.config.timezone)).date()
        metrics={'forecast_age_s':health['age_s'],'archive_status':'ok' if health['archive_ok'] else 'error',
                 'last_forecast':self.profile['issued_at_utc']}
        interval=next((r for r in self.profile['intervals'] if timestamp(r['interval_start_utc'])<=timestamp(now)<timestamp(r['interval_end_utc'])),None)
        metrics['available_power_w']=interval['power_w'] if interval else None
        for offset,label in [(0,'remaining_today'),(1,'tomorrow'),(2,'day_after_tomorrow')]:
            date=(today+dt.timedelta(days=offset)).isoformat()
            day=next((r for r in self.profile['daily'] if r['date_local']==date),None)
            if offset==0 and day:
                # Recompute remaining energy from immutable profile at current time.
                rows=[r for r in self.profile['intervals'] if timestamp(r['interval_start_utc']).astimezone(ZoneInfo(self.config.timezone)).date().isoformat()==date and timestamp(r['interval_end_utc'])>timestamp(now)]
                metrics[label+'_energy_kwh']=sum(r['power_w']*max(0,(timestamp(r['interval_end_utc'])-max(timestamp(now),timestamp(r['interval_start_utc']))).total_seconds())/3600000 for r in rows) if rows and all(r['power_w'] is not None for r in rows) and day['remaining_complete'] else None
            else:
                metrics[label+'_energy_kwh']=day['energy_kwh'] if day else None
            if offset:
                metrics[label+'_conservative_energy_kwh']=day['conservative_energy_kwh'] if day else None
        for key,value in metrics.items():
            self.publisher.publish_json('solar/metrics/'+key,dict(value=value,issued_at_utc=self.profile['issued_at_utc']),retain=True,qos=1)
