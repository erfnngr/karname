import unittest
from settlement_logic import validate

class SettlementTest(unittest.TestCase):
    def test_partial_cash_bank_and_check_are_distinct(self):
        result=validate('1000',[{'kind':'cash','amount':'100'},{'kind':'bank','amount':'200','bank_account_id':'b'},{'kind':'check','amount':'500','check_id':'c'}])
        self.assertEqual(result,{'received':'300','pending_checks':'500','unallocated':'200','uncollected':'700'})
    def test_overpayment_duplicate_and_fractional_rials_rejected(self):
        cases=[[{'kind':'cash','amount':'1001'}],[{'kind':'check','amount':'1','check_id':'c'},{'kind':'check','amount':'1','check_id':'c'}],[{'kind':'cash','amount':'1.5'}],[{'kind':'bank','amount':'1'}]]
        for payments in cases:
            with self.subTest(payments=payments),self.assertRaises(ValueError):validate('1000',payments)
