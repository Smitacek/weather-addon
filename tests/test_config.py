import json
import tempfile
import unittest
from pathlib import Path
from addon_config import Config
from tests.test_solar_model import ARRAYS

class ConfigTests(unittest.TestCase):
    def load(self,options):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'options.json'; p.write_text(json.dumps(options))
            return Config(options_path=p)
    def test_legacy_disabled(self):
        self.assertFalse(self.load({}).solar_enabled)
    def test_two_arrays(self):
        c=self.load({'solar_enabled':True,'pv_arrays':ARRAYS,'timezone':'Europe/Prague'})
        self.assertEqual(len(c.pv_arrays),2)
    def test_bad_configuration(self):
        for raw in [{'solar_enabled':True},{'units':'imperial'},{'timezone':'invalid'},
                    {'latitude':91},{'provider':'openweathermap'}, {'update_interval':0}]:
            with self.subTest(raw=raw), self.assertRaises(ValueError): self.load(raw)
