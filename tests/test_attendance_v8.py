import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from org_store import Store,DomainError
from attendance_import import preview,read_table,guess_mapping
from attendance_reporting import default_policy

class AttendanceReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.s=Store(self.root/'server');self.admin=self.s.bootstrap('admin','1','مدیر کل');self.people={}
        for name,co,role in [('staff','mana','employee'),('other','mana','employee'),('manager','mana','company_manager'),('foreign','arka','company_manager')]:
            id=self.s.save_user(self.admin,dict(username=name,password='1',fullname=name,memberships=[dict(company_id=co,role=role)]))['id'];self.people[name]=self.s.user(id)
        self.s.save_record(self.admin,'employee',dict(title='کارمند نمونه',employee_code='001',user_id=self.people['staff']['id']),'mana');self.s.save_record(self.admin,'employee',dict(title='همکار دیگر',employee_code='002',user_id=self.people['other']['id']),'mana')
    def tearDown(self):self.temp.cleanup()
    def insert(self,*rows):return self.s.import_attendance(self.people['manager'],'mana',list(rows),'1405/08')
    def report(self,actor=None,code='001'):return self.s.attendance_report(actor or self.people['staff'],'mana','1405/08',code)
    def row(self,code,day,start,end,minutes=''):
        return dict(employee_code=code,date=day,check_in=start,check_out=end,minutes=minutes)
    def test_manager_sees_company_people_staff_only_self_and_other_company_denied(self):
        self.assertEqual({p['employee_code'] for p in self.s.attendance_people(self.people['manager'],'mana')['people']},{'001','002'});self.assertEqual([p['employee_code'] for p in self.s.attendance_people(self.people['staff'],'mana')['people']],['001'])
        with self.assertRaises(DomainError):self.report(self.people['staff'],'002')
        with self.assertRaises(DomainError):self.s.attendance_people(self.people['foreign'],'mana')
        with self.assertRaises(DomainError):self.s.attendance_report(self.people['foreign'],'mana','1405/08','001')
        with self.assertRaises(DomainError):self.s.import_attendance(self.people['staff'],'mana',[self.row('001','1405/08/02','09:00','10:00')],'1405/08')
    def test_import_sorted_intervals_dedup_overlap_and_approved_overtime(self):
        records=[self.row('001','1405/08/02','13:00','19:00'),self.row('001','1405/08/02','09:00','12:00'),self.row('001','1405/08/02','11:00','14:00')];self.assertEqual(self.insert(*records)['added'],3);self.assertEqual(self.insert(*records)['duplicates'],3)
        report=self.report();d=next(x for x in report['days'] if x['date']=='1405/08/02');self.assertEqual(d['weekday'],'شنبه');self.assertEqual([x['check_in'] for x in d['entries']],['09:00','11:00','13:00']);self.assertEqual(d['worked_minutes'],600);self.assertEqual(d['required_minutes'],480);self.assertEqual(d['overtime_minutes'],120);self.assertEqual(d['approved_minutes'],0);self.assertTrue(any('overlap' in x['flags'] for x in d['entries']))
        for r in self.s.all_visible(self.people['manager'],'attendance','mana'):self.s.save_record(self.people['manager'],'attendance',dict(r['payload'],status='approved'),'mana',r['id'],r['version'])
        d=next(x for x in self.report()['days'] if x['date']=='1405/08/02');self.assertEqual(d['approved_minutes'],600);self.assertEqual(d['approved_overtime_minutes'],120);self.assertTrue(all(x['version']==2 for x in d['entries']))
    def test_incomplete_entry_has_no_actual_hours_no_absence_inference(self):
        self.insert(self.row('001','1405/08/02','09:00',''));d=next(x for x in self.report()['days'] if x['date']=='1405/08/02');self.assertEqual(d['entries'][0]['status'],'needs_review');self.assertIn('incomplete_interval',d['entries'][0]['flags']);self.assertEqual(d['worked_minutes'],0);self.assertNotIn('no_record',d['flags']);self.assertIn('غیبت قطعی نیست',self.report()['note'])
    def test_weekends_exceptions_and_approved_leave(self):
        self.insert(self.row('001','1405/08/01','09:00','10:00'),self.row('001','1405/08/02','09:00','18:00'));report=self.report();friday=next(x for x in report['days'] if x['date']=='1405/08/01');self.assertEqual(friday['weekday'],'جمعه');self.assertFalse(friday['working_day']);self.assertEqual(friday['overtime_minutes'],60)
        policy=default_policy();policy['exclude_official_holidays']=False;policy['exceptions']['1405/08/01']=dict(working=True,start='09:00',end='17:00',break_minutes=0);self.s.workspace_policy(self.people['manager'],'mana','attendance',policy);d=next(x for x in self.report()['days'] if x['date']=='1405/08/01');self.assertTrue(d['working_day']);self.assertEqual(d['overtime_minutes'],0)
        leave=self.s.desk_leave_save(self.people['staff'],'mana',dict(start_date='1405/08/02',end_date='1405/08/02',leave_type='استحقاقی'))['item'];self.s.desk_leave_review(self.people['manager'],leave['id'],1,'approved');d=next(x for x in self.report()['days'] if x['date']=='1405/08/02');self.assertTrue(d['leave']);self.assertEqual(d['required_minutes'],0);self.assertIn('leave_work_overlap',d['flags']);self.assertEqual(d['overtime_minutes'],0)
    def test_hourly_leave_reduces_required_time_and_unauthorized_schedule_changes_fail(self):
        leave=self.s.desk_leave_save(self.people['staff'],'mana',dict(start_date='1405/08/02',end_date='1405/08/02',leave_type='ساعتی',start_time='09:00',end_time='11:00'))['item'];self.s.desk_leave_review(self.people['manager'],leave['id'],1,'approved');d=next(x for x in self.report()['days'] if x['date']=='1405/08/02');self.assertEqual(d['required_minutes'],360)
        with self.assertRaises(DomainError):self.s.workspace_policy(self.people['staff'],'mana','attendance',default_policy())
        with self.assertRaises(ValueError):p=default_policy();p['week']['5']['break_minutes']=600;self.s.workspace_policy(self.people['manager'],'mana','attendance',p)
    def test_csv_and_xlsx_preview_partial_and_duplicate(self):
        from openpyxl import Workbook
        rows=[['کد پرسنلی','تاریخ','ورود','خروج'],['001','1405/08/02','09:00','17:00'],['001','1405/08/02','09:00','17:00'],['001','1405/08/03','09:00','']]
        csv=self.root/'تردد.csv';csv.write_text('\n'.join(','.join(r) for r in rows),'utf-8-sig');book=Workbook();sheet=book.active
        for row in rows:sheet.append(row)
        excel=self.root/'تردد.xlsx';book.save(excel);book.close()
        for path in (csv,excel):
            headers,data=read_table(path);result=preview(headers,data,guess_mapping(headers),'1405/08');self.assertEqual([r['valid'] for r in result],[True,False,True]);self.assertIn('تکراری',result[1]['error']);self.assertEqual(result[2]['payload']['status'],'needs_review')
    def test_per_year_policy_does_not_leak_other_staff_rules(self):
        p=default_policy();p['people']={self.people['staff']['id']:dict(week={},exceptions={'1405/08/02':dict(working=False,start='09:00',end='17:00',break_minutes=0)}),self.people['other']['id']:dict(week={},exceptions={})};self.s.workspace_policy(self.people['manager'],'mana','attendance',p);visible=self.s.workspace_policy(self.people['staff'],'mana','attendance')['value']['people'];self.assertEqual(set(visible),{self.people['staff']['id']})

