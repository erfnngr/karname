import unittest
from insurance_preview import calculate_preview


class InsurancePreviewTests(unittest.TestCase):
    def setUp(self):
        self.data=dict(period='۱۴۰۵/۰۸',days='۳۰',daily_wage='۱۰۰۰',daily_seniority='۱۰۰',
                       insured_benefits='۳۰۰۰',non_insured_benefits='۲۰۰۰',minimum_daily='۱۰۰',maximum_daily='۱۰۰۰۰',
                       worker_rate='۷',employer_rate='۲۰',unemployment_rate='۳',source='منبع آزمایشی',rules_version='test',
                       approved=True,unemployment_applies=True)

    def test_values_are_translated_and_computed_with_integer_rials(self):
        value=calculate_preview(self.data)
        self.assertEqual(value['insured_total'],'36000')
        self.assertEqual(value['insurance_total'],'10800')

    def test_unconfirmed_rules_and_bad_input_are_rejected(self):
        with self.assertRaises(ValueError):calculate_preview({**self.data,'approved':False})
        with self.assertRaises(ValueError):calculate_preview({**self.data,'period':'۱۴۰۵/۱۳'})
        with self.assertRaises(ValueError):calculate_preview({**self.data,'daily_wage':'1.2'})
