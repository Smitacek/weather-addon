import tests
import sys
import importlib.util
import datetime as dt
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
sys.path.append(str(Path(__file__).resolve().parents[1]/'weather-dashboard'))
from mqtt_listener import DataStore
spec=importlib.util.spec_from_file_location('dashboard_main',Path(__file__).resolve().parents[1]/'weather-dashboard/main.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from solar_model import build_profile
from tests.test_solar_model import ARRAYS,hours,UTC

class DashboardTests(unittest.TestCase):
    def test_empty_and_stale_profiles(self):
        store=DataStore();client=TestClient(module.create_app(store))
        self.assertFalse(client.get('/api/solar').json()['valid'])
        old=dt.datetime(2020,1,1,tzinfo=UTC)
        profile=build_profile(hours(old,100),ARRAYS,old,'UTC')
        store.update_solar('profile',profile)
        store.update_solar('health',{'ts_utc':old.isoformat(),'age_s':0,'forecast_valid':True,'archive_ok':True})
        response=client.get('/api/solar').json()
        self.assertFalse(response['valid'])
    def test_rejects_older_or_invalid_profile(self):
        store=DataStore();now=dt.datetime.now(UTC)
        profile=build_profile(hours(now.replace(minute=0,second=0,microsecond=0),100),ARRAYS,now,'UTC')
        self.assertTrue(store.update_solar('profile',profile))
        self.assertFalse(store.update_solar('profile',{**profile,'issued_at_utc':'2020-01-01T00:00:00Z'}))
        self.assertFalse(store.update_solar('profile',{'schema_version':2,'intervals':[{}]*1000}))
        self.assertEqual(store.snapshot()['solar']['issue_id'],profile['issue_id'])
        self.assertFalse(store.update_solar('profile',{**profile,'array_config':[None]}))
        self.assertFalse(store.update_solar('profile',{**profile,'daily':[None]}))
    def test_assets_served_in_ingress(self):
        client=TestClient(module.create_app(DataStore()))
        self.assertEqual(client.get('/static/dashboard.js').status_code,200)
        self.assertIn('Předpověď',client.get('/').text)

    def test_comparison_period_aggregates_only_comparable_days(self):
        store=DataStore();client=TestClient(module.create_app(store))
        self.assertTrue(store.update_solar('comparison',{'schema_version':1,'timezone':'Europe/Prague','updated_at_utc':dt.datetime.now(UTC).isoformat(),'days':[
            {'date_local':'2026-10-11','expected_hours':24,'elapsed_hours':24,'actual_energy_kwh':8,'predicted_energy_kwh':10,'error_kwh':-2,'comparable':True,'coverage_fraction':1,'eligible_fraction':0,'curtailed_fraction':0,'hours':[]},
            {'date_local':'2026-10-12','expected_hours':24,'elapsed_hours':24,'actual_energy_kwh':2,'predicted_energy_kwh':10,'error_kwh':None,'comparable':False,'coverage_fraction':0.5,'eligible_fraction':0,'curtailed_fraction':0,'hours':[]}]}))
        result=client.get('/api/comparison?period=month&date=2026-10-12').json()
        self.assertEqual(result['summary']['comparable_days'],1)
        self.assertEqual(result['summary']['error_kwh'],-2)
        self.assertEqual(result['summary']['error_pct'],-20)
        self.assertEqual(result['summary']['mae_kwh'],2)
        self.assertEqual(client.get('/api/comparison?period=week&date=2026-10-12').json()['start_date'],'2026-10-12')
        self.assertEqual(client.get('/api/comparison?period=year').status_code,400)
        self.assertEqual(client.get('/api/comparison?period=day&date=bad').status_code,400)
    def test_comparison_missing_and_zero_forecast_percent(self):
        store=DataStore();client=TestClient(module.create_app(store))
        response=client.get('/api/comparison?period=day&date=2026-10-11')
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.json()['summary']['actual_energy_kwh'])
        self.assertTrue(store.update_solar('comparison',{'schema_version':1,'timezone':'Europe/Prague','updated_at_utc':dt.datetime.now(UTC).isoformat(),'days':[{'date_local':'2026-10-11','elapsed_hours':24,'expected_hours':24,'actual_energy_kwh':0,'predicted_energy_kwh':0,'error_kwh':0,'comparable':True,'coverage_fraction':1,'eligible_fraction':1,'curtailed_fraction':0,'hours':[]}]}))
        self.assertIsNone(client.get('/api/comparison?period=day&date=2026-10-11').json()['summary']['error_pct'])
        self.assertFalse(store.update_solar('comparison',{'schema_version':1,'timezone':'Europe/Prague','days':[None]}))

    def test_missing_dst_day_still_has_correct_calendar_length(self):
        client=TestClient(module.create_app(DataStore()))
        result=client.get('/api/comparison?period=day&date=2026-03-29').json()
        self.assertEqual(result['days'][0]['expected_hours'],23)