class PermissionHttpTests(unittest.TestCase):
    def test_active_session_restrictions_immediate_and_independent_modules(self):
        from org_http import RunningServer
        from org_client import Client
        with tempfile.TemporaryDirectory() as tmp:
            server=RunningServer(tmp,'127.0.0.1',0,background=False);s=server.store;admin=s.bootstrap('admin','1','مدیر');uid=s.save_user(admin,dict(username='staff',password='1',fullname='کارمند',memberships=[dict(company_id='mana',role='employee')]))['id'];staff=s.user(uid);s.save_record(admin,'employee',dict(title='کارمند',employee_code='001',user_id=uid),'mana');s.desk_note_save(staff,dict(title='یادداشت',body='خصوصی'));s.save_record(admin,'task',dict(title='کار',due_date='1405/08/10',assignee_id=uid),'mana');root=Client(f'http://127.0.0.1:{server.port}');client=Client(f'http://127.0.0.1:{server.port}')
            try:
                root.login('admin','1');client.login('staff','1');self.assertEqual(len(client.request('workspace/attendance-people',company='mana')['people']),1)
                root.request('permissions',dict(user_id=uid,company='mana',permissions={'module.attendance.view':False,'module.desk.view':False,'module.chat.view':False}))
                with self.assertRaises(DomainError):client.request('workspace/attendance-people',company='mana')
                with self.assertRaises(DomainError):client.request('desk')
                self.assertEqual(client.request('chat/rooms'),[]);today=client.request('workspace/today');self.assertFalse(today['notes']);self.assertEqual([r['title'] for r in today['tasks']],['کار']);self.assertTrue(client.request('dashboard'));self.assertIsNotNone(client.request('users'))
                self.assertTrue(all('permissions' not in m for p in client.request('users') if p['id']!=uid for m in p['memberships']))
            finally:root.session.close();client.session.close();server.close()
    def test_manager_permissions_scoped_and_cannot_modify_self_or_global(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);admin=s.bootstrap('admin','1','مدیر کل');manager=s.user(s.save_user(admin,dict(username='manager',password='1',fullname='مدیر',memberships=[dict(company_id='mana',role='company_manager')]))['id']);staff=s.user(s.save_user(admin,dict(username='staff',password='1',fullname='کارمند',memberships=[dict(company_id='mana',role='employee')]))['id'])
            with self.assertRaises(DomainError):s.save_permissions(manager,manager['id'],'mana',{'module.chat.view':False})
            with self.assertRaises(DomainError):s.save_permissions(manager,admin['id'],'mana',{'module.chat.view':False})
            s.save_permissions(admin,manager['id'],'mana',{'module.access.manage':False});fresh=s.user(manager['id'])
            with self.assertRaises(DomainError):s.save_permissions(fresh,staff['id'],'mana',{'module.chat.view':False})

if __name__=='__main__':unittest.main()
