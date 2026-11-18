import unittest
from types import SimpleNamespace
from react_home_bridge import ReactHomeBridge
from storage import jalali_date

class HomeBriefingFreshnessTests(unittest.TestCase):
    def test_cached_weather_is_not_presented_as_current(self):
        bridge=SimpleNamespace(panel=SimpleNamespace(owner=SimpleNamespace(org=SimpleNamespace(birthdays=[]))))
        weather={'has_data':True,'cached':True,'current':{'label':'آفتابی','temp':'29','kind':'sun'}}
        result=ReactHomeBridge._build_briefing(bridge,today=jalali_date(1405,8,1),weekday='جمعه',reminders=[],reminders_total=0,activity={},occasions=[],weather_payload=weather)
        self.assertIn('ذخیره‌شده',result['summary']);self.assertNotIn('29°',result['summary'])
