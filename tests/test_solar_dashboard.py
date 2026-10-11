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
