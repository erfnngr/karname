import os,sys,tempfile,unittest,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from org_store import Store,DomainError
from occasions import find_occasions

class DeskTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'company-server');self.admin=self.store.bootstrap('admin','1','مدیر اصلی');self.staff=self.make('staff','mana');self.other=self.make('other','mana');self.manager=self.make('manager','mana','company_manager');self.foreign=self.make('foreign','arka','company_manager')
    def tearDown(self):self.temp.cleanup()
    def make(self,name,company,role='employee'):
        id=self.store.save_user(self.admin,dict(username=name,password='1',fullname=name,memberships=[dict(company_id=company,role=role)]))['id'];return self.store.user(id)
    def leave(self,actor=None,**changes):
        p=dict(start_date='1405/08/10',end_date='1405/08/11',leave_type='استحقاقی',notes='درخواست نمونه');p.update(changes);return self.store.desk_leave_save(actor or self.staff,'mana',p)['item']
    def note(self,actor=None,**changes):
        p=dict(title='یادداشت خصوصی',body='متن فقط برای خودم',date_jalali='1405/08/10',calendar_enabled=True,lead_days=[5,1,0]);p.update(changes);return self.store.desk_note_save(actor or self.staff,p)
    def test_leave_ready_without_hr_profile_identity_status_bound(self):
        row=self.leave(requester_id=self.other['id'],status='approved');self.assertEqual(row['requester_id'],self.staff['id']);self.assertEqual(row['status'],'pending');self.assertEqual(row['payload']['requester_name'],'staff');self.assertEqual(len(self.store.desk_snapshot(self.staff)['leaves']),1);self.assertFalse(self.store.desk_snapshot(self.other)['leaves']);self.assertFalse(self.store.desk_snapshot(self.other)['incoming'])
    def test_only_company_managers_notified_and_review(self):
        row=self.leave();self.assertTrue(any(n['leave_id']==row['id'] for n in self.store.desk_snapshot(self.manager)['notifications']));self.assertFalse(self.store.desk_snapshot(self.foreign)['notifications']);self.assertFalse(self.store.desk_snapshot(self.other)['notifications'])
        with self.assertRaises(DomainError):self.store.desk_leave_review(self.other,row['id'],1,'approved')
        with self.assertRaises(DomainError):self.store.desk_leave_review(self.foreign,row['id'],1,'approved')
        decision=self.store.desk_leave_review(self.manager,row['id'],1,'approved','تأیید شد');self.assertEqual(decision['status'],'approved');self.assertEqual(decision['reviewer_id'],self.manager['id']);self.assertTrue(self.store.desk_snapshot(self.staff)['notifications']);self.assertFalse(self.store.desk_snapshot(self.manager)['notifications'])
    def test_cannot_self_approve_or_change_reviewed_leave(self):
        row=self.leave(self.manager)
        with self.assertRaises(DomainError):self.store.desk_leave_review(self.manager,row['id'],1,'approved')
        self.store.desk_leave_review(self.admin,row['id'],1,'rejected','تاریخ اصلاح شود')
        with self.assertRaises(DomainError):self.store.desk_leave_save(self.manager,'mana',row['payload'],row['id'],2)
        with self.assertRaises(DomainError):self.store.desk_leave_review(self.admin,row['id'],2,'approved')
    def test_leave_edit_stale_review_cancel_and_time_validation(self):
        row=self.leave();new=self.store.desk_leave_save(self.staff,'mana',dict(row['payload'],end_date='1405/08/12'),row['id'],1)['item'];self.assertEqual(new['version'],2)
        with self.assertRaises(DomainError) as e:self.store.desk_leave_review(self.manager,row['id'],1,'approved')
        self.assertEqual(e.exception.status,409);self.store.desk_leave_cancel(self.staff,row['id'],2);self.assertEqual(self.store.desk_leave(self.staff,row['id'])['status'],'cancelled');self.assertFalse(self.store.desk_snapshot(self.manager)['notifications'])
        with self.assertRaises(DomainError):self.leave(start_date='1405/08/12',end_date='1405/08/11')
        with self.assertRaises(DomainError):self.leave(leave_type='ساعتی',start_time='09:00',end_time='10:00')
        hourly=self.leave(leave_type='ساعتی',end_date='1405/08/10',start_time='09:30',end_time='11:00');self.assertEqual(hourly['payload']['hours'],'1.50')
    def test_private_notes_direct_id_update_delete_and_export_acl(self):
        n=self.note();snapshot=self.store.desk_snapshot(self.staff);self.assertEqual(len(snapshot['notes']),1);self.assertFalse(self.store.desk_snapshot(self.admin)['notes']);self.assertFalse(self.store.desk_snapshot(self.other)['notes'])
        with self.assertRaises(DomainError):self.store.desk_note_save(self.admin,dict(title='سرقت',body=''),n['id'],1)
        with self.assertRaises(DomainError):self.store.desk_note_delete(self.other,n['id'],1)
        self.assertEqual(len(self.store.export_scope(self.staff)['personal_desk']['notes']),1);self.assertFalse(self.store.export_scope(self.staff,'mana')['personal_desk']['notes']);self.assertFalse(self.store.export_scope(self.admin)['personal_desk']['notes'])
        self.store.desk_note_delete(self.staff,n['id'],1);self.assertFalse(self.store.desk_snapshot(self.staff)['notes'])
    def test_note_dates_revision_and_atomic_restore(self):
        a=self.note();before=self.store.desk_snapshot(self.staff)['notes'][0]
        with self.assertRaises(DomainError):self.note(date_jalali='')
        self.store.desk_note_save(self.staff,dict(before,title='تازه'),a['id'],1)
        with self.assertRaises(DomainError):self.store.desk_note_save(self.staff,before,a['id'],1)
        b=self.note(self.other);foreign=self.store.desk_snapshot(self.other)['notes'][0]
        with self.assertRaises(DomainError):self.store.desk_restore_notes(self.staff,[before,foreign])
        self.assertEqual(self.store.desk_snapshot(self.staff)['notes'][0]['title'],'تازه');self.store.desk_restore_notes(self.staff,[before]);self.assertEqual(self.store.desk_snapshot(self.staff)['notes'][0]['title'],'یادداشت خصوصی')
    def test_notification_receipt_requires_recipient_and_current_scope(self):
        row=self.leave();notice=self.store.desk_snapshot(self.manager)['notifications'][0]
        with self.assertRaises(DomainError):self.store.desk_notification(self.other,notice['id'],'shown')
        self.store.desk_notification(self.manager,notice['id'],'shown');self.assertTrue(self.store.desk_snapshot(self.manager)['notifications'][0]['shown']);self.store.desk_notification(self.manager,notice['id'],'opened');self.assertFalse(self.store.desk_snapshot(self.manager)['notifications'])
        self.store.save_user(self.admin,dict(id=self.manager['id'],username='manager',fullname='manager',memberships=[dict(company_id='arka',role='company_manager')]))
        with self.assertRaises(DomainError):self.store.desk_leave(self.store.user(self.manager['id']),row['id'])
    def test_full_server_backup_recovers_notes_and_leave(self):
        from backup_bundle import create_bundle
        from server_restore import restore_closed_server
        self.note();self.leave();db=self.root/'copy.sqlite';self.store.backup_database(db);backup=self.root/'data.karname';create_bundle(backup,{'events':[],'settings':{}},{'server/company.sqlite':db.read_bytes()});self.note(title='پس از پشتیبان');restore_closed_server(self.root,backup);store=Store(self.root/'company-server');snapshot=store.desk_snapshot(store.user(self.staff['id']));self.assertEqual(len(snapshot['notes']),1);self.assertEqual(len(snapshot['leaves']),1)

