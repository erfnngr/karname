import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from insurance_engine import InsuranceInput, InsuranceRules, calculate_insurance

class InsuranceEngineTests(unittest.TestCase):
    def setUp(self):
        self.rules=InsuranceRules('test','test source',date(2026,1,1),date(2026,12,31),Decimal('7'),Decimal('20'),Decimal('3'),100,10000,True)
        self.item=InsuranceInput(date(2026,4,1),date(2026,4,30),30,30,1000,100,3000,2000,True)
    def test_seniority_and_benefits_are_not_counted_twice(self):
        result=calculate_insurance(self.item,self.rules)
        self.assertEqual((result['monthly_wage'],result['seniority_total'],result['insured_total'],result['gross_total']),(33000,3000,36000,38000))
        self.assertEqual((result['worker'],result['employer'],result['unemployment'],result['insurance_total']),(2520,7200,1080,10800))
    def test_unconfirmed_rules_and_invalid_days_block_calculation(self):
        with self.assertRaises(ValueError):calculate_insurance(self.item,replace(self.rules,approved=False))
        with self.assertRaises(ValueError):calculate_insurance(replace(self.item,insured_days=31),self.rules)
    def test_without_unemployment_and_outside_rules(self):
        self.assertEqual(calculate_insurance(replace(self.item,unemployment_applies=False),self.rules)['unemployment'],0)
        with self.assertRaises(ValueError):calculate_insurance(self.item,replace(self.rules,effective_to=date(2026,4,15)))
