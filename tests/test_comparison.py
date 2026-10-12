import tests
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from solar_archive import SolarArchive
from solar_model import iso
UTC=dt.timezone.utc

def forecast(a,start,hours,issued,key='early',power=1000):
    a.save_forecast({'issue_id':key,'issued_at_utc':issued,'intervals':[
        {'interval_start_utc':iso(start+dt.timedelta(hours=h)),
         'interval_end_utc':iso(start+dt.timedelta(hours=h+1)),
         'power_w':power,'energy_kwh':power/1000} for h in range(hours)]})
def observe(a,start,minutes,quality='eligible'):
    for m in range(minutes+1):
        t=start+dt.timedelta(minutes=m)
        a.save_observation({'ts_utc':iso(t),'values':{'pv1_power_w':1000,'pv2_power_w':1000},'quality':quality})

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=str(Path(self.tmp.name)/'solar.db');self.a=SolarArchive(self.path)
    def tearDown(self):self.a.close();self.tmp.cleanup()
    def compare(self,now):
        self.assertTrue(callable(getattr(self.a,'comparison_summary',None)), 'Comparison of archived 22:00 forecasts is missing')
        return self.a.comparison_summary(now,'Europe/Prague',400)
    def test_2200_baseline_rejects_later_revision(self):
        start=dt.datetime(2026,10,11,22,tzinfo=UTC)
        forecast(self.a,start,24,'2026-10-11T19:55:00Z')
        forecast(self.a,start,24,'2026-10-11T20:01:00Z','late',9000)
        observe(self.a,start,1440)
        day=self.compare('2026-10-12T22:00:00Z')['days'][0]
        self.assertEqual(day['issue_id'],'early');self.assertEqual(day['cutoff_utc'],'2026-10-11T20:00:00Z')
        self.assertAlmostEqual(day['predicted_energy_kwh'],24);self.assertAlmostEqual(day['actual_energy_kwh'],48)
        self.assertAlmostEqual(day['error_kwh'],24);self.assertAlmostEqual(day['error_pct'],100)
    def test_partial_today_compares_only_elapsed_time(self):
        start=dt.datetime(2026,10,11,22,tzinfo=UTC)
        forecast(self.a,start,24,'2026-10-11T19:55:00Z');observe(self.a,start,720)
        day=self.compare('2026-10-12T10:00:00Z')['days'][0]
        self.assertTrue(day['partial']);self.assertAlmostEqual(day['full_forecast_energy_kwh'],24)
        self.assertAlmostEqual(day['predicted_energy_kwh'],12);self.assertAlmostEqual(day['actual_energy_kwh'],24)
    def test_missing_measurements_never_become_zero_or_accuracy(self):
        start=dt.datetime(2026,10,11,22,tzinfo=UTC)
        forecast(self.a,start,24,'2026-10-11T19:55:00Z');observe(self.a,start,720)
        day=self.compare('2026-10-12T22:00:00Z')['days'][0]
        self.assertAlmostEqual(day['coverage_fraction'],0.5);self.assertIsNone(day['error_pct']);self.assertIsNone(day['error_kwh'])
    def test_dst_day_lengths(self):
        for start,hours,issued,end in [('2026-03-28T23:00:00Z',23,'2026-03-28T20:55:00Z','2026-03-29T22:00:00Z'),('2026-10-24T22:00:00Z',25,'2026-10-24T19:55:00Z','2026-10-25T23:00:00Z')]:
            with self.subTest(hours=hours):
                self.a.connection.execute('delete from forecasts');self.a.connection.execute('delete from observations')
                t=dt.datetime.fromisoformat(start.replace('Z','+00:00'));forecast(self.a,t,hours,issued);observe(self.a,t,hours*60)
                day=self.compare(end)['days'][-1]
                self.assertEqual(day['expected_hours'],hours);self.assertEqual(len(day['hours']),hours)
                self.assertAlmostEqual(day['predicted_energy_kwh'],hours);self.assertAlmostEqual(day['actual_energy_kwh'],hours*2)
    def test_curtailment_is_visible_and_not_calibration_eligible(self):
        start=dt.datetime(2026,10,11,22,tzinfo=UTC)
        forecast(self.a,start,24,'2026-10-11T19:55:00Z');observe(self.a,start,1440,'suspected_curtailed')
        day=self.compare('2026-10-12T22:00:00Z')['days'][0]
        self.assertAlmostEqual(day['curtailed_fraction'],1);self.assertEqual(day['eligible_fraction'],0)
    def test_no_previous_evening_forecast_is_explicit(self):
        start=dt.datetime(2026,10,11,22,tzinfo=UTC);observe(self.a,start,1440)
        day=self.compare('2026-10-12T22:00:00Z')['days'][0]
        self.assertIsNone(day['predicted_energy_kwh']);self.assertIsNone(day['error_pct']);self.assertIsNone(day['issue_id'])

    def test_offset_samples_close_hour_and_day_boundaries(self):
        start=dt.datetime(2026,10,11,22,tzinfo=UTC)
        forecast(self.a,start,24,'2026-10-11T19:55:00Z',power=2000)
        observe(self.a,start-dt.timedelta(seconds=30),1441)
        day=next(d for d in self.compare('2026-10-12T22:03:00Z')['days'] if d['date_local']=='2026-10-12')
        self.assertAlmostEqual(day['actual_energy_kwh'],48)
        self.assertAlmostEqual(sum(r[1] for r in day['hours']),48)
        self.assertAlmostEqual(day['error_kwh'],0)
        self.assertEqual(day['coverage_fraction'],1)
