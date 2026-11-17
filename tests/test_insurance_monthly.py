import tempfile
import unittest
from pathlib import Path
from org_store import Store,DomainError
from insurance_monthly import calculate_draft

class InsuranceMonthlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name));self.a=self.s.bootstrap('admin','pass','مدیر')
        self.w=self.s.save_record(self.a,'insurance_workshop',{'title':'کارگاه','workshop_code':'۰۰۱'},'mana')
        e=self.s.save_record(self.a,'employee',{'title':'کارمند','employee_code':'001'},'mana')
        self.p=self.s.save_record(self.a,'insurance_employee',{'title':'کارمند','workshop_id':self.w['id'],'employee_id':e['id'],'national_id':'۰۰۱۲۳۴۵۶۷۸'},'mana')
        self.d={'title':'آبان','workshop_id':self.w['id'],'period':'۱۴۰۵/۰۸','list_no':'۰۰۱','rows':[{'profile_id':self.p['id'],'days':'۳۰','daily_wage':'۱۰۰۰','daily_seniority':'','insured_benefits':'','non_insured_benefits':'','unemployment_applies':None}]}
    def tearDown(self):self.tmp.cleanup()
    def test_save_draft_preserves_numbers_and_never_claims_submission(self):
        r=self.s.save_record(self.a,'insurance_list',self.d,'mana')
        self.assertEqual(r['payload']['period'],'1405/08');self.assertEqual(r['payload']['list_no'],'001');self.assertEqual(r['payload']['rows'][0]['days'],'30');self.assertEqual(r['payload']['status'],'draft')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',{**self.d,'status':'submitted'},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',self.d,'mana')
        with self.assertRaises(DomainError):self.s.delete_record(self.a,self.p['id'],self.p['version'])
    def test_cannot_mix_company_or_exceed_days(self):
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',self.d,'arka')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',{**self.d,'rows':[dict(self.d['rows'][0],days='31')]},'mana')
    def test_group_calculation_blocks_incomplete_rows(self):
        rules={'worker_rate':'7','employer_rate':'20','unemployment_rate':'3','minimum_daily':'100','maximum_daily':'10000','source':'آزمایشی','rules_version':'test','approved':True}
        self.assertTrue(calculate_draft(self.d,rules)['errors'])
        row={**self.d['rows'][0],'daily_seniority':'100','insured_benefits':'3000','non_insured_benefits':'2000','unemployment_applies':True}
        result=calculate_draft({**self.d,'rows':[row]},rules)
        self.assertEqual(result['totals']['insurance_total'],'10800');self.assertFalse(result['errors'])
        with self.assertRaises(ValueError):calculate_draft(self.d,{**rules,'approved':False})
