import os,sys,json,tempfile,unittest,copy,zipfile,concurrent.futures,base64
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from org_store import Store,DomainError
from org_schema import SCHEMAS

class CompanyTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.store=Store(self.folder.name);self.admin=self.store.bootstrap('admin','Test-pass-12345','مدیر آزمایشی')
        self.manager=self.person('manager','mana','company_manager');self.employee=self.person('employee','mana','employee');self.other=self.person('other','arka','company_manager');self.auditor=self.person('auditor','mana','auditor')
    def tearDown(self):self.folder.cleanup()
    def person(self,name,company,role):
        value=self.store.save_user(self.admin,dict(username=name,password='Test-pass-12345',fullname=name,memberships=[dict(company_id=company,role=role)]));return self.store.user(value['id'])
    def task(self,company='mana',actor=None,**kw):
        p=dict(title='کار آزمایشی',due_date='1405/08/10',status='draft',require_approval=True,checklist=[],dependencies=[]);p.update(kw);return self.store.save_record(actor or self.manager,'task',p,company)
    def test_cross_company_scope_private_and_auditor(self):
        a=self.task();self.task('arka',self.other)
        self.assertEqual(self.store.list_records(self.employee)['total'],0)
        self.assertEqual(len(self.store.all_visible(self.manager,'task')),1)
        with self.assertRaises(DomainError):self.store.save_record(self.other,'task',a['payload'],'arka',a['id'],a['version'])
        with self.assertRaises(DomainError):self.task(actor=self.auditor)
        private=self.store.save_record(self.employee,'task',dict(title='خصوصی',due_date='1405/08/10'),None,private=True)
        self.assertFalse(self.store.readable(self.admin,private));self.assertTrue(self.store.readable(self.employee,private))
    def test_assigned_employee_cannot_disable_approval_or_move_company(self):
        task=self.task(assignee_id=self.employee['id'],reviewer_id=self.manager['id']);p=copy.deepcopy(task['payload']);p.update(status='completed',require_approval=False)
        with self.assertRaises(DomainError):self.store.save_record(self.employee,'task',p,'arka',task['id'],task['version'])
        p=copy.deepcopy(task['payload']);p['status']='review';new=self.store.save_record(self.employee,'task',p,'arka',task['id'],task['version']);self.assertEqual(new['company_id'],'mana')
        p['status']='completed'
        with self.assertRaises(DomainError):self.store.save_record(self.employee,'task',p,'mana',new['id'],new['version'])
        final=self.store.save_record(self.manager,'task',p,'mana',new['id'],new['version']);self.assertEqual(final['payload']['status'],'completed')
    def test_self_created_employee_task_still_requires_approval(self):
        t=self.task(actor=self.employee,require_approval=False);self.assertTrue(t['payload']['require_approval']);p=dict(t['payload'],require_approval=False,status='completed')
        with self.assertRaises(DomainError):self.store.save_record(self.employee,'task',p,'mana',t['id'],t['version'])
    def test_optimistic_lock_under_concurrent_edits(self):
        t=self.task()
        def write(i):
            try:self.store.save_record(self.manager,'task',dict(t['payload'],title=str(i)),'mana',t['id'],t['version']);return 'ok'
            except DomainError as exc:return exc.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,[1,2]))
        self.assertCountEqual(results,['ok',409]);self.assertEqual(self.store.record(t['id'])['version'],2)
    def test_dependencies_cycles_checklist_and_evidence(self):
        first=self.task();second=self.task(dependencies=[first['id']])
        with self.assertRaises(DomainError):self.store.save_record(self.manager,'task',dict(first['payload'],dependencies=[second['id']]),'mana',first['id'],first['version'])
        with self.assertRaises(DomainError):self.store.save_record(self.manager,'task',dict(second['payload'],status='in_progress'),'mana',second['id'],second['version'])
        evidence=self.task(require_evidence=True)
        with self.assertRaises(DomainError):self.store.save_record(self.manager,'task',dict(evidence['payload'],status='completed'),'mana',evidence['id'],evidence['version'])
        self.store.add_file(self.manager,evidence['id'],'رسید.txt',b'confirmed')
        self.assertEqual(self.store.save_record(self.manager,'task',dict(evidence['payload'],status='completed'),'mana',evidence['id'],evidence['version'])['payload']['status'],'completed')
    def test_proposal_is_atomic_on_stale_or_other_company_task(self):
        a=self.task();b=self.task(due_date='1405/08/11');p=dict(title='تمدید',source='https://tax.gov.ir/',old_date='1405/08/10',new_date='1405/08/20',task_ids=a['id']+','+b['id'],reason='اطلاعیه بررسی‌شده',status='approved')
        with self.assertRaises(DomainError):self.store.save_record(self.manager,'proposal',p,'mana')
        self.assertEqual(self.store.record(a['id'])['payload']['due_date'],'1405/08/10');self.assertFalse(self.store.all_visible(self.manager,'proposal'))
        p['task_ids']=a['id'];self.store.save_record(self.manager,'proposal',p,'mana');self.assertEqual(self.store.record(a['id'])['payload']['due_date'],'1405/08/20')
    def test_rate_and_calculation_snapshots_immutable(self):
        rate=self.store.save_record(self.manager,'rate',dict(title='نسخه نرخ',effective_from='1405/01/01',fixed='10',monthly='2',source='منبع پرونده'),'mana')
        calc=self.store.save_record(self.manager,'calculation',dict(title='محاسبه',amount='100000000',rate_id=rate['id'],months='3'),'mana');self.assertEqual(calc['payload']['result']['penalty'],'16000000');self.assertEqual(calc['payload']['rate_snapshot']['fixed'],'10')
        with self.assertRaises(DomainError):self.store.save_record(self.manager,'rate',dict(rate['payload'],fixed='20'),'mana',rate['id'],rate['version'])
        with self.assertRaises(DomainError):self.store.save_record(self.manager,'calculation',calc['payload'],'mana',calc['id'],calc['version'])
    def test_notice_schedule_expiry_receipts_and_revocation(self):
        now=datetime.now(timezone.utc);future=self.store.publish(self.manager,dict(companies=['mana'],title='فردا',body='خبر',publish_at=(now+timedelta(days=1)).isoformat()));self.assertFalse(self.store.readable(self.employee,future));self.assertFalse(self.store.inbox(self.employee))
        notice=self.store.publish(self.manager,dict(companies=['mana'],title='اکنون',body='اطلاع',require_ack=True));self.assertEqual(len(self.store.inbox(self.employee)),1);self.store.acknowledge(self.employee,notice['id'],'ack');r=next(r for r in self.store.receipt_report(self.manager,notice['id']) if r['user_id']==self.employee['id']);self.assertTrue(r['delivered']);self.assertTrue(r['opened']);self.assertTrue(r['acknowledged']);self.assertFalse(self.store.readable(self.other,notice))
        self.store.save_user(self.admin,dict(id=self.employee['id'],username='employee',fullname='employee',memberships=[]));revoked=self.store.user(self.employee['id']);self.assertFalse(self.store.readable(revoked,notice))
    def test_session_password_lockout_and_revoke(self):
        token=self.store.login('employee','Test-pass-12345')['token'];self.assertEqual(self.store.authenticate(token)['id'],self.employee['id']);self.store.logout(token)
        with self.assertRaises(DomainError):self.store.authenticate(token)
        for _ in range(8):
            with self.assertRaises(DomainError):self.store.login('employee','wrong')
        with self.assertRaises(DomainError) as ctx:self.store.login('employee','Test-pass-12345')
        self.assertEqual(ctx.exception.status,429)
    def test_only_managers_manage_accounts_and_english_names(self):
        payload=dict(username='sara.ahmadi',first_name='سارا',last_name='احمدی',password='Personal-Test-12345',memberships=[dict(company_id='mana',role='employee')])
        with self.assertRaises(DomainError):self.store.save_user(self.employee,payload)
        with self.assertRaises(DomainError):self.store.save_user(self.auditor,payload)
        new=self.store.save_user(self.manager,payload);person=self.store.user(new['id']);self.assertEqual(person['first_name'],'سارا');self.assertEqual(person['last_name'],'احمدی');self.assertEqual(person['fullname'],'سارا احمدی');self.assertNotIn('password',person)
        with self.assertRaises(DomainError):self.store.save_user(self.manager,dict(payload,username='other.staff',memberships=[dict(company_id='arka',role='employee')]))
        with self.assertRaises(DomainError):self.store.save_user(self.manager,dict(payload,username='global.admin',global_role='group_admin'))
        with self.assertRaises(DomainError):Store.clean_username('کارمند')
        with self.assertRaises(DomainError):Store.clean_username('sara ahmadi')
    def test_manager_password_reset_revokes_old_sessions(self):
        token=self.store.login('employee','Test-pass-12345')['token'];self.store.save_user(self.manager,dict(id=self.employee['id'],username='employee',first_name='کارمند',last_name='نمونه',password='New-Test-Pass-12345',memberships=[dict(company_id='mana',role='employee')]))
        with self.assertRaises(DomainError):self.store.authenticate(token)
        with self.assertRaises(DomainError):self.store.login('employee','Test-pass-12345')
        self.assertEqual(self.store.login('employee','New-Test-Pass-12345')['user']['fullname'],'کارمند نمونه')
    def test_attachments_scope_versioning_path_and_extracted_search(self):
        task=self.task();a=self.store.add_file(self.manager,task['id'],'../../document.txt','آیین‌نامه پرداخت شرکت'.encode());b=self.store.add_file(self.manager,task['id'],'document.txt',b'second');self.assertEqual(a['name'],'document.txt');self.assertEqual(b['version'],2)
        with self.assertRaises(DomainError):self.store.read_file(self.other,a['id'])
        self.store.extract_document(self.manager,a['id']);self.assertEqual(self.store.knowledge_search(self.manager,'پرداخت')[0]['id'],task['id']);self.assertFalse(self.store.knowledge_search(self.other,'پرداخت'))
    def test_hr_import_dedup_and_payroll_only_approved(self):
        self.store.save_record(self.manager,'employee',dict(title='کارمند',employee_code='001',user_id=self.employee['id'],hourly_rate='600000',daily_minutes='480'),'mana')
        row=dict(employee_code='001',date='1405/08/01',check_in='08:00',check_out='16:00',minutes='480');self.assertEqual(self.store.import_attendance(self.manager,'mana',[row],'1405/08')['added'],1);self.assertEqual(self.store.import_attendance(self.manager,'mana',[row],'1405/08')['duplicates'],1)
        self.assertEqual(self.store.payroll(self.manager,'mana','1405/08')[0]['دقایق تأییدشده'],'0');r=self.store.all_visible(self.manager,'attendance')[0];self.store.save_record(self.manager,'attendance',dict(r['payload'],status='approved'),'mana',r['id'],r['version']);self.assertEqual(self.store.payroll(self.manager,'mana','1405/08')[0]['برآورد دستمزد ساعتی ریال'],'4800000')
        with self.assertRaises(DomainError):self.store.import_attendance(self.employee,'mana',[row],'1405/08')
    def test_automation_opt_in_once_a_day(self):
        self.task(due_date='1400/01/01',assignee_id=self.employee['id']);rule=self.store.save_record(self.manager,'automation',dict(title='پیگیری',trigger='overdue',delay_days='0',message='کار را بررسی کنید',enabled=False),'mana');self.assertEqual(self.store.run_automations(),0);self.store.save_record(self.manager,'automation',dict(rule['payload'],enabled=True),'mana',rule['id'],rule['version']);self.assertEqual(self.store.run_automations(),1);self.assertEqual(self.store.run_automations(),0);self.assertEqual(len(self.store.inbox(self.employee)),1)
    def test_export_contains_only_visible_data_and_no_credentials(self):
        self.task(assignee_id=self.employee['id']);self.task('arka',self.other);value=self.store.export_scope(self.employee);encoded=json.dumps(value);self.assertEqual(len(value['records']),1);self.assertNotIn('password',encoded);self.assertNotIn('token',encoded)

