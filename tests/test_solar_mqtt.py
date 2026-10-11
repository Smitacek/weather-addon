import tests
import unittest
from mqtt_helper import solar_discovery, MQTTPublisher

class MQTTTests(unittest.TestCase):
    def test_forecast_energy_is_not_total(self):
        cfg=solar_discovery('tomorrow_energy_kwh','default',900)
        self.assertEqual(cfg['device_class'],'energy')
        self.assertEqual(cfg['unit_of_measurement'],'kWh')
        self.assertNotIn('state_class',cfg)
        self.assertEqual(cfg['expire_after'],900)
        self.assertEqual(cfg['availability_mode'],'all')
    def test_mqtt_publish_error_reported(self):
        class Client:
            def publish(self,*args,**kw): return type('Result',(),{'rc':4})()
        p=MQTTPublisher('localhost',1883);p.client=Client()
        self.assertFalse(p.publish_json('solar/profile',{'test':1}))
        self.assertFalse(p.publish_json('solar/profile',{'bad':float('nan')}))
