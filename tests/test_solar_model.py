import unittest
import datetime as dt
from solar_model import dc_power_w, build_profile, normalize_arrays

UTC = dt.timezone.utc
ARRAYS = [dict(id='jjz', capacity_kw=3.5, tilt_deg=90, azimuth_deg=202.5,
               gamma_per_c=-0.004, noct_c=20, loss_fraction=0.14,
               shading_factor=1, geometry_confirmed=False),
          dict(id='jv', capacity_kw=3.5, tilt_deg=90, azimuth_deg=135,
               gamma_per_c=-0.004, noct_c=20, loss_fraction=0.14,
               shading_factor=1, geometry_confirmed=False)]

def hours(start, count, poa=1000):
    return [dict(interval_start_utc=(start+dt.timedelta(hours=i)).isoformat(),
                 interval_end_utc=(start+dt.timedelta(hours=i+1)).isoformat(),
                 temp_2m_c=25, poa_w_m2={'jjz':poa, 'jv':poa}) for i in range(count)]

class ModelTests(unittest.TestCase):
    def test_dc_stc_and_no_ac_clipping(self):
        self.assertAlmostEqual(dc_power_w(1000, 25, ARRAYS[0]),3010)
        self.assertGreater(dc_power_w(1400,25,ARRAYS[0]),3500)
        self.assertEqual(dc_power_w(0,25,ARRAYS[0]),0)
    def test_missing_is_not_zero(self):
        with self.assertRaises(ValueError): dc_power_w(float('nan'),25,ARRAYS[0])
        h=hours(dt.datetime(2026,10,11,tzinfo=UTC),24)
        h[5]['poa_w_m2']['jv']=None
        p=build_profile(h,ARRAYS,dt.datetime(2026,10,10,tzinfo=UTC),'UTC')
        self.assertIsNone(p['daily'][0]['energy_kwh'])
        self.assertFalse(p['daily'][0]['complete'])
    def test_daily_sum_and_partial_hour(self):
        start=dt.datetime(2026,10,11,tzinfo=UTC)
        p=build_profile(hours(start,96),ARRAYS,start+dt.timedelta(minutes=30),'UTC')
        self.assertAlmostEqual(p['daily'][0]['remaining_energy_kwh'],141.47)
        self.assertAlmostEqual(p['daily'][1]['energy_kwh'],144.48)
        self.assertEqual(len(p['intervals']),73)
    def test_dst_days(self):
        for start, day, total in [(dt.datetime(2026,3,28,23,tzinfo=UTC),'2026-03-29',23),
                                  (dt.datetime(2026,10,24,22,tzinfo=UTC),'2026-10-25',25)]:
            p=build_profile(hours(start,100),ARRAYS,start,'Europe/Prague')
            d=next(d for d in p['daily'] if d['date_local']==day)
            self.assertEqual(d['expected_hours'],total)
            self.assertAlmostEqual(d['energy_kwh'],6.02*total)
    def test_array_validation(self):
        self.assertEqual(len(normalize_arrays({'pv_arrays':ARRAYS})),2)
        with self.assertRaises(ValueError): normalize_arrays({'pv_arrays':[ARRAYS[0],ARRAYS[0]]})
        with self.assertRaises(ValueError): normalize_arrays({'pv_arrays':[dict(ARRAYS[0],tilt_deg=110)]})

