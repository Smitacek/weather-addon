import tests
import unittest
import datetime as dt
from solar_telemetry import TelemetryCollector
from tests.test_solar_model import UTC

class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,10,11,12,tzinfo=UTC)
        self.topics={k:k for k in ['pv1_power_w','pv2_power_w','pv1_voltage_v','pv1_current_a',
          'ac_power_w','battery1_soc','battery2_soc','battery1_power_w','battery2_power_w',
          'inverter_available','inverter_connection','bms_connection','battery1_available','battery2_available']}
        self.c=TelemetryCollector(self.topics)
    def ingest(self,k,value,offset=0,retained=False):
        self.c.ingest(k,str(value).encode(),self.now+dt.timedelta(seconds=offset),retained)
    def full(self):
        for k,v in [('pv1_power_w',1000),('pv2_power_w',1500),('ac_power_w',10),
                    ('battery1_soc',99),('battery2_soc',99),('battery1_power_w',200),('battery2_power_w',200)]:self.ingest(k,v)
        for k in ['inverter_available','inverter_connection','bms_connection','battery1_available','battery2_available']:self.ingest(k,'online',retained=True)
    def test_retained_scalar_not_fresh(self):
        self.ingest('pv1_power_w',1000,retained=True)
        self.assertIsNone(self.c.snapshot(self.now)['values']['pv1_power_w'])
    def test_offline_invalidates_values(self):
        self.full();self.ingest('inverter_available','offline')
        self.assertIsNone(self.c.snapshot(self.now)['values']['pv1_power_w'])
    def test_charge_and_low_load_not_curtailed(self):
        self.full()
        self.assertEqual(self.c.snapshot(self.now)['quality'],'ambiguous')
        self.ingest('battery1_power_w',0);self.ingest('battery2_power_w',0)
        self.assertEqual(self.c.snapshot(self.now)['quality'],'suspected_curtailed')
    def test_stale_and_out_of_order(self):
        self.full();self.ingest('pv1_power_w',800,offset=-60)
        self.assertEqual(self.c.snapshot(self.now)['values']['pv1_power_w'],1000)
        self.assertIsNone(self.c.snapshot(self.now+dt.timedelta(seconds=91))['values']['pv1_power_w'])
    def test_bad_payload(self):
        self.ingest('pv1_power_w','NaN')
        self.assertIsNone(self.c.snapshot(self.now)['values']['pv1_power_w'])
