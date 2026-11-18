import unittest
from insurance_validation import review

class InsuranceValidationTests(unittest.TestCase):
    def test_warns_for_excess_days_and_omitted_overlapping_person(self):
        d=dict(title='آبان',workshop_id='w',period='1405/08',list_no='1',rows=[dict(profile_id='p',days='25',daily_wage='1',daily_seniority='0',spouse_benefit='0',insured_benefits='0',non_insured_benefits='0',unemployment_applies=True)])
        profiles={'p':dict(employee_id='e',workshop_id='w',start_date='1405/08/20'), 'omitted':dict(employee_id='e2',workshop_id='w',start_date='1405/01/01'), 'other':dict(employee_id='e3',workshop_id='x',start_date='1405/01/01')}
        result=review(d,{'workshop_code':'001'},profiles,{'e':{},'e2':{},'e3':{}})
        self.assertTrue(any(i['profile_id']=='p' and 'بیشتر' in i['message'] for i in result))
        self.assertTrue(any(i['profile_id']=='omitted' and 'در لیست نیست' in i['message'] for i in result))
        self.assertFalse(any(i['profile_id']=='other' for i in result))
    def test_missing_values_and_midmonth_are_distinguished(self):
        d=dict(title='آبان',workshop_id='w',period='1405/08',list_no='1',rows=[dict(profile_id='p',days='20',daily_wage='',daily_seniority='0',insured_benefits='0',non_insured_benefits='0',unemployment_applies=None)])
        p={'p':dict(employee_id='e',workshop_id='w',start_date='1405/08/10')}
        result=review(d,{'workshop_code':'001'},p,{'e':{}})
        self.assertTrue(any(i['severity']=='error' and 'مزد روزانه' in i['message'] for i in result))
        self.assertTrue(any(i['severity']=='warning' and 'میانه ماه' in i['message'] for i in result))
        self.assertFalse(any('سنوات روزانه' in i['message'] for i in result))