class OccasionSearchTests(unittest.TestCase):
    def test_search_all_months_and_persian_variant(self):
        y=1405;items=find_occasions(y,1,'یلدا');self.assertTrue(items);self.assertTrue(all('یلدا' in x['title'] for x in items));self.assertTrue(any(x['date'].month==12 for x in items));self.assertTrue(find_occasions(y,1,'اسفند'));self.assertEqual(find_occasions(y,1,'روز جهانی كتاب'),find_occasions(y,1,'روز جهانی کتاب'))

class DeskHttpTests(unittest.TestCase):
    def test_two_accounts_requests_and_private_notes_over_http(self):
        from org_http import RunningServer
        from org_client import Client
        import requests
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder);admin=store.bootstrap('admin','1','مدیر');store.save_user(admin,dict(username='staff',password='1',fullname='کارمند',memberships=[dict(company_id='mana',role='employee')]));server=RunningServer(folder,'127.0.0.1',0)
            try:
                origin='http://127.0.0.1:'+str(server.port);a=Client(origin);a.login('admin','1');b=Client(origin);b.login('staff','1');r=b.request('desk/leave',dict(company='mana',payload=dict(start_date='1405/08/10',end_date='1405/08/10',leave_type='استحقاقی')))['item'];self.assertEqual(len(a.request('desk')['incoming']),1)
                with self.assertRaises(DomainError):b.request('desk/review',dict(id=r['id'],version=1,status='approved'))
                a.request('desk/review',dict(id=r['id'],version=1,status='approved'));self.assertEqual(b.request('desk')['leaves'][0]['status'],'approved');n=b.request('desk/note',dict(payload=dict(title='خصوصی',body='فقط من',calendar_enabled=False)))
                self.assertFalse(a.request('desk')['notes']);self.assertEqual(b.request('desk')['notes'][0]['body'],'فقط من')
                with self.assertRaises(DomainError):a.request('desk/delete-note',dict(id=n['id'],version=1))
                self.assertEqual(requests.get(origin+'/desk').status_code,200)
            finally:server.close()

if __name__=='__main__':unittest.main(verbosity=2)
