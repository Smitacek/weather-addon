import tests
import unittest
import importlib.util

class CorrectionsTests(unittest.TestCase):
    def analyze(self,days):
        self.assertIsNotNone(importlib.util.find_spec('solar_corrections'),'Correction recommendation analysis is missing')
        from solar_corrections import recommend
        return recommend(days)
    def dataset(self,quality=1,actual=0.8):
        days=[]
        for d in range(1,11):
            rows=[[f'2026-10-{d:02}T{h:02}:00Z',actual,1,1,quality,0] for h in range(10,20)]
            days.append({'date_local':f'2026-10-{d:02}','partial':False,'hours':rows,'horizons':{str(k):{'hourly_energy_kwh':[1]*10} for k in [1,2,3]}})
        return days
    def test_unknown_or_curtailed_data_never_recommends_adjustment(self):
        r=self.analyze(self.dataset(0))['1']
        self.assertIsNone(r['factor']);self.assertEqual(r['eligible_hours'],0)
    def test_factor_is_validated_on_later_days(self):
        r=self.analyze(self.dataset())['1']
        self.assertAlmostEqual(r['factor'],0.8)
        self.assertEqual(r['status'],'validated')
        self.assertGreater(r['validation_improvement_pct'],99)
        self.assertGreater(r['validation_start_date'],r['training_end_date'])
    def test_changed_validation_weather_rejects_wrong_correction(self):
        days=self.dataset()
        for day in days[7:]:
            for row in day['hours']:row[1]=1.2
        r=self.analyze(days)['1']
        self.assertIsNone(r['factor']);self.assertEqual(r['status'],'not_improved')
