import tempfile
import unittest
from pathlib import Path
from org_store import Store,DomainError
from insurance_monthly import calculate_draft,eligible_profiles_for_period

class InsuranceMonthlyTests(unittest.TestCase):
    def test_choose_period_people_without_guessing_incomplete_dates(self):
        def profile(id,start,end='',workshop='w'):
            return {'id':id,'payload':{'workshop_id':workshop,'start_date':start,'end_date':end}}
        records=[profile('active','1405/07/20'),profile('join','1405/08/30'),profile('left','1405/08/01','1405/08/02'),profile('past','1405/01/01','1405/07/30'),profile('future','1405/09/01'),profile('missing',''),profile('bad','1405/08/20','1405/08/01'),profile('other','1405/01/01',workshop='other')]
        eligible,review=eligible_profiles_for_period(records,'w','۱۴۰۵/۰۸')
        self.assertEqual(eligible,['active','join','left']);self.assertEqual(review,['missing','bad'])
        with self.assertRaises(ValueError):eligible_profiles_for_period(records,'w','1405/13')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name));self.a=self.s.bootstrap('admin','pass','مدیر')
        self.w=self.s.save_record(self.a,'insurance_workshop',{'title':'کارگاه','workshop_code':'۰۰۱'},'mana')
        e=self.s.save_record(self.a,'employee',{'title':'کارمند','employee_code':'001'},'mana')
        self.p=self.s.save_record(self.a,'insurance_employee',{'title':'کارمند','workshop_id':self.w['id'],'employee_id':e['id'],'national_id':'۰۰۱۲۳۴۵۶۷۸'},'mana')
        self.d={'title':'آبان','workshop_id':self.w['id'],'period':'۱۴۰۵/۰۸','list_no':'۰۰۱','rows':[{'profile_id':self.p['id'],'days':'۳۰','daily_wage':'۱۰۰۰','daily_seniority':'','insured_benefits':'','non_insured_benefits':'','unemployment_applies':None}]}
    def tearDown(self):self.tmp.cleanup()
    def test_workshop_scope_restricts_related_records_and_refreshes_cache(self):
        one=self.s.save_user(self.a,dict(username='finance1',password='pass',fullname='مالی یک',memberships=[dict(company_id='mana',role='finance')]))['id']
        two=self.s.save_user(self.a,dict(username='finance2',password='pass',fullname='مالی دو',memberships=[dict(company_id='mana',role='finance')]))['id']
        first=self.s.user(one);second=self.s.user(two)
        row={**self.d['rows'][0],'daily_seniority':'100','spouse_benefit':'500','insured_benefits':'2500','non_insured_benefits':'2000','unemployment_applies':True}
        draft=self.s.save_record(self.a,'insurance_list',{**self.d,'rows':[row]},'mana')
        evidence=self.s.save_record(self.a,'insurance_evidence',dict(title='رسید',insurance_list_id=draft['id'],kind='ارسال دستی',date='1405/08/21',reference='ref',amount='',notes=''),'mana')
        rules=self.s.save_record(self.a,'insurance_rules',dict(title='آزمایشی',rules_version='acl',source='آزمایشی',effective_from='1405/01/01',effective_to='1405/12/29',worker_rate='7',employer_rate='20',unemployment_rate='3',minimum_daily='100',maximum_daily='10000',approved=True),'mana')
        calc=self.s.save_record(self.a,'insurance_calculation',dict(title='محاسبه',insurance_list_id=draft['id'],rules_id=rules['id']),'mana')
        review=self.s.save_record(self.a,'insurance_review',dict(title='بررسی',calculation_id=calc['id'],notes='هشدارها بررسی شد'),'mana')
        scoped=(self.p,draft,evidence,calc,review)
        self.assertTrue(all(self.s.readable(second,r) for r in (self.w,*scoped)))
        revision=self.s.records_revision();known=[r['id'] for r in (self.w,*scoped)]
        restricted=self.s.save_record(self.a,'insurance_workshop',{**self.w['payload'],'access_users':[one]},'mana',self.w['id'],self.w['version'])
        for r in (restricted,*scoped):
            self.assertTrue(self.s.readable(first,r));self.assertFalse(self.s.readable(second,r))
        delta=self.s.workspace_records_delta(second,revision,known)
        self.assertTrue(set(known).issubset(set(delta['removed'])))
        with self.assertRaises(DomainError):self.s.save_record(first,'insurance_workshop',{**restricted['payload'],'access_users':[one,two]},'mana',restricted['id'],restricted['version'])
        with self.assertRaises(DomainError):self.s.save_record(second,'insurance_list',{**self.d,'list_no':'2'},'mana')
        reopened=self.s.save_record(self.a,'insurance_workshop',{**restricted['payload'],'access_users':None},'mana',restricted['id'],restricted['version'])
        self.assertTrue(self.s.readable(second,reopened));self.assertTrue(self.s.readable(second,draft))
    def test_save_draft_preserves_numbers_and_never_claims_submission(self):
        r=self.s.save_record(self.a,'insurance_list',self.d,'mana')
        self.assertEqual(r['payload']['period'],'1405/08');self.assertEqual(r['payload']['list_no'],'001');self.assertEqual(r['payload']['rows'][0]['days'],'30');self.assertEqual(r['payload']['status'],'draft')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',{**self.d,'status':'submitted'},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',self.d,'mana')
        with self.assertRaises(DomainError):self.s.delete_record(self.a,self.p['id'],self.p['version'])
    def test_cannot_mix_company_or_exceed_days(self):
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',self.d,'arka')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',{**self.d,'rows':[dict(self.d['rows'][0],days='31')]},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',{**self.d,'rows':[dict(self.d['rows'][0],payroll_batch_id='a'*32)]},'mana')
    def test_group_calculation_blocks_incomplete_rows(self):
        rules={'worker_rate':'7','employer_rate':'20','unemployment_rate':'3','minimum_daily':'100','maximum_daily':'10000','source':'آزمایشی','rules_version':'test','approved':True}
        self.assertTrue(calculate_draft(self.d,rules)['errors'])
        row={**self.d['rows'][0],'daily_seniority':'100','spouse_benefit':'500','insured_benefits':'2500','non_insured_benefits':'2000','unemployment_applies':True}
        result=calculate_draft({**self.d,'rows':[row]},rules)
        self.assertEqual(result['totals']['insurance_total'],'10800');self.assertEqual(result['totals']['spouse_benefit'],'500');self.assertFalse(result['errors'])
        with self.assertRaises(ValueError):calculate_draft(self.d,{**rules,'approved':False})
    def test_breakdown_does_not_add_benefits_twice(self):
        rules={'worker_rate':'7','employer_rate':'20','unemployment_rate':'3','minimum_daily':'100','maximum_daily':'10000','source':'آزمایشی','rules_version':'test','approved':True}
        row={**self.d['rows'][0],'daily_seniority':'100','spouse_benefit':'500','insured_benefits':'2500','non_insured_benefits':'2000','unemployment_applies':True,'benefit_breakdown':[{'title':'مسکن','amount':'2500','insured':True},{'title':'پرداخت غیرمشمول','amount':'2000','insured':False}]}
        self.assertEqual(calculate_draft({**self.d,'rows':[row]},rules)['totals']['insured_total'],'36000')
        row['benefit_breakdown'][0]['amount']='2499'
        self.assertTrue(calculate_draft({**self.d,'rows':[row]},rules)['errors'])
        row['benefit_breakdown'][0]['title']='حق تأهل'
        with self.assertRaises(ValueError):calculate_draft({**self.d,'rows':[row]},rules)
    def test_incomplete_calculation_reports_person_and_field(self):
        draft=self.s.save_record(self.a,'insurance_list',{**self.d,'rows':[{**self.d['rows'][0],'unemployment_applies':True}]},'mana')
        rules=self.s.save_record(self.a,'insurance_rules',dict(title='آزمایشی',rules_version='r1',source='منبع',effective_from='1405/01/01',effective_to='1405/12/29',worker_rate='7',employer_rate='20',unemployment_rate='3',minimum_daily='100',maximum_daily='10000',approved=True),'mana')
        with self.assertRaises(DomainError) as caught:self.s.save_record(self.a,'insurance_calculation',dict(title='محاسبه',insurance_list_id=draft['id'],rules_id=rules['id']),'mana')
        self.assertIn('کارمند',str(caught.exception));self.assertIn('سنوات',str(caught.exception))
    def test_manual_evidence_is_distinct_and_freezes_linked_draft(self):
        r=self.s.save_record(self.a,'insurance_list',self.d,'mana')
        p=dict(title='رسید آزمایشی',insurance_list_id=r['id'],kind='پرداخت دستی',date='1405/08/21',reference='test-001',amount='۱۰۰۰',notes='')
        saved=self.s.save_record(self.a,'insurance_evidence',p,'mana')
        self.assertEqual(saved['payload']['amount'],'1000');self.assertEqual(self.s.record(r['id'])['payload']['status'],'draft')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',self.d,'mana',r['id'],r['version'])
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_evidence',{**p,'reference':''},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_evidence',p,'arka')
        file=self.s.add_file(self.a,saved['id'],'receipt.txt',b'example receipt')
        self.assertEqual(self.s.read_file(self.a,file['id'])[1],b'example receipt')
        uid=self.s.save_user(self.a,dict(username='worker',password='pass',fullname='همکار',memberships=[dict(company_id='mana',role='employee')]))['id']
        with self.assertRaises(DomainError):self.s.read_file(self.s.user(uid),file['id'])
    def test_changes_require_reason_and_record_it(self):
        r=self.s.save_record(self.a,'insurance_list',self.d,'mana')
        changed={**self.d,'notes':'اصلاح تستی'}
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',changed,'mana',r['id'],r['version'])
        self.s.save_record(self.a,'insurance_list',changed,'mana',r['id'],r['version'],reason='اصلاح کارکرد')
        self.assertTrue(any(x['reason']=='اصلاح کارکرد' for x in self.s.history(self.a,r['id'])))
    def test_internal_revision_preserves_original_and_rejects_stale_number(self):
        original=self.s.save_record(self.a,'insurance_list',self.d,'mana')
        copy={**original['payload'],'revision':'2','copy_from':original['id'],'notes':'نسخه اصلاحی'}
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',copy,'mana')
        new=self.s.save_record(self.a,'insurance_list',copy,'mana',reason='اصلاح')
        self.assertEqual(new['payload']['revision'],'2');self.assertEqual(self.s.record(original['id'])['payload']['revision'],'1')
        with self.assertRaises(DomainError):self.s.delete_record(self.a,original['id'],original['version'])
        self.assertEqual(self.s.save_record(self.a,'insurance_list',copy,'mana',reason='اصلاح مجدد')['payload']['revision'],'3')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_list',{**copy,'revision':'3','copy_from':''},'mana')
    def test_server_calculation_uses_approved_rule_and_snapshot(self):
        row={**self.d['rows'][0],'daily_seniority':'100','spouse_benefit':'500','insured_benefits':'2500','non_insured_benefits':'2000','unemployment_applies':True}
        draft=self.s.save_record(self.a,'insurance_list',{**self.d,'rows':[row]},'mana')
        rules=self.s.save_record(self.a,'insurance_rules',dict(title='آزمایشی',rules_version='r1',source='منبع آزمایشی',effective_from='1405/01/01',effective_to='1405/12/29',worker_rate='7',employer_rate='20',unemployment_rate='3',minimum_daily='100',maximum_daily='10000',approved=True),'mana')
        args=dict(title='محاسبه',insurance_list_id=draft['id'],rules_id=rules['id'])
        result=self.s.save_record(self.a,'insurance_calculation',args,'mana')
        self.assertEqual(result['payload']['result']['totals']['insurance_total'],'10800');self.assertEqual(result['payload']['list_version'],draft['version'])
        self.assertEqual(result['payload']['people_snapshot'][0]['employee']['employee_code'],'001')
        self.assertEqual(result['payload']['workshop_snapshot']['workshop_code'],'001')
        review=dict(title='بررسی داخلی',calculation_id=result['id'],notes='هشدارها بررسی شدند')
        approved=self.s.save_record(self.a,'insurance_review',review,'mana')
        self.assertEqual(approved['payload']['scope'],'internal_preliminary')
        for item in (approved,result,rules):
            with self.assertRaises(DomainError):self.s.delete_record(self.a,item['id'],item['version'])
        self.s.save_record(self.a,'insurance_employee',{**self.p['payload'],'job_title':'شغل جدید'},'mana',self.p['id'],self.p['version'])
        self.assertFalse(self.s.record(result['id'])['payload']['people_snapshot'][0]['profile'].get('job_title'))
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_review',review,'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_calculation',{**args,'result':{'totals':{}}},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_calculation',args,'arka')
        unapproved=self.s.save_record(self.a,'insurance_rules',{**rules['payload'],'rules_version':'r2','approved':False},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.a,'insurance_calculation',{**args,'rules_id':unapproved['id']},'mana')
    def test_payroll_estimate_link_and_snapshot_are_scoped(self):
        batch=self.s.save_record(self.a,'payroll_batch',{'title':'برآورد','period':'1405/08','slips':[{'name':'کارمند','code':'001','base':'3000','days':'30','period_days':'30'}]},'mana')
        confirmation=self.s.save_record(self.a,'payroll_confirmation',dict(title='تأیید حقوق',payroll_batch_id=batch['id'],reference='ref-test',notes=''),'mana')
        with self.assertRaises(DomainError):self.s.delete_record(self.a,batch['id'],batch['version'])
        row={**self.d['rows'][0],'daily_seniority':'0','spouse_benefit':'0','insured_benefits':'0','non_insured_benefits':'0','unemployment_applies':True,'payroll_batch_id':batch['id']}
        draft=self.s.save_record(self.a,'insurance_list',{**self.d,'rows':[row]},'mana')
        rules=self.s.save_record(self.a,'insurance_rules',dict(title='آزمایشی',rules_version='r1',source='آزمایشی',effective_from='1405/01/01',effective_to='1405/12/29',worker_rate='7',employer_rate='20',unemployment_rate='3',minimum_daily='100',maximum_daily='10000',approved=True),'mana')
        result=self.s.save_record(self.a,'insurance_calculation',dict(title='برآورد',insurance_list_id=draft['id'],rules_id=rules['id']),'mana')
        snapshot=result['payload']['people_snapshot'][0]['payroll_estimate'];self.assertEqual(snapshot['id'],batch['id']);self.assertFalse(snapshot['finalized']);self.assertEqual(snapshot['slip']['code'],'001')
        self.assertEqual(snapshot['internal_confirmation']['id'],confirmation['id'])
