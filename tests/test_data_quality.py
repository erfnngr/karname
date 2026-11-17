import unittest
from data_quality import inspect

class DataQualityTests(unittest.TestCase):
    def test_findings_scoped_to_company_and_non_destructive(self):
        records=[{'id':'a','company_id':'mana','kind':'client','payload':{'title':'الف','national_id':'123'}},{'id':'b','company_id':'mana','kind':'client','payload':{'title':'ب','national_id':'123'}},{'id':'c','company_id':'arka','kind':'client','payload':{'title':'پ','national_id':'123'}},{'id':'i','company_id':'mana','kind':'invoice','payload':{'status':'issued','totals':{'total':'100'},'settlement_summary':{'received':'150'}}}]
        findings=inspect(records,{'checks':[],'transactions':[]},'mana')
        self.assertEqual(sum('تکرار' in x['reason'] for x in findings),2)
        self.assertTrue(any('بیش از' in x['reason'] for x in findings));self.assertFalse(any(x['id']=='c' for x in findings));self.assertEqual(len(records),4)
