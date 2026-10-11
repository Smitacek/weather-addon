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
