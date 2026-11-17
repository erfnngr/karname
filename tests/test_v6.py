import os,sys,tempfile,unittest,base64,json,sqlite3,zipfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from org_store import Store,DomainError
from payroll import compute_payroll,progressive

class V6StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'company-server');self.admin=self.store.bootstrap('admin','1','مدیر اصلی','مدیر','اصلی');self.staff=self.make('staff','mana');self.other=self.make('other','arka');self.staff2=self.make('staff2','mana')
        self.scope='__shared_chat__';self.room=self.store.workspace_group_create(self.admin,self.scope,'گروه آزمون',[self.staff['id'],self.staff2['id']])['room']
    def tearDown(self):self.temp.cleanup()
    def make(self,name,co,role='employee'):
        value=self.store.save_user(self.admin,dict(username=name,password='ر',first_name='نام',last_name=name,memberships=[dict(company_id=co,role=role)]));return self.store.user(value['id'])
    def test_password_free_type_and_length(self):
        self.assertEqual(self.store.login('admin','1')['user']['id'],self.admin['id']);self.assertEqual(self.store.login('staff','ر')['user']['id'],self.staff['id'])
        with self.assertRaises(DomainError):self.store.bootstrap('bad','','empty')
        with self.assertRaises(DomainError):self.store.login('staff','x')
    def test_room_membership_scope_and_direct_access(self):
        self.assertEqual({r['room'] for r in self.store.chat_rooms(self.admin)},{self.room,'saved:'+self.admin['id']});self.assertEqual({r['room'] for r in self.store.chat_rooms(self.staff)},{self.room,'saved:'+self.staff['id']})
        with self.assertRaises(DomainError):self.store.chat_send(self.staff,self.scope,'saved:'+self.admin['id'],'خصوصی')
        with self.assertRaises(DomainError):self.store.chat_send(self.staff,self.scope,'managers','محرمانه')
        with self.assertRaises(DomainError):self.store.chat_send(self.staff,'arka','general','غیرمجاز')
        manager_room=self.store.workspace_group_create(self.admin,self.scope,'مدیران',[])['room'];m=self.store.chat_send(self.admin,self.scope,manager_room,'مدیران')
        with self.assertRaises(DomainError):self.store.chat_message(self.staff,m['id'])
        self.assertFalse(self.store.chat_updates(self.staff)['items'])
    def test_seen_like_delete_and_attachment_acl(self):
        raw=b'%PDF-1.4 fixture';m=self.store.chat_send(self.admin,self.scope,self.room,'فایل',attachments=[dict(name='sample.pdf',data=base64.b64encode(raw).decode())]);messages=self.store.chat_list(self.staff,self.scope,self.room)['items'];file=messages[0]['files'][0]
        with self.assertRaises(DomainError):self.store.chat_download(self.other,file['id'])
        self.assertEqual(base64.b64decode(self.store.chat_download(self.staff,file['id'])['data']),raw)
        self.store.chat_state(self.staff,self.scope,self.room,seq=m['seq']);self.store.chat_action(self.staff,m['id'],'like');view=self.store.chat_list(self.admin,self.scope,self.room)['items'][0];self.assertEqual(view['seen_by'][0]['id'],self.staff['id']);self.assertEqual(len(view['likes']),1)
        with self.assertRaises(DomainError):self.store.chat_action(self.staff,m['id'],'delete')
        self.store.chat_action(self.admin,m['id'],'delete');self.assertTrue(self.store.chat_list(self.staff,self.scope,self.room)['items'][0]['deleted'])
        with self.assertRaises(DomainError):self.store.chat_download(self.staff,file['id'])
    def test_poll_vote_changes_no_duplicate(self):
        m=self.store.chat_send(self.staff,self.scope,self.room,'کدام؟',kind='poll',payload={'options':['اول','دوم']});self.store.chat_action(self.staff,m['id'],'vote',0);self.store.chat_action(self.staff,m['id'],'vote',1);v=self.store.chat_list(self.staff,self.scope,self.room)['items'][0];self.assertEqual(v['votes'],[0,1]);self.assertEqual(v['my_vote'],1)
        with self.assertRaises(DomainError):self.store.chat_action(self.staff,m['id'],'vote',5)
        with self.assertRaises(DomainError):self.store.chat_send(self.staff,self.scope,self.room,'بد',kind='poll',payload={'options':['یک','یک']})
    def test_unread_notifications_mute_and_meeting(self):
        m=self.store.chat_send(self.admin,self.scope,self.room,'پیام');self.assertEqual(len(self.store.chat_updates(self.staff)['items']),1);self.store.chat_state(self.staff,self.scope,self.room,muted=True);self.assertFalse(self.store.chat_updates(self.staff)['items']);self.store.chat_state(self.staff,self.scope,self.room,muted=False);self.store.chat_state(self.staff,self.scope,self.room,seq=m['seq']);self.assertFalse(self.store.chat_updates(self.staff)['items'])
        meeting=self.store.chat_send(self.admin,self.scope,self.room,'جلسه',kind='meeting',payload={'at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()});self.assertEqual(len(self.store.chat_updates(self.staff)['meetings']),1);self.store.chat_action(self.staff,meeting['id'],'meeting_notified');self.assertFalse(self.store.chat_updates(self.staff)['meetings'])
        with self.assertRaises(DomainError):self.store.chat_send(self.admin,self.scope,self.room,'جلسه',kind='meeting',payload={'at':'2026-10-27'})
    def test_cursor_batch_does_not_skip_notifications(self):
        for i in range(205):self.store.chat_send(self.admin,self.scope,self.room,'پیام '+str(i))
        first=self.store.chat_updates(self.staff);second=self.store.chat_updates(self.staff,first['cursor']);self.assertEqual(len(first['items'])+len(second['items']),205);self.assertEqual(len({x['id'] for x in first['items']+second['items']}),205)
    def test_preferences_profile_and_company_admin(self):
        p=self.store.save_profile(self.staff,dict(color='#FF0000',preferences={'visible_modules':['chat'],'news_terms':'#مالیات'}));self.assertEqual(self.store.user(self.staff['id'])['profile'],p);self.assertFalse(self.store.own_profile(self.other)['preferences'])
        with self.assertRaises(DomainError):self.store.save_profile(self.staff,dict(avatar=base64.b64encode(b'not an image').decode()))
        co=self.store.save_company(self.admin,dict(name='شرکت تازه',phone='021',address='تهران',extra='نمونه'));self.assertEqual(co['phone'],'021')
        with self.assertRaises(DomainError):self.store.save_company(self.staff,dict(name='مجاز نیست'))
        manager=self.make('manager','mana','company_manager');self.store.save_company(manager,dict(id='mana',name='مانا',phone='100'))
        with self.assertRaises(DomainError):self.store.save_company(manager,dict(id='arka',name='آرکا'))
    def test_full_backup_restores_chat_profiles_files_and_accounts(self):
        from backup_bundle import create_bundle,verify_bundle
        from server_restore import inspect_server_backup,restore_closed_server
        m=self.store.chat_send(self.admin,self.scope,self.room,'پشتیبان',attachments=[dict(name='test.xlsx',data=base64.b64encode(b'fixture').decode())]);self.store.save_profile(self.staff,dict(color='#ABCDEF'));snapshot=self.root/'snapshot.sqlite';self.store.backup_database(snapshot);extras={'server/company.sqlite':snapshot.read_bytes()};extras.update({'server/files/'+p.name:p.read_bytes() for p in self.store.files.glob('*.bin')});target=self.root/'test.karname';data={'events':[],'settings':{}};create_bundle(target,data,extras);self.assertEqual(verify_bundle(target)[2]['kind'],'server');inspect_server_backup(target);self.store.chat_send(self.admin,self.scope,self.room,'بعد از بکاپ');_,archive=restore_closed_server(self.root,target);self.assertTrue(archive.exists());restored=Store(self.root/'company-server');self.assertEqual(len(restored.chat_list(restored.user(self.admin['id']),self.scope,self.room)['items']),1);self.assertEqual(restored.own_profile(self.staff)['color'],'#ABCDEF');self.assertTrue(restored.login('admin','1'))
    def test_backup_rejects_missing_chat_file(self):
        from backup_bundle import create_bundle
        from server_restore import inspect_server_backup
        self.store.chat_send(self.admin,self.scope,self.room,'پیوست',attachments=[dict(name='a.pdf',data=base64.b64encode(b'fixture').decode())]);db=self.root/'copy.sqlite';self.store.backup_database(db);p=self.root/'bad.karname';create_bundle(p,{'events':[],'settings':{}},{'server/company.sqlite':db.read_bytes()})
        with self.assertRaises(ValueError):inspect_server_backup(p)

class V6PayrollTests(unittest.TestCase):
    def p(self,**kw):
        from payroll_ui import DEFAULTS
        return dict(DEFAULTS,**kw)
    def test_payroll_reconciles_and_no_float_math(self):
        r=compute_payroll(self.p(base='220000000',overtime_hours='10',housing='10000000',tax_amount='1000000',advance='2000000'));self.assertEqual(r['overtime'],Decimal('14000000'));self.assertEqual(r['gross'],Decimal('244000000'));self.assertEqual(r['net'],r['gross']-r['insurance']-r['tax']-r['deductions']);self.assertEqual(r['employer_cost'],r['gross']+r['company_insurance'])
    def test_partial_days_and_tax_brackets(self):
        self.assertEqual(compute_payroll(self.p(base='3000',days='15',worker_rate='0',employer_rate='0'))['net'],Decimal('1500'));brackets=[{'cap':'100','rate':'0'},{'cap':'200','rate':'10'},{'cap':'','rate':'20'}];self.assertEqual(progressive(Decimal('250'),brackets),Decimal('20'));self.assertEqual(progressive(Decimal('100'),brackets),0)
        with self.assertRaises(ValueError):compute_payroll(self.p(period_days='0'))
        with self.assertRaises(ValueError):compute_payroll(self.p(days='32'))
        with self.assertRaises(ValueError):compute_payroll(self.p(tax_mode='progressive'))
    def test_flat_tax_exemption_and_explicit_basis(self):
        r=compute_payroll(self.p(base='1000',tax_mode='flat',tax_rate='10',tax_exemption='100',tax_override=True,tax_basis='500',tax_deduction='50',insurance_override=True,insurance_basis='200',worker_rate='7'));self.assertEqual(r['tax'],35);self.assertEqual(r['insurance'],14)

class V6HttpTests(unittest.TestCase):
    def test_two_clients_rooms_csrf_and_chat_transport(self):
        from org_http import RunningServer
        from org_client import Client
        import requests
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder);a=store.bootstrap('admin','1','مدیر');staff_id=store.save_user(a,dict(username='staff',password='س',fullname='کارمند',memberships=[dict(company_id='mana',role='employee')]))['id'];server=RunningServer(folder,'127.0.0.1',0)
            try:
                scope='__shared_chat__';room=store.workspace_group_create(a,scope,'گروه آزمون',[staff_id])['room'];private=store.workspace_group_create(a,scope,'خصوصی',[])['room']
                url='http://127.0.0.1:'+str(server.port);admin=Client(url);admin.login('admin','1');staff=Client(url);staff.login('staff','س');m=admin.request('chat/messages',dict(company=scope,room=room,text='سلام 👋'));self.assertEqual(staff.request('chat/messages',company=scope,room=room)['items'][0]['text'],'سلام 👋')
                with self.assertRaises(DomainError):staff.request('chat/messages',company=scope,room=private)
                self.assertEqual(requests.post(url+'/api/chat/messages',json=dict(company=scope,room=room,text='bad'),headers={'Authorization':'Bearer '+staff.token}).status_code,403)
                self.assertEqual(requests.get(url+'/chat').status_code,200);self.assertEqual(requests.get(url+'/chat.js').status_code,200)
            finally:server.close()

if __name__=='__main__':unittest.main(verbosity=2)
