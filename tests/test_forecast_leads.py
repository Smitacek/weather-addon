import tests
import datetime as dt
import unittest
from pathlib import Path
from tests import test_comparison as fixtures
forecast=fixtures.forecast;observe=fixtures.observe;UTC=fixtures.UTC

class LeadTests(unittest.TestCase):
    setUp=fixtures.ComparisonTests.setUp
    tearDown=fixtures.ComparisonTests.tearDown
    compare=fixtures.ComparisonTests.compare
    def test_three_evening_baselines_use_same_measured_day(self):
        start=dt.datetime(2026,10,11,22,tzinfo=UTC)
        for n,power in [(1,1000),(2,2000),(3,3000)]:
            issued=(start-dt.timedelta(days=n-1,hours=2)).isoformat()
            forecast(self.a,start,24,issued,'d'+str(n),power)
        observe(self.a,start,1440)
        day=self.compare('2026-10-12T22:03:00Z')['days'][0]
        self.assertIn('horizons',day)
        for n,want in [('1',24),('2',48),('3',72)]:
            self.assertAlmostEqual(day['horizons'][n]['predicted_energy_kwh'],want)
            self.assertEqual(day['horizons'][n]['issue_id'],'d'+n)
        self.assertEqual(day['actual_energy_kwh'],48)
    def test_old_cache_is_upgraded_without_losing_measurements(self):
        import solar_archive
        start=dt.datetime(2026,10,11,22,tzinfo=UTC)
        forecast(self.a,start,24,'2026-10-11T19:55:00Z');observe(self.a,start,1440)
        old={'date_local':'2026-10-12','actual_energy_kwh':-999}
        self.a.connection.execute('insert into daily_comparisons values (?,?,?)',('2026-10-12','Europe/Prague',solar_archive.encode(old)));self.a.connection.commit()
        day=self.compare('2026-10-12T22:03:00Z')['days'][0]
        self.assertEqual(day['actual_energy_kwh'],48)
        self.assertIn('horizons',day)

    def test_default_archive_horizon_covers_entire_third_day(self):
        from addon_config import Config
        from solar_model import build_profile
        from tests.test_solar_model import ARRAYS,hours
        cfg=Config(options_path=str(Path(self.tmp.name)/'no-options.json'))
        issued=dt.datetime(2026,10,9,19,55,tzinfo=UTC)
        p=build_profile(hours(issued.replace(minute=0),120),ARRAYS,issued,'Europe/Prague',cfg.hourly_horizon_h)
        end=dt.datetime.fromisoformat(p['intervals'][-1]['interval_end_utc'].replace('Z','+00:00'))
        self.assertGreaterEqual(end,dt.datetime(2026,10,12,22,tzinfo=UTC))
