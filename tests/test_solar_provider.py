import unittest
from providers.open_meteo import parse_hourly, merge_poa, provider_azimuth

class ProviderTests(unittest.TestCase):
    def test_dni_is_normal_not_horizontal(self):
        data={'hourly':{'time':['2026-10-11T12:00'], 'direct_radiation':[100],
                        'direct_normal_irradiance':[250], 'shortwave_radiation':[200]}}
        r=parse_hourly(data)[0]
        self.assertEqual(r['dni_w_m2'],250)
        self.assertEqual(r['interval_start_utc'],'2026-10-11T11:00:00Z')
        self.assertEqual(provider_azimuth(135),-45)
        self.assertEqual(provider_azimuth(202.5),22.5)
    def test_short_array_rejected(self):
        with self.assertRaises(ValueError):
            parse_hourly({'hourly':{'time':['2026-10-11T12:00'], 'shortwave_radiation':[1,2]}})
    def test_join_uses_timestamps(self):
        rows=parse_hourly({'hourly':{'time':['2026-10-11T12:00','2026-10-11T13:00']}})
        merge_poa(rows,{'hourly':{'time':['2026-10-11T13:00'], 'global_tilted_irradiance':[500]}},'jjz')
        self.assertIsNone(rows[0]['poa_w_m2']['jjz'])
        self.assertEqual(rows[1]['poa_w_m2']['jjz'],500)
