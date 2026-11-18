import unittest
from insurance_payroll_compare import compare,suggestions,payroll_options

class CompareTests(unittest.TestCase):
    def test_options_show_only_same_company_period_and_current_confirmation(self):
        def batch(id,company,period,version=1):return {'id':id,'kind':'payroll_batch','company_id':company,'version':version,'title':id,'payload':{'period':period}}
        def confirmation(id,company,version):return {'kind':'payroll_confirmation','company_id':company,'payload':{'payroll_batch_id':id,'batch_version':version}}
        records=[batch('a','mana','1405/08',2),batch('b','mana','1405/08'),batch('other','arka','1405/08'),batch('later','mana','1405/09'),confirmation('a','mana',1),confirmation('b','mana',1),confirmation('a','arka',2)]
        result=payroll_options(records,'mana','۱۴۰۵/۰۸')
        self.assertEqual([(r['id'],ok) for r,ok in result],[('b',True),('a',False)])
    def test_suggestions_do_not_round_or_infer_benefits(self):
        slip={'days':'۳۰','period_days':'۳۰','base':'۳۰۰۰','seniority':'۹۰۰'}
        self.assertEqual(suggestions(slip,30),{'days':'30','daily_wage':'100','daily_seniority':'30'})
        self.assertNotIn('daily_wage',suggestions({**slip,'base':'3001'},30))
        self.assertEqual(suggestions(slip,31),{})
    def test_matches_employee_code_and_reports_differences(self):
        draft={'period':'1405/08','rows':[{'profile_id':'p','days':'30'}]};batch={'period':'1405/08','slips':[{'code':'۰۰۱','days':'29','base':'300000'}]}
        result=compare(draft,batch,{'p':{'employee_id':'e'}},{'e':{'employee_code':'001'}})
        self.assertIn('متفاوت',result[0]['message']);self.assertEqual(result[0]['payroll_base'],'300000')
        self.assertIn('قابل مشاهده نیست',compare(draft,batch,{},{} )[0]['message'])
        with self.assertRaises(ValueError):compare(draft,{**batch,'period':'1405/09'},{},{})
        with self.assertRaises(ValueError):compare(draft,{**batch,'slips':batch['slips']*2},{},{})
