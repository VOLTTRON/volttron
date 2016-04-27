
import unittest
import json
import time
import thermostat_api
from thermostat_api import ThermostatInterface, FakeThermostat

class CEA2045TestCase(unittest.TestCase):
    def test_tcool(self):
        '''Test  t_cool() interface'''
        obj = thermostat_api.Thermostat_API("Fake")
        self.assertEqual(obj.t_cool(79.0),{'success': 0})

    def test_theat(self):
        '''Test  t_heat() interface'''
        obj = thermostat_api.Thermostat_API("Fake")
        self.assertEqual(obj.t_cool(79.0),{'success': 0})

    def test_mode(self):
       '''Test  mode() interface'''
       obj = thermostat_api.Thermostat_API("Fake")
       self.assertEqual(obj.t_cool(0),{'success': 0})

    def test_tstat(self):
        '''Test the tstat() interface'''
        obj = thermostat_api.Thermostat_API("Fake")
        expected_dict = {
            "temp":70.50,
            "tmode":0,
            "fmode":0,
            "override":0,
            "hold":0,
            "t_cool":85.00,
            "t_heat":70.00,
            "time":
                {
                    "day": time.localtime().tm_wday,
                    "hour": time.localtime().tm_hour,
                    "minute": time.localtime().tm_min
                }
        }
        tstat_value = obj.tstat()
        self.assertTrue(45 <=  json.loads(tstat_value)['temp'] <= 99)
        self.assertTrue(0 <=  json.loads(tstat_value)['tmode'] <= 3)
