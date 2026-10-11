import tests
import unittest
import tempfile
import datetime as dt
from types import SimpleNamespace
from pathlib import Path
from solar_service import SolarService
from solar_archive import SolarArchive
from solar_telemetry import TelemetryCollector
from tests.test_solar_model import ARRAYS,hours,UTC

class Publisher:
    def __init__(self): self.messages=[]
    def publish_json(self,t,p,**kw): self.messages.append((t,p));return True
    def publish_raw(self,t,p,**kw): self.messages.append((t,p));return True

class ServiceTests(unittest.TestCase):
    def test_provider_failure_and_restart_age(self):
        with tempfile.TemporaryDirectory() as d:
            now=dt.datetime(2026,10,11,12,tzinfo=UTC)
            cfg=SimpleNamespace(timezone='UTC',hourly_horizon_h=72,conservative_factor=0.8,
                pv_arrays=ARRAYS,update_interval=300,solar_retention_days=400,
                mqtt_topic_prefix='weather',site_id='default',pv_mapping_confirmed=False)
            a=SolarArchive(str(Path(d)/'data.db'));p=Publisher()
            s=SolarService(cfg,p,a,TelemetryCollector({}))
            s.accept_forecast({'hourly':hours(now-dt.timedelta(hours=12),108)},now)
            self.assertTrue(s.health(now)['forecast_valid'])
            s.record_error('provider timeout')
            self.assertFalse(s.health(now+dt.timedelta(seconds=901))['forecast_valid'])
            restored=SolarService(cfg,p,a,TelemetryCollector({}))
            self.assertFalse(restored.health(now+dt.timedelta(seconds=901))['forecast_valid'])
            a.close()
    def test_archive_failure_is_visible(self):
        class BrokenArchive:
            def latest_forecast(self): return None
            def save_forecast(self,p): raise OSError('disk full')
        cfg=SimpleNamespace(timezone='UTC',hourly_horizon_h=72,conservative_factor=0.8,pv_arrays=ARRAYS,update_interval=300)
        s=SolarService(cfg,Publisher(),BrokenArchive(),TelemetryCollector({}))
        with self.assertLogs(level='ERROR'):
            s.accept_forecast({'hourly':hours(dt.datetime(2026,10,11,tzinfo=UTC),96)},dt.datetime(2026,10,11,tzinfo=UTC))
        self.assertFalse(s.health(dt.datetime(2026,10,11,tzinfo=UTC))['archive_ok'])

    def test_sampling_continues_while_provider_is_blocked(self):
        import main
        import threading
        from unittest.mock import patch
        from addon_config import Config
        import json
        with tempfile.TemporaryDirectory() as d:
            options=Path(d)/'options.json'
            db=str(Path(d)/'solar.db')
            options.write_text(json.dumps({'solar_enabled':True,'pv_arrays':ARRAYS,
                'mqtt_enabled':False,'solar_archive_path':db,'log_raw':False,'log_features':False}))
            config=Config(options_path=options)
            waiting=threading.Event();release=threading.Event()
            def fetch(**kw):
                waiting.set();release.wait(5)
                raise TimeoutError('provider deliberately blocked')
            def stop(seconds):
                self.assertTrue(waiting.wait(1))
                raise KeyboardInterrupt
            try:
                with patch.object(main,'get_config',return_value=config),patch.object(main,'fetch_open_meteo',side_effect=fetch),patch.object(main.time,'sleep',side_effect=stop):
                    main.main()
                a=SolarArchive(db)
                self.assertEqual(a.connection.execute('SELECT count(*) FROM observations').fetchone()[0],1)
                a.close()
            finally: release.set()
