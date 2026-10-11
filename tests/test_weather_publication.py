import tests
import unittest
import datetime as dt
from weather_publication import daily_weather
from tests.test_solar_model import hours,UTC

class WeatherTests(unittest.TestCase):
    def test_local_calendar_and_missing_data(self):
        rows=hours(dt.datetime(2026,10,10,22,tzinfo=UTC),25)
        for row in rows: row.update(ghi_w_m2=100,cloud_cover_pct=0,precip_mm=0)
        out=daily_weather(rows,[],'Europe/Prague')
        d=next(r for r in out if r['date_local']=='2026-10-11')
        self.assertAlmostEqual(d['ghi_daily_total_mj_m2'],8.64)
        rows[0]['ghi_w_m2']=None
        self.assertIsNone(daily_weather(rows,[],'Europe/Prague')[0]['ghi_daily_total_mj_m2'])

    def test_hourly_weather_survives_dashboard_reconnect(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from weather_publication import publish_weather,HOURLY
        now=dt.datetime(2026,10,11,13,10,tzinfo=UTC)
        rows=hours(now.replace(minute=0),1)
        calls=[]
        publisher=SimpleNamespace(connected=True,publish_json=lambda topic,payload,**kw:calls.append((topic,payload,kw)))
        cfg=SimpleNamespace(latitude=50,longitude=14,timezone='Europe/Prague',site_id='default',log_raw=False,log_features=False)
        with patch('weather_publication.derive_hourly_features',return_value={}):
            publish_weather({'hourly':rows,'daily':[],'issue_time_utc':now.isoformat()},cfg,publisher,now)
        hourly=[r for r in calls if r[0].startswith('hourly/')]
        self.assertEqual(len(hourly),len(HOURLY))
        self.assertTrue(all(r[2].get('retain') is True for r in hourly))
        self.assertTrue(all(dt.datetime.fromisoformat(r[1]['ts_utc'])==now for r in hourly))
