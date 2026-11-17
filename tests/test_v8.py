import os,sys,tempfile,unittest,json,copy,zipfile,hashlib,base64,threading,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from org_store import Store,DomainError
from backup_bundle import create_bundle,verify_bundle

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.s=Store(self.root/'company-server');self.admin=self.s.bootstrap('admin','1','مدیر');self.staff=self.make('staff','mana');self.other=self.make('other','mana');self.manager=self.make('manager','mana','company_manager');self.foreign=self.make('foreign','arka','company_manager')
        self.scope='__shared_chat__'
        if getattr(self,'seed_chat',True):self.room=self.s.workspace_group_create(self.admin,self.scope,'مشترک',[self.staff['id'],self.other['id'],self.manager['id']])['room']
    def tearDown(self):self.temp.cleanup()
    def test_custom_group_membership_and_archive(self):
        room=self.s.workspace_group_create(self.staff,self.scope,'گروه آزمایشی',[self.manager['id']])['room']
        self.s.chat_send(self.staff,self.scope,room,text='پیام گروه')
        self.assertEqual(self.s.chat_list(self.manager,self.scope,room)['items'][0]['text'],'پیام گروه')
        with self.assertRaises(DomainError):self.s.chat_list(self.other,self.scope,room)
        with self.assertRaises(DomainError):self.s.chat_list(self.foreign,self.scope,room)
        self.s.workspace_hide_room(self.staff,self.scope,room)
        with self.assertRaises(DomainError):self.s.chat_list(self.staff,self.scope,room)
        self.s.workspace_restore_group(self.staff,self.scope,room);self.assertEqual(self.s.chat_list(self.staff,self.scope,room)['items'][0]['text'],'پیام گروه')
    def test_saved_messages_are_private_and_allow_attachments(self):
        saved='saved:'+self.staff['id'];self.assertTrue(any(r['room']==saved for r in self.s.chat_rooms(self.staff)))
        private=self.s.chat_send(self.staff,self.scope,saved,text='یادداشت خصوصی',attachments=[{'name':'private.txt','data':base64.b64encode(b'private').decode()}]);file_id=self.s.chat_list(self.staff,self.scope,saved)['items'][0]['files'][0]['id']
        with self.assertRaises(DomainError):self.s.chat_list(self.admin,self.scope,saved)
        with self.assertRaises(DomainError):self.s.chat_download(self.admin,file_id)
        room=self.s.workspace_direct(self.staff,self.scope,self.other['id'])['room']
        sent=self.s.chat_send(self.staff,self.scope,room,text='پیام شخصی',attachments=[{'name':'a.txt','data':base64.b64encode(b'hello').decode()}]);self.assertEqual(self.s.chat_list(self.other,self.scope,room)['items'][0]['text'],'پیام شخصی')
        with self.assertRaises(DomainError):self.s.chat_list(self.manager,self.scope,room)
        preview=self.s.workspace_clear_chat(self.staff,self.scope,room);self.assertEqual(preview['count'],1);self.s.workspace_clear_chat(self.staff,self.scope,room,preview['through']);self.assertTrue(self.s.chat_list(self.other,self.scope,room)['items'][0]['deleted'])
        trash=next(item for item in self.s.workspace_trash(self.staff) if item['trash_kind']=='message');self.assertEqual(trash['id'],sent['id']);self.assertFalse(any(item.get('id')==sent['id'] for item in self.s.workspace_trash(self.manager)));self.s.workspace_trash(self.staff,'message',sent['id'],1,restore=True);self.assertEqual(self.s.chat_list(self.staff,self.scope,room)['items'][0]['text'],'پیام شخصی')
    def test_deleted_message_can_be_restored_or_purged_only_by_actor(self):
        sent=self.s.chat_send(self.staff,self.scope,self.room,text='نمونه');self.s.chat_action(self.staff,sent['id'],'delete');self.assertTrue(any(x['id']==sent['id'] for x in self.s.workspace_trash(self.staff)))
        with self.assertRaises(DomainError):self.s.workspace_trash(self.other,'message',sent['id'],1,restore=True)
        self.s.workspace_trash(self.staff,'message',sent['id'],1,restore=True);self.assertEqual(self.s.chat_list(self.staff,self.scope,self.room)['items'][0]['text'],'نمونه');self.s.chat_action(self.staff,sent['id'],'delete');self.s.workspace_trash(self.staff,'message',sent['id'],1,purge=True);self.assertFalse(any(x['id']==sent['id'] for x in self.s.workspace_trash(self.staff)))
    def test_unlinked_invoice_can_be_purged_without_reusing_number(self):
        buyer=self.s.save_record(self.admin,'client',{'title':'مشتری'},'mana');payload={'title':'فروش','client_id':buyer['id'],'number':'__AUTO__','date':'1405/08/01','document_type':'فاکتور فروش','status':'draft','lines':[{'description':'خدمت','quantity':'1','unit_price':'100'}]};invoice=self.s.save_record(self.admin,'invoice',payload,'mana');self.s.delete_record(self.admin,invoice['id'],invoice['version']);self.s.workspace_trash(self.admin,'record',invoice['id'],invoice['version']+1,purge=True);next_invoice=self.s.save_record(self.admin,'invoice',payload,'mana');self.assertEqual(next_invoice['payload']['number'],'101')
    def test_archived_group_requires_manager_and_restores_history(self):
        self.s.chat_send(self.staff,self.scope,self.room,text='پیام نمونه')
        with self.assertRaises(DomainError):self.s.workspace_hide_room(self.staff,self.scope,self.room)
        self.s.workspace_hide_room(self.manager,self.scope,self.room)
        self.assertFalse(any(r['room']==self.room and r['company']==self.scope for r in self.s.chat_rooms(self.staff)))
        with self.assertRaises(DomainError):self.s.chat_list(self.staff,self.scope,self.room)
        with self.assertRaises(DomainError):self.s.workspace_restore_group(self.staff,self.scope,self.room)
        self.s.workspace_restore_group(self.manager,self.scope,self.room);self.assertEqual(self.s.chat_list(self.staff,self.scope,self.room)['items'][0]['text'],'پیام نمونه')
    def test_hidden_direct_is_personal_and_reopen_restores_history(self):
        room=self.s.workspace_direct(self.staff,self.scope,self.other['id'])['room'];self.s.chat_send(self.staff,self.scope,room,text='پیام')
        self.s.workspace_hide_room(self.staff,self.scope,room)
        self.assertFalse(any(r['room']==room for r in self.s.chat_rooms(self.staff)))
        self.assertTrue(any(r['room']==room for r in self.s.chat_rooms(self.other)))
        self.s.workspace_direct(self.staff,self.scope,self.other['id']);self.assertTrue(any(r['room']==room for r in self.s.chat_rooms(self.staff)));self.assertEqual(self.s.chat_list(self.staff,self.scope,room)['items'][0]['text'],'پیام')
    def test_manager_can_manage_staff_group_without_reading_messages(self):
        room=self.s.workspace_group_create(self.staff,self.scope,'کارکنان',[self.other['id']])['room'];self.s.chat_send(self.staff,self.scope,room,text='خصوصی کارکنان')
        with self.assertRaises(DomainError):self.s.chat_list(self.manager,self.scope,room)
        self.s.workspace_hide_room(self.manager,self.scope,room)
        with self.assertRaises(DomainError):self.s.chat_list(self.staff,self.scope,room)
        self.s.workspace_restore_group(self.manager,self.scope,room);self.assertEqual(self.s.chat_list(self.staff,self.scope,room)['items'][0]['text'],'خصوصی کارکنان')
    def test_clear_chat_is_authorized_and_never_clears_new_messages(self):
        self.s.chat_send(self.staff,self.scope,self.room,text='قدیمی',attachments=[{'name':'example.txt','data':base64.b64encode(b'private').decode()}])
        file_id=self.s.chat_list(self.staff,self.scope,self.room)['items'][0]['files'][0]['id']
        with self.assertRaises(DomainError):self.s.workspace_clear_chat(self.staff,self.scope,self.room)
        preview=self.s.workspace_clear_chat(self.manager,self.scope,self.room);self.assertEqual(preview['count'],1)
        self.s.chat_send(self.staff,self.scope,self.room,text='جدید')
        result=self.s.workspace_clear_chat(self.manager,self.scope,self.room,preview['through']);self.assertEqual(result['count'],1)
        rows=self.s.chat_list(self.staff,self.scope,self.room)['items'];self.assertTrue(rows[0]['deleted']);self.assertEqual(rows[-1]['text'],'جدید')
        with self.assertRaises(DomainError):self.s.chat_download(self.staff,file_id)
        room=self.s.workspace_direct(self.staff,self.scope,self.other['id'])['room'];self.s.chat_send(self.staff,self.scope,room,text='پیام خصوصی')
        with self.assertRaises(DomainError):self.s.workspace_clear_chat(self.manager,self.scope,room)
        preview=self.s.workspace_clear_chat(self.other,self.scope,room);self.s.workspace_clear_chat(self.other,self.scope,room,preview['through']);self.assertTrue(self.s.chat_list(self.staff,self.scope,room)['items'][0]['deleted'])
    def make(self,name,co,role='employee'):
        id=self.s.save_user(self.admin,dict(username=name,password='1',fullname=name,memberships=[dict(company_id=co,role=role)]))['id'];return self.s.user(id)
    def task(self,**changes):
        p=dict(title='کار نمونه',due_date='1405/08/10',status='draft',require_approval=True,assignee_id=self.staff['id'],estimate_hours='3');p.update(changes);return self.s.save_record(self.admin,'task',p,'mana')
    def request(self,actor=None,**changes):
        p=dict(title='مأموریت نمونه',start_date='۱۴۰۵/۰۸/۱۰',end_date='1405/08/11',notes='شرح',hours='2',amount='100');p.update(changes);return self.s.workspace_request_save(actor or self.staff,'mana','mission',p)
    def test_request_identity_scope_and_canonical_dates(self):
        r=self.request(user_id=self.other['id'],status='approved');self.assertEqual(r['user_id'],self.staff['id']);self.assertEqual(r['status'],'pending');self.assertEqual(r['payload']['start_date'],'1405/08/10');self.assertFalse(self.s.workspace_requests(self.other));self.assertFalse(self.s.workspace_requests(self.foreign));self.assertTrue(self.s.workspace_notifications(self.manager))
        with self.assertRaises(DomainError):self.s.workspace_request_item(self.other,r['id'])
        with self.assertRaises(DomainError):self.s.workspace_request_review(self.staff,r['id'],1,'approved')
        with self.assertRaises(DomainError):self.s.workspace_request_review(self.foreign,r['id'],1,'approved')
    def test_sequential_route_self_approval_stale_and_decision_history(self):
        self.s.workspace_policy(self.manager,'mana','routes',{'mission':[self.manager['id'],self.admin['id']]});r=self.request()
        with self.assertRaises(DomainError):self.s.workspace_request_review(self.admin,r['id'],1,'approved')
        r=self.s.workspace_request_review(self.manager,r['id'],1,'approved','مرحله اول');self.assertEqual(r['status'],'pending');self.assertEqual(r['stage'],1)
        with self.assertRaises(DomainError):self.s.workspace_request_review(self.admin,r['id'],1,'approved')
        r=self.s.workspace_request_review(self.admin,r['id'],2,'approved','مرحله دوم');self.assertEqual(r['status'],'approved');self.assertEqual(len(r['decisions']),2)
        with self.assertRaises(DomainError):self.request(self.manager)
    def test_request_edit_cancel_and_invalid_numbers(self):
        r=self.request();new=self.s.workspace_request_save(self.staff,'mana','mission',dict(r['payload'],title='اصلاح'),r['id'],1);self.assertEqual(new['version'],2);self.s.workspace_request_review(self.staff,r['id'],2,'cancelled')
        with self.assertRaises(DomainError):self.s.workspace_request_save(self.staff,'mana','mission',r['payload'],r['id'],3)
        with self.assertRaises(ValueError):self.request(amount='-10')
    def test_views_favorites_and_search_are_owner_scoped(self):
        t=self.task();self.s.workspace_views(self.staff,{'name':'کارهای من','company':'mana','assignee':'me'});self.assertEqual(len(self.s.workspace_views(self.staff)),1);self.assertFalse(self.s.workspace_views(self.other));self.s.workspace_save(self.staff,'record',t['id']);self.assertTrue(self.s.workspace_today(self.staff)['tasks'][0]['saved']);self.assertFalse(self.s.workspace_search(self.other,'نمونه'));self.assertTrue(self.s.workspace_search(self.staff,'نمونه'))
    def test_board_approval_dependencies_and_estimate_validation(self):
        t=self.task();p=dict(t['payload'],status='completed')
        with self.assertRaises(DomainError):self.s.save_record(self.staff,'task',p,'mana',t['id'],1)
        dep=self.task(title='پیش نیاز');t=self.task(dependencies=[dep['id']])
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'task',dict(t['payload'],status='in_progress'),'mana',t['id'],1)
        with self.assertRaises(ValueError):self.task(estimate_hours='9000')
    def test_trash_private_note_and_record_scope_version(self):
        n=self.s.desk_note_save(self.staff,dict(title='خصوصی',body='متن'));self.s.desk_note_delete(self.staff,n['id'],1);self.assertFalse(self.s.workspace_trash(self.admin));self.assertEqual(len(self.s.workspace_trash(self.staff)),1)
        with self.assertRaises(DomainError):self.s.workspace_trash(self.other,'note',n['id'],2,True)
        self.s.workspace_trash(self.staff,'note',n['id'],2,True);self.assertEqual(len(self.s.desk_snapshot(self.staff)['notes']),1)
        t=self.task();self.s.delete_record(self.admin,t['id'],1);self.assertFalse(self.s.workspace_trash(self.foreign));self.s.workspace_trash(self.admin,'record',t['id'],2,True);self.assertEqual(self.s.record(t['id'])['version'],3)
    def test_trash_expiry_and_stale_restore(self):
        n=self.s.desk_note_save(self.staff,dict(title='من',body=''));self.s.desk_note_delete(self.staff,n['id'],1)
        with self.assertRaises(DomainError):self.s.workspace_trash(self.staff,'note',n['id'],1,True)
        with self.s.db(True) as c:c.execute('UPDATE desk_notes SET updated=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=31)).isoformat(),n['id']))
        self.assertEqual(len(self.s.workspace_trash(self.staff)),1)
        with self.assertRaises(DomainError):self.s.workspace_trash(self.staff,'note',n['id'],2,True)
        self.s.workspace_trash(self.staff,'note',n['id'],2,purge=True);self.assertFalse(self.s.workspace_trash(self.staff))
    def test_leave_policy_balance_and_workload_acl(self):
        policy=dict(daily_hours='8',working_days=[0,1,2,3,4,5,6],exclude_holidays=False,people={self.staff['id']:dict(annual_hours='200',opening_hours='8',daily_hours='8')});self.s.workspace_policy(self.manager,'mana','leave',policy);r=self.s.desk_leave_save(self.staff,'mana',dict(start_date='1405/08/10',end_date='1405/08/11',leave_type='استحقاقی'))['item'];self.s.desk_leave_review(self.manager,r['id'],1,'approved');d=self.s.workspace_leave_balance(self.staff,'mana',1405);self.assertEqual(d['used'],'16');self.assertEqual(d['remaining'],'192');self.assertNotIn(self.staff['id'],self.s.workspace_policy(self.other,'mana','leave')['value']['people'])
        with self.assertRaises(DomainError):self.s.workspace_leave_balance(self.other,'mana',1405,self.staff['id'])
        with self.assertRaises(DomainError):self.s.workspace_workload(self.staff,'mana','1405/08')
        self.task(estimate_hours='15');d=self.s.workspace_workload(self.manager,'mana','1405/08');person=next(p for p in d['people'] if p['user']==self.staff['id']);self.assertTrue(any(x['overloaded'] for x in person['days']))
    def test_hourly_overlaps_do_not_double_deduct(self):
        policy=dict(working_days=list(range(7)),exclude_holidays=False,people={self.staff['id']:dict(annual_hours='200',daily_hours='8')});self.s.workspace_policy(self.manager,'mana','leave',policy)
        for a,b in [('09:00','11:00'),('10:00','12:00')]:
            r=self.s.desk_leave_save(self.staff,'mana',dict(start_date='1405/08/10',end_date='1405/08/10',leave_type='ساعتی',start_time=a,end_time=b))['item'];self.s.desk_leave_review(self.manager,r['id'],1,'approved')
        self.assertEqual(self.s.workspace_leave_balance(self.staff,'mana',1405)['used'],'3')
    def test_chat_idempotent_reply_thread_mentions_search_saved_and_pins(self):
        m=self.s.chat_send(self.staff,self.scope,self.room,'سلام @other',request_id='0123456789abcdef');again=self.s.chat_send(self.staff,self.scope,self.room,'سلام @other',request_id='0123456789abcdef');self.assertEqual(m['id'],again['id']);self.assertEqual(len(self.s.chat_list(self.staff,self.scope,self.room)['items']),1);self.assertTrue(self.s.workspace_notifications(self.other))
        r=self.s.chat_send(self.other,self.scope,self.room,'پاسخ',reply_to=m['id']);self.assertEqual(len(self.s.chat_list(self.staff,self.scope,self.room,thread=m['id'])['items']),2);self.s.chat_action(self.staff,r['id'],'save');self.assertEqual(len(self.s.chat_list(self.staff,self.scope,self.room,saved=True)['items']),1);self.assertFalse(self.s.chat_list(self.manager,self.scope,self.room,saved=True)['items']);self.s.chat_action(self.manager,m['id'],'pin');self.assertEqual(len(self.s.chat_list(self.staff,self.scope,self.room,pinned=True)['items']),1);self.assertEqual(self.s.chat_list(self.staff,self.scope,self.room,q='پاسخ')['items'][0]['id'],r['id'])
    def test_private_chat_not_readable_even_by_unrelated_manager_admin(self):
        room=self.s.workspace_direct(self.staff,self.scope,self.other['id']);self.assertTrue(room['direct']);again=self.s.workspace_direct(self.other,self.scope,self.staff['id']);self.assertEqual(room['room'],again['room']);m=self.s.chat_send(self.staff,self.scope,room['room'],'محرمانه',attachments=[dict(name='private.txt',data=base64.b64encode(b'private').decode())]);items=self.s.chat_list(self.other,self.scope,room['room'])['items'];self.assertEqual(len(items),1);file=items[0]['files'][0]
        for actor in (self.admin,self.manager,self.foreign):
            with self.assertRaises(DomainError):self.s.chat_list(actor,self.scope,room['room'])
            with self.assertRaises(DomainError):self.s.chat_download(actor,file['id'])
            self.assertFalse(any(r['room']==room['room'] for r in self.s.chat_rooms(actor)))
        self.assertTrue(self.s.chat_updates(self.other)['items']);self.assertFalse(any(r['text']=='محرمانه' for r in self.s.chat_updates(self.manager)['items']));self.s.chat_action(self.staff,m['id'],'pin')
    def test_private_chat_cross_company_and_reply_cannot_cross_rooms(self):
        direct=self.s.workspace_direct(self.staff,self.scope,self.foreign['id']);self.assertEqual(direct['display_title'],self.foreign['fullname'])
        m=self.s.chat_send(self.manager,self.scope,self.room,'پیام گروه')
        with self.assertRaises(DomainError):self.s.chat_send(self.staff,self.scope,direct['room'],'پاسخ',reply_to=m['id'])
    def test_message_to_task_preserves_link_and_acl(self):
        m=self.s.chat_send(self.staff,self.scope,self.room,'بررسی پرونده');t=self.s.workspace_task_from_message(self.staff,m['id'],dict(title='پیگیری',due_date='1405/08/12',company_id='mana'));self.assertEqual(t['payload']['source_message'],m['id']);self.assertEqual(t['payload']['assignee_id'],self.staff['id'])
    def test_deadline_proposal_atomic_change_and_targeted_notice(self):
        a=self.task();b=self.task(title='دوم');p=dict(title='تمدید',source='https://tax.gov.ir/example',new_date='1405/08/15',old_date='1405/08/10',reason='با تأیید مسئول',task_ids=a['id']+','+b['id'],status='approved');self.s.save_record(self.manager,'proposal',p,'mana');self.assertEqual(self.s.record(a['id'])['payload']['due_date'],'1405/08/15');self.assertTrue(self.s.workspace_notifications(self.staff));self.assertFalse(self.s.workspace_notifications(self.foreign))
        with self.assertRaises(DomainError):self.s.save_record(self.manager,'proposal',dict(p,new_date='1405/08/20'),'mana')
        self.assertEqual(self.s.record(b['id'])['payload']['due_date'],'1405/08/15')
    def test_record_delta_filters_scope_and_removals(self):
        a=self.task();base=self.s.records_revision();self.s.chat_send(self.staff,self.scope,self.room,'فقط چت');self.assertEqual(self.s.records_revision(),base);d=self.s.workspace_records_delta(self.staff,base,[a['id']]);self.assertFalse(d['items']);self.s.delete_record(self.admin,a['id'],1);d=self.s.workspace_records_delta(self.staff,base,[a['id']]);self.assertEqual(d['removed'],[a['id']]);self.assertFalse(self.s.workspace_records_delta(self.foreign,base)['items'])
    def test_notice_delta_recipient_privacy_and_expiration(self):
        from unittest.mock import patch
        notice=self.s.publish(self.admin,dict(companies=['mana'],users=[self.staff['id'],self.other['id']],title='اعلان نمونه',body='متن'))
        value=self.s.workspace_records_delta(self.staff,0);item=next(r for r in value['items'] if r['id']==notice['id']);self.assertNotIn('recipients',item['payload'])
        exported=self.s.export_scope(self.staff);self.assertNotIn('recipients',next(r for r in exported['records'] if r['id']==notice['id'])['payload'])
        base=value['revision'];payload=notice['payload'];payload['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        with self.s.db(True) as c:c.execute('UPDATE records SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),notice['id']))
        with patch('workspace_store.time.time',return_value=time.time()+120):
            delta=self.s.workspace_records_delta(self.staff,base,[notice['id']]);self.assertIn(notice['id'],delta['removed']);self.assertFalse(any(r['id']==notice['id'] for r in delta['items']))
    def test_notification_target_rechecks_owner_and_message_room_access(self):
        room=self.s.workspace_direct(self.staff,self.scope,self.other['id']);m=self.s.chat_send(self.staff,self.scope,room['room'],'سلام @other');n=self.s.workspace_notifications(self.other)[0];target=self.s.workspace_target(self.other,n['id']);self.assertEqual(target['kind'],'message');self.assertEqual(target['room'],room['room']);self.assertEqual(target['message']['id'],m['id'])
        with self.assertRaises(DomainError):self.s.workspace_target(self.manager,n['id'])
        self.s.chat_action(self.staff,m['id'],'delete')
        with self.assertRaises(DomainError):self.s.workspace_target(self.other,n['id'])
    def test_private_chat_audit_metadata_is_hidden_from_nonparticipants(self):
        room=self.s.workspace_direct(self.staff,self.scope,self.other['id']);m=self.s.chat_send(self.staff,self.scope,room['room'],'سلام');self.s.chat_state(self.other,self.scope,room['room'],seq=m['seq']);self.assertFalse(any(room['room'] in json.dumps(r) for r in self.s.history(self.admin)));self.assertEqual(self.s.chat_list(self.staff,self.scope,room['room'])['items'][0]['id'],m['id'])
    def test_request_id_cannot_be_reused_for_different_content(self):
        self.s.chat_send(self.staff,self.scope,self.room,'یک',request_id='aaaa000011112222')
        with self.assertRaises(DomainError) as ctx:self.s.chat_send(self.staff,self.scope,self.room,'دو',request_id='aaaa000011112222')
        self.assertEqual(ctx.exception.status,409);self.assertEqual(len(self.s.chat_list(self.staff,self.scope,self.room)['items']),1)
    def test_retry_is_atomic_across_separate_store_instances(self):
        other_store=Store(self.root/'company-server');barrier=threading.Barrier(2);results=[];errors=[]
        def send(store):
            try:barrier.wait();results.append(store.chat_send(self.staff,self.scope,self.room,'ارسال','text',request_id='cccc000011112222'))
            except Exception as e:errors.append(e)
        workers=[threading.Thread(target=send,args=(store,)) for store in (self.s,other_store)]
        for t in workers:t.start()
        for t in workers:t.join(10)
        self.assertFalse(errors);self.assertEqual(len(results),2);self.assertEqual(results[0]['id'],results[1]['id']);self.assertEqual(len(self.s.chat_list(self.staff,self.scope,self.room)['items']),1)
    def test_leave_opening_balance_is_scoped_to_configured_year(self):
        policy=dict(people={self.staff['id']:dict(daily_hours='8',years={'1405':dict(annual_hours='200',opening_hours='8'),'1406':dict(annual_hours='210',opening_hours='0')})});self.s.workspace_policy(self.manager,'mana','leave',policy)
        self.assertEqual(self.s.workspace_leave_balance(self.staff,'mana',1405)['remaining'],'208');self.assertEqual(self.s.workspace_leave_balance(self.staff,'mana',1406)['remaining'],'210');self.assertIsNone(self.s.workspace_leave_balance(self.staff,'mana',1407)['remaining'])
    def test_contract_links_same_company_and_reminder_dates(self):
        client=self.s.save_record(self.admin,'client',dict(title='مشتری'),'mana');contract=self.s.save_record(self.admin,'contract',dict(title='قرارداد',due_date='1405/09/01',client_id=client['id']),'mana');self.s.save_record(self.admin,'installment',dict(title='قسط',due_date='1405/08/20',amount='10',contract_id=contract['id']),'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'contract',dict(title='نامعتبر',due_date='1405/09/01',client_id=client['id']),'arka')
    def test_payroll_batch_server_recomputes_and_keeps_snapshot(self):
        from payroll_ui import DEFAULTS
        p=dict(DEFAULTS,name='نمونه',code='001',base='100000000',days='30',period='1405/08');r=self.s.save_record(self.manager,'payroll_batch',dict(title='حقوق',period='1405/08',slips=[p],total_net='1'),'mana');self.assertNotEqual(r['payload']['total_net'],'1')
        with self.assertRaises(DomainError):self.s.save_record(self.manager,'payroll_batch',r['payload'],'mana',r['id'],1)
        with self.assertRaises(DomainError):self.s.save_record(self.staff,'payroll_batch',r['payload'],'mana')

class BackupUpdateDeliveryTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_encrypted_backup_roundtrip_wrong_password_and_tamper(self):
        from backup_crypto import PasswordRequired,encrypted
        path=self.root/'test.karname';create_bundle(path,dict(events=[],settings={}),{'sample.txt':b'secret'},password='رمز من');self.assertTrue(encrypted(path));self.assertNotIn(b'secret',path.read_bytes());self.assertEqual(verify_bundle(path,password='رمز من')[1]['sample.txt'],b'secret')
        with self.assertRaises(PasswordRequired):verify_bundle(path)
        with self.assertRaises(ValueError):verify_bundle(path,password='wrong')
        raw=bytearray(path.read_bytes());raw[-10]^=1;path.write_bytes(raw)
        with self.assertRaises(ValueError):verify_bundle(path,password='رمز من')
    def test_scheduled_rotation_second_copy_and_legacy_import(self):
        from backup_schedule import create_scheduled
        first=self.root/'daily';second=self.root/'second';clock=datetime(2026,10,1,tzinfo=timezone.utc)
        for days in range(5):create_scheduled(first,dict(events=[],settings={}),{},'backup',2,2,second,clock+timedelta(days=days))
        self.assertEqual(len(list(first.glob('*daily*.karname'))),2);self.assertEqual(len(list(second.glob('*daily*.karname'))),2)
        old=self.root/'old.zip';create_bundle(old,dict(events=[],settings={}));self.assertTrue(verify_bundle(old))
    def test_windows_encrypted_queue_survives_restart_and_retry(self):
        from chat_delivery import DeliveryQueue
        q=DeliveryQueue(self.root,'http://127.0.0.1:1','user');q.save_draft('mana','general','پیش‌نویس');id=q.enqueue(dict(company='mana',room='general',text='سلام'));q2=DeliveryQueue(self.root,'http://127.0.0.1:1','user');self.assertEqual(q2.draft('mana','general')['text'],'پیش‌نویس');self.assertEqual(q2.pending()['payload']['request_id'],id);self.assertFalse(DeliveryQueue(self.root,'http://127.0.0.1:1','other').pending());q2.failed(id,'خطا',True);self.assertIsNone(q2.pending());q2.retry(id);q2.acknowledge(id);self.assertFalse(q2.value['outbox'])
    def test_signed_update_integrity_version_and_staging(self):
        from cryptography.hazmat.primitives.asymmetric import rsa,padding
        from cryptography.hazmat.primitives import hashes,serialization
        from updater import inspect_package,stage_package
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048);public=self.root/'public.pem';public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo));raw=b'MZ'+b'fixture executable';m=dict(format='karname-update-v1',version='9.1',files={'Karname.exe':dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())});manifest=json.dumps(m).encode();signature=key.sign(manifest,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256());path=self.root/'update.zip'
        with zipfile.ZipFile(path,'w') as z:z.writestr('update.json',manifest);z.writestr('update.sig',signature);z.writestr('Karname.exe',raw)
        self.assertEqual(inspect_package(path,public)['version'],'9.1');stage,_=stage_package(path,self.root,public);self.assertEqual((stage/'Karname.exe').read_bytes(),raw)
        m['version']='8.6';old_manifest=json.dumps(m).encode();old_signature=key.sign(old_manifest,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256());old_path=self.root/'old-update.zip'
        with zipfile.ZipFile(old_path,'w') as z:z.writestr('update.json',old_manifest);z.writestr('update.sig',old_signature);z.writestr('Karname.exe',raw)
        with self.assertRaises(ValueError):inspect_package(old_path,public)
        with zipfile.ZipFile(path,'a') as z:z.writestr('../escape.txt',b'bad')
        with self.assertRaises(ValueError):inspect_package(path,public)
    def test_local_assistant_exact_sentences_and_task_review_suggestions(self):
        from local_assistant import summarize,task_suggestions
        text='جلسه مالی برگزار شد.\nباید گزارش مالی ارسال شود.\nپیگیری بیمه توسط مسئول مالی انجام شود.';summary=summarize(text,2);self.assertTrue(all(s in text for s in summary));self.assertTrue(task_suggestions(text));self.assertLessEqual(len(summary),2)

