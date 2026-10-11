import tests
import sys
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from solar_model import build_profile
from solar_archive import SolarArchive
from solar_telemetry import TelemetryCollector
from solar_service import SolarService
from weather_publication import publish_weather
from tests.test_solar_model import ARRAYS,hours,UTC
sys.path.append(str(Path(__file__).resolve().parents[1]/'weather-dashboard'))
from mqtt_listener import DataStore

class ReviewRegressions(unittest.TestCase):
    def test_bad_mqtt_timestamp_rejected(self):
        self.assertFalse(DataStore().update_solar('profile',{'schema_version':2,'intervals':[],
            'array_config':[],'daily':[],'issued_at_utc':None}))
    def test_expiry_caps_integration(self):
        now=dt.datetime(2026,10,11,10,tzinfo=UTC)
        c=TelemetryCollector({'pv1_power_w':'pv1','pv2_power_w':'pv2'})
        for topic in ['pv1','pv2']: c.ingest(topic,b'1000',now)
        with tempfile.TemporaryDirectory() as d:
            a=SolarArchive(str(Path(d)/'a.db'))
            for i in [0,1,2]: a.save_observation(c.snapshot(now+dt.timedelta(minutes=i)))
            r=a.hourly_actual(now,now+dt.timedelta(minutes=2))
            self.assertAlmostEqual(r['coverage_fraction'],0.75)
            self.assertAlmostEqual(r['energy_kwh'],0.05)
            a.close()
    def test_partial_input_not_in_joint_energy(self):
        now=dt.datetime(2026,10,11,10,tzinfo=UTC)
        with tempfile.TemporaryDirectory() as d:
            a=SolarArchive(str(Path(d)/'a.db'))
            for i,power in enumerate([1000,None,1000]):
                a.save_observation({'ts_utc':(now+dt.timedelta(minutes=i)).isoformat(),
                    'values':{'pv1_power_w':1000,'pv2_power_w':power},'quality':'ambiguous'})
            r=a.hourly_actual(now,now+dt.timedelta(minutes=2))
            self.assertAlmostEqual(r['energy_kwh'],2/60)
            self.assertAlmostEqual(r['coverage_fraction'],0.5)
            a.close()
    def test_offline_online_requires_new_measurement(self):
        now=dt.datetime(2026,10,11,10,tzinfo=UTC)
        c=TelemetryCollector({'pv1_power_w':'pv1','inverter_available':'available'})
        c.ingest('available',b'online',now,retained=True);c.ingest('pv1',b'1000',now)
        c.ingest('available',b'offline',now+dt.timedelta(seconds=10))
        c.ingest('available',b'online',now+dt.timedelta(seconds=20),retained=True)
        self.assertIsNone(c.snapshot(now+dt.timedelta(seconds=20))['values']['pv1_power_w'])
    def test_outage_between_samples_caps_segment(self):
        now=dt.datetime(2026,10,11,10,tzinfo=UTC)
        c=TelemetryCollector({'pv1_power_w':'pv1','pv2_power_w':'pv2','inverter_available':'available'})
        c.ingest('available',b'online',now,retained=True)
        for topic in ['pv1','pv2']: c.ingest(topic,b'1000',now)
        first=c.snapshot(now)
        c.ingest('available',b'offline',now+dt.timedelta(seconds=10))
        c.ingest('available',b'online',now+dt.timedelta(seconds=20))
        for topic in ['pv1','pv2']: c.ingest(topic,b'1000',now+dt.timedelta(seconds=30))
        second=c.snapshot(now+dt.timedelta(seconds=60))
        with tempfile.TemporaryDirectory() as d:
            a=SolarArchive(str(Path(d)/'a.db'));a.save_observation(first);a.save_observation(second)
            r=a.hourly_actual(now,now+dt.timedelta(seconds=60))
            self.assertAlmostEqual(r['coverage_fraction'],1/6)
            a.close()
    def test_observation_does_not_clear_forecast_write_failure(self):
        class Archive:
            def latest_forecast(self): return None
            def save_forecast(self,p): raise OSError('forecast disk failure')
            def save_observation(self,p): pass
            def recent_observations(self,*args): return []
            def cleanup(self,*args): pass
            def evaluation_summary(self,*args): return {}
        now=dt.datetime(2026,10,11,10,tzinfo=UTC)
        cfg=SimpleNamespace(pv_arrays=ARRAYS,timezone='UTC',hourly_horizon_h=72,
            conservative_factor=0.8,update_interval=300,solar_retention_days=400)
        s=SolarService(cfg,None,Archive(),TelemetryCollector({}))
        with self.assertLogs(level='ERROR'):
            s.accept_forecast({'hourly':hours(now,96)},now)
        s.sample(now)
        self.assertFalse(s.health(now)['archive_ok'])
    def test_jsonl_failure_not_forecast_failure(self):
        now=dt.datetime(2026,10,11,10,tzinfo=UTC)
        cfg=SimpleNamespace(latitude=50,longitude=14,timezone='UTC',log_raw=True,log_features=True,site_id='test')
        forecast={'hourly':hours(now,3),'issue_time_utc':now.isoformat(),'daily':[]}
        with patch('weather_publication.append_jsonl',side_effect=OSError('disk full')):
            error=publish_weather(forecast,cfg,None,now)
        self.assertIn('disk full',error)
