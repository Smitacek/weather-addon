import tests
import tempfile
import unittest
import datetime as dt
from pathlib import Path
from solar_archive import SolarArchive
from solar_model import build_profile
from tests.test_solar_model import ARRAYS,hours,UTC

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.tmp.name)/'solar.db')
        self.archive=SolarArchive(self.path)
    def tearDown(self):
        self.archive.close(); self.tmp.cleanup()
    def test_no_future_revision_leak(self):
        start=dt.datetime(2026,10,11,10,tzinfo=UTC)
        early=build_profile(hours(start,24),ARRAYS,start-dt.timedelta(hours=2),'UTC')
        late=build_profile(hours(start,24,300),ARRAYS,start+dt.timedelta(minutes=30),'UTC')
        self.archive.save_forecast(early);self.archive.save_forecast(late)
        f=self.archive.forecast_before(start.isoformat(),1)
        self.assertEqual(f['issue_id'],early['issue_id'])
        self.archive.close(); self.archive=SolarArchive(self.path)
        self.assertEqual(self.archive.latest_forecast()['issue_id'],late['issue_id'])
    def test_missing_breaks_integration(self):
        for minute,power in [(0,1000),(1,1000),(2,None),(5,1000),(6,1000)]:
            self.archive.save_observation({'ts_utc':f'2026-10-11T10:0{minute}:00Z',
              'values':{'pv1_power_w':power,'pv2_power_w':power},'quality':'ambiguous'})
        actual=self.archive.hourly_actual('2026-10-11T10:00:00Z','2026-10-11T10:06:00Z')
        self.assertAlmostEqual(actual['arrays']['pv1']['energy_kwh'],0.05)
        self.assertAlmostEqual(actual['coverage_fraction'],0.5)
    def test_retention_and_dedup(self):
        p=build_profile(hours(dt.datetime(2020,1,1,tzinfo=UTC),24),ARRAYS,dt.datetime(2020,1,1,tzinfo=UTC),'UTC')
        self.archive.save_forecast(p);self.archive.save_forecast(p)
        self.archive.cleanup('2026-10-11T00:00:00Z',400)
        self.assertIsNone(self.archive.latest_forecast())
    def test_future_schema_rejected(self):
        self.archive.connection.execute('PRAGMA user_version=999')
        self.archive.close()
        with self.assertRaises(ValueError): SolarArchive(self.path)
