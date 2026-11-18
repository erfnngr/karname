import unittest
from insurance_period_compare import compare_periods

class PeriodCompareTests(unittest.TestCase):
    def test_compares_only_same_workshop_and_tracks_changes(self):
        row=dict(profile_id='p',days='30',daily_wage='100',daily_seniority='0',insured_benefits='0',non_insured_benefits='0',unemployment_applies=True)
        old=dict(title='a',workshop_id='w',period='1405/07',list_no='1',rows=[row]);new={**old,'period':'1405/08','rows':[{**row,'days':'25'}]}
        self.assertTrue(any('روز بیمه' in x['message'] for x in compare_periods(new,old)))
        with self.assertRaises(ValueError):compare_periods({**new,'workshop_id':'other'},old)