class FileTests(unittest.TestCase):
    def test_server_restore_preserves_current_snapshot_and_revokes_sessions(self):
        from server_restore import restore_closed_server
        from backup_bundle import create_bundle
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=Store(root/'company-server');admin=store.bootstrap('admin','Account-Test-12345','مدیر');store.login('admin','Account-Test-12345');a=store.save_record(admin,'task',dict(title='نسخه پشتیبان',due_date='1405/08/01'),'mana');attachment=store.add_file(admin,a['id'],'رسید.txt',b'original receipt');snapshot=root/'snapshot.sqlite';store.backup_database(snapshot);target=root/'backup.zip';create_bundle(target,dict(events=[],settings={}),{'server/company.sqlite':snapshot.read_bytes(),'server/files/'+attachment['id']+'.bin':(store.files/(attachment['id']+'.bin')).read_bytes()});store.save_record(admin,'task',dict(title='نسخه جدیدتر',due_date='1405/08/02'),'mana');counts,archive=restore_closed_server(root,target);self.assertTrue(archive.is_dir());restored=Store(root/'company-server');self.assertEqual(len(restored.all_visible(restored.user(admin['id']),'task')),1);self.assertEqual(len(Store(archive).all_visible(admin,'task')),2)
            with restored.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],0)
    def test_offline_snapshot_encrypted_and_password_required(self):
        from offline_cache import OfflineCache
        with tempfile.TemporaryDirectory() as folder:
            cache=OfflineCache(folder,'https://company.example','employee','Private-Pass-12345');cache.save({'records':[{'title':'مبلغ محرمانه'}]});self.assertNotIn('مبلغ'.encode(),cache.path.read_bytes());self.assertEqual(cache.load()['records'][0]['title'],'مبلغ محرمانه')
            with self.assertRaises(ValueError):OfflineCache(folder,'https://company.example','employee','wrong').load()
            self.assertFalse(OfflineCache(folder,'https://other.example','employee','Private-Pass-12345').path.exists())
    def test_month_mapping_dates_overnight_dedup_and_invalid(self):
        from attendance_import import preview
        rows=[['001','2026-10-23','22:00','06:00'],['001','1405/08/01','22:00','06:00'],['002','1405/07/31','08:00','16:00'],['003','1405/08/02','29:00','16:00']];result=preview(['id','date','in','out'],rows,dict(employee_code=0,date=1,check_in=2,check_out=3),'1405/08');self.assertEqual(result[0]['payload']['minutes'],'480');self.assertEqual([r['valid'] for r in result],[True,False,False,False])
    def test_backup_dirty_excludes_automatic_state_and_failed_verification(self):
        from backup_bundle import BackupState,create_bundle,verify_bundle
        with tempfile.TemporaryDirectory() as folder:
            data=dict(events=[dict(id='a',created_from_excel=True,title='موعد')],settings={});state=BackupState(folder,data);self.assertFalse(state.dirty(data));data['events'][0]['last_alerts']={'today':True};data['official_news']={'items':[1]};self.assertFalse(state.dirty(data));data['events'][0]['title']='تغییر';self.assertTrue(state.dirty(data));path=Path(folder)/'backup.zip';create_bundle(path,data);self.assertEqual(verify_bundle(path)[0],data);state.mark_saved(data);self.assertFalse(state.dirty(data))
            with zipfile.ZipFile(path,'a') as z:z.writestr('unexpected.txt','unexpected')
            with self.assertRaises(ValueError):verify_bundle(path)
    def test_backup_rejects_zip_traversal(self):
        from backup_bundle import verify_bundle
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'evil.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../escape.txt','no')
            with self.assertRaises(ValueError):verify_bundle(p)
            self.assertFalse((Path(folder).parent/'escape.txt').exists())
    def test_quotes_300_authors_sources_daily_rotation_and_tehran_midnight(self):
        from quotes import collection,daily_quote,TEHRAN
        quotes=collection();self.assertEqual(len(quotes),300);self.assertEqual(len({x['id'] for x in quotes}),300);self.assertEqual(len({x['author'] for x in quotes}),4);self.assertEqual(len({daily_quote(date(2026,1,1)+timedelta(days=n))['id'] for n in range(300)}),300)
        before=datetime(2026,12,31,20,29,tzinfo=timezone.utc);after=before+timedelta(minutes=1);self.assertNotEqual(daily_quote(before)['id'],daily_quote(after)['id']);self.assertEqual(daily_quote(after)['id'],daily_quote(date(2027,1,1))['id'])

class HttpTests(unittest.TestCase):
    def test_api_scope_csrf_tls_and_cookie(self):
        import requests
        from org_http import RunningServer,make_certificate
        from org_client import Client
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder);store.bootstrap('admin','Test-pass-12345','مدیر');cert,key,fp=make_certificate(folder,['127.0.0.1']);host=RunningServer(folder,'127.0.0.1',0,True,cert,key)
            try:
                url='https://127.0.0.1:'+str(host.port);client=Client(url,str(cert));client.login('admin','Test-pass-12345');self.assertEqual({c['id'] for c in client.request('companies')},{'mana','airia','arka'});self.assertEqual(len(fp),64);self.assertTrue(client.session.cookies.get('karname'));r=client.session.post(url+'/api/logout',json={});self.assertEqual(r.status_code,403);self.assertTrue(client.request('me'));r=client.session.get(url+'/');self.assertEqual(r.status_code,200);self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy']);client.logout()
                with self.assertRaises(DomainError):client.request('me')
            finally:host.close()
        with self.assertRaises(ValueError):Client('http://192.168.1.5:8843')

if __name__=='__main__':unittest.main(verbosity=2)