class WorkspaceHttpTests(unittest.TestCase):
    def test_certificate_change_rejected_without_overwriting_existing_files(self):
        from org_http import make_certificate
        with tempfile.TemporaryDirectory() as tmp:
            cert,key,fp=make_certificate(tmp,['192.168.1.10']);before=(cert.read_bytes(),key.read_bytes())
            with self.assertRaisesRegex(ValueError,'نشانی'):make_certificate(tmp,['192.168.1.11'])
            self.assertEqual((cert.read_bytes(),key.read_bytes()),before);self.assertEqual(make_certificate(tmp,['192.168.1.10'])[2],fp)
            key.unlink()
            with self.assertRaisesRegex(ValueError,'یکی از دو فایل'):make_certificate(tmp,['192.168.1.10'])
            self.assertEqual(cert.read_bytes(),before[0])
    def test_close_interrupts_long_poll(self):
        from org_http import RunningServer
        from org_client import Client
        with tempfile.TemporaryDirectory() as tmp:
            server=RunningServer(tmp,'127.0.0.1',0,background=False);server.store.bootstrap('admin','1','مدیر');client=Client(f'http://127.0.0.1:{server.port}');client.login('admin','1');started=threading.Event();errors=[]
            def poll():
                started.set()
                try:client.request('workspace/changes',after=server.store.revision(),wait=12)
                except Exception as exc:errors.append(exc)
            worker=threading.Thread(target=poll);worker.start();started.wait(2);time.sleep(.4);t=time.monotonic();server.close();duration=time.monotonic()-t;worker.join(3);client.session.close();self.assertLess(duration,3);self.assertFalse(worker.is_alive());self.assertFalse(errors)
    def test_private_chat_and_requests_between_three_http_clients(self):
        from org_http import RunningServer
        from org_client import Client
        with tempfile.TemporaryDirectory() as tmp:
            server=RunningServer(tmp,'127.0.0.1',0,background=False);s=server.store;admin=s.bootstrap('admin','1','مدیر');people=[]
            for name in ('alice','bob','eve'):people.append(s.save_user(admin,dict(username=name,password='1',fullname=name,memberships=[dict(company_id='mana',role='employee')])))
            clients=[Client(f'http://127.0.0.1:{server.port}') for _ in range(3)]
            try:
                for c,name in zip(clients,('alice','bob','eve')):c.login(name,'1')
                scope='__shared_chat__';room=clients[0].request('workspace/direct',dict(company=scope,person=people[1]['id']));clients[0].request('chat/messages',dict(company=scope,room=room['room'],text='خصوصی',request_id='1234567890abcdef'));self.assertEqual(len(clients[1].request('chat/messages',company=scope,room=room['room'])['items']),1)
                with self.assertRaises(DomainError):clients[2].request('chat/messages',company=scope,room=room['room'])
                from version_info import APP_VERSION
                r=clients[0].request('workspace/requests',dict(company='mana',kind='advance',payload=dict(title='مساعده',amount='100')));self.assertEqual(r['user_id'],people[0]['id']);self.assertFalse(clients[2].request('workspace/requests'));self.assertEqual(clients[0].request('status')['version'],APP_VERSION)
            finally:
                for c in clients:c.session.close()
                server.close()

if __name__=='__main__':unittest.main()
