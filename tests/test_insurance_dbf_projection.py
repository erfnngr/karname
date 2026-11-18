import unittest
from insurance_dbf_projection import worker_projection,workshop_projection

class ProjectionTests(unittest.TestCase):
    def test_projection_keeps_unknown_fields_open_and_preserves_identifiers(self):
        draft={'period':'1405/08','list_no':'001'};workshop={'workshop_code':'0000000123'}
        line={'days':'30','daily_wage':'1000','daily_seniority':'100','spouse_benefit':'500'}
        person={'profile':{'insurance_number':'00001234','first_name':'آزمایش','gender':'مرد','birth_date':'1400/01/02'}}
        amounts={'monthly_wage':'33000','insured_total':'36000','gross_total':'38000','worker':'2520'}
        result=worker_projection(workshop,draft,line,person,amounts);f=result['fields']
        self.assertEqual(f['DSW_ID1'],'00001234');self.assertEqual(f['DSW_BDATE'],'14000102');self.assertEqual(f['DSW_INC'],100);self.assertEqual(f['DSW_SPOUSE'],'500')
        self.assertNotIn('DSW_MAZ',f);self.assertIn('DSW_MAZ',result['unresolved']);self.assertIn('DSW_LNAME',result['missing'])
    def test_workshop_reconciles_each_total_and_does_not_guess(self):
        keys={'monthly_wage':'33000','seniority_total':'3000','spouse_benefit':'500','insured_total':'36000','gross_total':'38000','worker':'2520','employer':'7200','unemployment':'1080','insurance_total':'10800'}
        draft={'period':'1405/08','list_no':'001','rows':[{'profile_id':'p','days':'30'}]}
        result={'rows':[{'profile_id':'p','amounts':keys}],'totals':{**keys,'days':'30'}}
        projected=workshop_projection({'title':'test','workshop_code':'001'},draft,result)
        self.assertEqual(projected['fields']['DSK_INC'],3000);self.assertEqual(projected['fields']['DSK_SPOUSE'],500);self.assertIn('DSK_BIC',projected['unresolved']);self.assertNotIn('DSK_BIC',projected['fields'])
        with self.assertRaises(ValueError):workshop_projection({},draft,{**result,'totals':{**result['totals'],'insured_total':'1'}})
