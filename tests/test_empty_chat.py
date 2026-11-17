import base64, unittest, uuid
from datetime import datetime,timezone,timedelta
import test_v8 as fixtures
from org_store import DomainError
from org_http import RunningServer
from org_client import Client

class EmptyChatTests(unittest.TestCase):
    seed_chat=False
    setUp=fixtures.WorkspaceTests.setUp
    tearDown=fixtures.WorkspaceTests.tearDown
    make=fixtures.WorkspaceTests.make
    def test_three_company_memberships_still_produce_one_private_saved_room(self):
        user=self.s.save_user(self.admin,dict(username='three_companies',password='1',fullname='کاربر سه شرکت',memberships=[dict(company_id=co,role='employee') for co in ('mana','airia','arka')]))
        actor=self.s.user(user['id']);rooms=self.s.chat_rooms(actor)
        self.assertEqual(rooms,[]);self.assertEqual(self.s.chat_rooms(self.staff),[]);saved=self.s.workspace_saved_chat(actor);rooms=self.s.chat_rooms(actor)
        self.assertEqual(len(rooms),1);self.assertEqual(saved['room'],'saved:'+actor['id']);self.assertEqual(rooms[0]['company'],'__shared_chat__');self.assertEqual(self.s.chat_rooms(self.staff),[])
        self.s.chat_send(actor,'__shared_chat__',rooms[0]['room'],'یادداشت خصوصی')
        self.assertEqual(len(self.s.chat_rooms(actor)),1)
        with self.assertRaises(DomainError):self.s.chat_list(self.staff,'__shared_chat__',rooms[0]['room'])
        self.s.workspace_hide_room(actor,'__shared_chat__',saved['room']);self.assertEqual(self.s.chat_rooms(actor),[])
        with self.assertRaises(DomainError):self.s.chat_list(actor,'__shared_chat__',saved['room'])
        self.s.workspace_saved_chat(actor);self.assertEqual(self.s.chat_list(actor,'__shared_chat__',saved['room'])['items'][0]['text'],'یادداشت خصوصی')
    def test_group_members_do_not_need_direct_message_permission(self):
        scope='__shared_chat__';self.s.save_permissions(self.admin,self.other['id'],'mana',{'module.chat.direct':False});other=self.s.user(self.other['id'])
        self.assertNotIn(other['id'],{p['id'] for p in self.s.workspace_direct(self.staff,scope)})
        self.assertIn(other['id'],{p['id'] for p in self.s.workspace_group_people(self.staff,scope)})
        room=self.s.workspace_group_create(self.staff,scope,'گروه کاری',[other['id']])
        self.s.chat_send(self.staff,scope,room['room'],text='سلام')
        self.assertEqual(self.s.chat_list(other,scope,room['room'])['items'][0]['text'],'سلام')
        with self.assertRaises(DomainError):self.s.workspace_direct(self.staff,scope,other['id'])
    def test_assistant_can_create_group_for_member_without_direct_access(self):
        self.s.save_permissions(self.admin,self.other['id'],'mana',{'module.chat.direct':False})
        server=RunningServer(self.root/'company-server','127.0.0.1',0,background=False);client=Client('http://127.0.0.1:'+str(server.port))
        try:
            client.login('staff','1')
            from ai_app_actions import collect,normalize_action
            snapshot=dict(actor=client.user,events=[],event_trash=[],overrides={},settings={},pages=[],client=client)
            context=collect(snapshot,'گروه پروژه را با other بساز')
            self.assertIn(self.other['id'],{p['id'] for p in context['public']['people']})
            action=normalize_action({'type':'chat_group_create','company_id':'__shared_chat__','changes':{'title':'پروژه','members':[self.other['id']]}},context)
            created=client.request('workspace/group',dict(company=action['company_id'],title=action['changes']['title'],members=action['changes']['members'],request_id=action['request_id']))
            self.assertIn(created['room'],{r['room'] for r in server.store.chat_rooms(server.store.user(self.other['id']))})
        finally:client.logout();client.session.close();server.close()
    def test_assistant_opens_only_explicit_authorized_private_chat(self):
        from ai_app_actions import capture,collect,normalize_action,execute
        from test_ai_app_actions import owner_for
        server=RunningServer(self.root/'company-server','127.0.0.1',0,background=False);client=Client('http://127.0.0.1:'+str(server.port))
        try:
            client.login('staff','1');owner=owner_for(client.user,client);query='چت شخصی با foreign بساز';context=collect(capture(owner),query)
            action=normalize_action({'type':'chat_direct_create','changes':{'person_id':self.foreign['id']}},context)
            from ai_actions_ui import proposal_text
            self.assertIn('همکار: foreign',proposal_text([action],context));self.assertNotIn(self.foreign['id'],proposal_text([action],context))
            result=execute(owner,[action],context,client.request);self.assertTrue(result[0]['ok'],str(result))
            rooms=[r for r in self.s.chat_rooms(self.staff) if r.get('direct')];self.assertEqual(len(rooms),1);self.assertEqual(rooms[0]['peer'],self.foreign['id']);self.assertFalse(self.s.chat_list(self.staff,'__shared_chat__',rooms[0]['room'])['items'])
            with self.assertRaises(DomainError):self.s.chat_list(self.other,'__shared_chat__',rooms[0]['room'])
            self.assertTrue(execute(owner,[action],context,client.request)[0]['ok']);self.assertEqual(len([r for r in self.s.chat_rooms(self.staff) if r.get('direct')]),1)
            other=collect(capture(owner),'آیا چت شخصی با foreign وجود دارد؟')
            with self.assertRaises(ValueError):normalize_action({'type':'chat_direct_create','changes':{'person_id':self.foreign['id']}},other)
            with self.assertRaises(ValueError):normalize_action({'type':'chat_direct_create','changes':{'person_id':self.other['id']}},context)
            self.s.save_permissions(self.admin,self.staff['id'],'mana',{'module.chat.direct':False})
            self.assertFalse(execute(owner,[action],context,client.request)[0]['ok'])
        finally:client.logout();client.session.close();server.close()
    def test_assistant_does_not_confuse_a_name_with_a_longer_name(self):
        from ai_app_actions import capture,collect,normalize_action
        from test_ai_app_actions import owner_for
        short=self.s.save_user(self.admin,dict(username='shortname',password='1',fullname='علی',memberships=[dict(company_id='mana',role='employee')]))['id']
        long=self.s.save_user(self.admin,dict(username='longname',password='1',fullname='علیزاده',memberships=[dict(company_id='mana',role='employee')]))['id']
        server=RunningServer(self.root/'company-server','127.0.0.1',0,background=False);client=Client('http://127.0.0.1:'+str(server.port))
        try:
            client.login('staff','1');context=collect(capture(owner_for(client.user,client)),'چت شخصی با علیزاده بساز')
            self.assertEqual([p['id'] for p in context['public'].get('direct_people',[])],[long])
            with self.assertRaises(ValueError):normalize_action({'type':'chat_direct_create','changes':{'person_id':short}},context)
            self.assertEqual(normalize_action({'type':'chat_direct_create','changes':{'person_id':long}},context)['changes']['person_id'],long)
        finally:client.logout();client.session.close();server.close()
    def test_assistant_archives_and_restores_only_the_named_manageable_group(self):
        from ai_app_actions import capture,collect,normalize_action,execute
        from test_ai_app_actions import owner_for
        scope='__shared_chat__';server=RunningServer(self.root/'company-server','127.0.0.1',0,background=False);client=Client('http://127.0.0.1:'+str(server.port));group=self.s.workspace_group_create(self.staff,scope,'پروژه نمونه',[self.other['id']]);self.s.chat_send(self.staff,scope,group['room'],'پیام آزمایشی')
        try:
            client.login('other','1');owner=owner_for(client.user,client);ctx=collect(capture(owner),'گروه پروژه نمونه را حذف کن');key=next(k for k,r in ctx['rooms'].items() if r['room']==group['room'])
            with self.assertRaises(ValueError):normalize_action({'type':'chat_group_archive','room_id':key},ctx)
            client.login('staff','1');owner=owner_for(client.user,client);ctx=collect(capture(owner),'گروه پروژه نمونه را حذف کن');key=next(k for k,r in ctx['rooms'].items() if r['room']==group['room']);action=normalize_action({'type':'chat_group_archive','room_id':key},ctx)
            self.assertTrue(execute(owner,[action],ctx,client.request)[0]['ok']);self.assertFalse(any(r['room']==group['room'] for r in self.s.chat_rooms(self.staff)))
            restored_ctx=collect(capture(owner),'گروه پروژه نمونه را بازیابی کن');target=restored_ctx['public']['deleted_groups'][0]['id'];restore=normalize_action({'type':'chat_group_restore','target':target},restored_ctx)
            self.assertTrue(execute(owner,[restore],restored_ctx,client.request)[0]['ok']);self.assertEqual(self.s.chat_list(self.staff,scope,group['room'])['items'][0]['text'],'پیام آزمایشی')
            no=collect(capture(owner),'گروه پروژه نمونه را حذف نکن');key=next(k for k,r in no['rooms'].items() if r['room']==group['room'])
            with self.assertRaises(ValueError):normalize_action({'type':'chat_group_archive','room_id':key},no)
            question=collect(capture(owner),'آیا گروه پروژه نمونه حذف شده؟');key=next(k for k,r in question['rooms'].items() if r['room']==group['room'])
            with self.assertRaises(ValueError):normalize_action({'type':'chat_group_archive','room_id':key},question)
        finally:client.logout();client.session.close();server.close()
    def test_assistant_never_archives_an_ambiguous_group_name(self):
        from ai_app_actions import capture,collect,normalize_action
        from test_ai_app_actions import owner_for
        scope='__shared_chat__';server=RunningServer(self.root/'company-server','127.0.0.1',0,background=False);client=Client('http://127.0.0.1:'+str(server.port))
        try:
            a=self.s.workspace_group_create(self.staff,scope,'گروه نمونه',[])['room'];b=self.s.workspace_group_create(self.staff,scope,'گروه نمونه',[])['room'];client.login('staff','1');context=collect(capture(owner_for(client.user,client)),'گروه گروه نمونه را حذف کن');key=next(k for k,r in context['rooms'].items() if r['room']==a)
            with self.assertRaises(ValueError):normalize_action({'type':'chat_group_archive','room_id':key},context)
            self.assertTrue({a,b}<={r['room'] for r in self.s.chat_rooms(self.staff)})
        finally:client.logout();client.session.close();server.close()
    def test_creator_can_restore_own_archived_group_and_purge_empty_group(self):
        scope='__shared_chat__';group=self.s.workspace_group_create(self.staff,scope,'گروه کاری',[self.other['id']]);room=group['room']
        self.s.workspace_hide_room(self.staff,scope,room)
        self.assertTrue(any(item['id']==room for item in self.s.workspace_trash(self.staff)))
        self.assertFalse(any(item['id']==room for item in self.s.workspace_trash(self.other)))
        with self.assertRaises(DomainError):self.s.workspace_restore_group(self.other,scope,room)
        self.s.workspace_trash(self.staff,'group',room,1,restore=True,company=scope)
        self.assertTrue(any(item['room']==room for item in self.s.chat_rooms(self.staff)))
        due=datetime.now(timezone.utc)+timedelta(minutes=5);self.s.chat_schedule(self.staff,scope,room,'پیام',due.isoformat(),uuid.uuid4().hex)
        self.s.workspace_hide_room(self.staff,scope,room);self.s.workspace_trash(self.staff,'group',room,1,purge=True,company=scope)
        with self.s.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM chat_scheduled WHERE room=?',(room,)).fetchone()[0],0)
        self.assertFalse(any(item['id']==room for item in self.s.workspace_trash(self.staff)))
    def test_scheduled_group_file_is_delivered_once_and_rechecks_access(self):
        scope='__shared_chat__';room=self.s.workspace_group_create(self.staff,scope,'گروه',[self.other['id']])['room']
        due=datetime.now(timezone.utc)+timedelta(minutes=5);rid=uuid.uuid4().hex;file={'name':'sample.txt','data':base64.b64encode(b'test file').decode()}
        self.s.chat_schedule(self.staff,scope,room,'آینده',due.isoformat(),rid,attachments=[file])
        self.assertTrue(self.s.chat_schedule(self.staff,scope,room,'آینده',due.isoformat(),rid,attachments=[file])['duplicate'])
        self.assertEqual(self.s.process_scheduled_chat(due-timedelta(seconds=2)),0)
        self.assertEqual(self.s.process_scheduled_chat(due+timedelta(seconds=1)),1)
        self.assertEqual(self.s.process_scheduled_chat(due+timedelta(seconds=2)),0)
        message=self.s.chat_list(self.other,scope,room)['items'][0]
        self.assertEqual(base64.b64decode(self.s.chat_download(self.other,message['files'][0]['id'])['data']),b'test file')
        second=due+timedelta(minutes=5);self.s.chat_schedule(self.staff,scope,room,'نباید ارسال شود',second.isoformat(),uuid.uuid4().hex,attachments=[file])
        self.s.save_permissions(self.admin,self.staff['id'],'mana',{'module.chat.attach':False})
        self.assertEqual(self.s.process_scheduled_chat(second+timedelta(seconds=1)),0)
        self.assertEqual(self.s.chat_scheduled_list(self.s.user(self.staff['id']),scope,room)[0]['status'],'failed')
    def test_group_attachment_trash_restore_and_purge(self):
        scope='__shared_chat__';room=self.s.workspace_group_create(self.staff,scope,'گروه',[self.other['id']])['room']
        message=self.s.chat_send(self.staff,scope,room,text='پیوست',attachments=[{'name':'a.txt','data':base64.b64encode(b'private').decode()}]);fid=self.s.chat_list(self.staff,scope,room)['items'][0]['files'][0]['id'];path=self.s.files/(fid+'.bin')
        self.s.chat_action(self.staff,message['id'],'delete')
        with self.assertRaises(DomainError):self.s.workspace_trash(self.other,'message',message['id'],1,purge=True)
        self.s.workspace_trash(self.staff,'message',message['id'],1,restore=True);self.assertTrue(path.exists())
        self.s.chat_action(self.staff,message['id'],'delete');self.s.workspace_trash(self.staff,'message',message['id'],1,purge=True);self.assertFalse(path.exists())
    def test_permanent_group_purge_removes_messages_and_files_only_in_selected_group(self):
        scope='__shared_chat__';group=self.s.workspace_group_create(self.staff,scope,'گروه نخست',[self.other['id']])['room'];other_group=self.s.workspace_group_create(self.staff,scope,'گروه دوم',[self.other['id']])['room']
        attachment={'name':'example.txt','data':base64.b64encode(b'data').decode()}
        message=self.s.chat_send(self.staff,scope,group,'پیام',attachments=[attachment]);self.s.chat_send(self.staff,scope,other_group,'باقی می‌ماند',attachments=[attachment])
        first=self.s.chat_list(self.staff,scope,group)['items'][0]['files'][0]['id'];second=self.s.chat_list(self.staff,scope,other_group)['items'][0]['files'][0]['id']
        self.s.chat_action(self.staff,message['id'],'save');self.s.chat_action(self.other,message['id'],'like');self.s.workspace_hide_room(self.staff,scope,group)
        with self.assertRaises(DomainError):self.s.workspace_trash(self.other,'group',group,1,purge=True,company=scope)
        self.s.workspace_trash(self.staff,'group',group,1,purge=True,company=scope)
        self.assertFalse((self.s.files/(first+'.bin')).exists());self.assertTrue((self.s.files/(second+'.bin')).exists())
        self.assertEqual(self.s.chat_list(self.staff,scope,other_group)['items'][0]['text'],'باقی می‌ماند')
        with self.s.db() as c:self.assertFalse(c.execute('SELECT 1 FROM chat_messages WHERE id=?',(message['id'],)).fetchone())
    def test_blank_rooms_and_any_employee_can_create_group(self):
        scope='__shared_chat__'
        self.assertEqual(self.s.chat_rooms(self.staff),[])
        room=self.s.workspace_group_create(self.staff,scope,'تیم پروژه',[self.foreign['id']])
        message=self.s.chat_send(self.staff,scope,room['room'],text='سلام')
        self.assertEqual(self.s.chat_list(self.foreign,scope,room['room'])['items'][0]['id'],message['id'])
        with self.assertRaises(DomainError):self.s.chat_list(self.other,scope,room['room'])
        with self.assertRaises(DomainError):self.s.chat_list(self.admin,scope,room['room'])
        self.assertEqual(self.s.chat_rooms(self.other),[])
        self.s.workspace_hide_room(self.staff,scope,room['room'])
        with self.assertRaises(DomainError):self.s.chat_list(self.foreign,scope,room['room'])
    def test_direct_conversation_and_task_are_private(self):
        scope='__shared_chat__';room=self.s.workspace_direct(self.staff,scope,self.foreign['id'])
        self.assertEqual(room['display_title'],self.foreign['fullname'])
        message=self.s.chat_send(self.staff,scope,room['room'],text='پیگیری پرونده')
        self.assertEqual(self.s.chat_list(self.foreign,scope,room['room'])['items'][0]['id'],message['id'])
        with self.assertRaises(DomainError):self.s.chat_list(self.admin,scope,room['room'])
        task=self.s.workspace_task_from_message(self.staff,message['id'],{'title':'پیگیری','company_id':'mana','due_date':'1405/08/12'})
        self.assertEqual(task['company_id'],'mana');self.assertEqual(task['payload']['source_message'],message['id'])
        with self.assertRaises(DomainError):self.s.workspace_task_from_message(self.staff,message['id'],{'title':'پیگیری','company_id':'arka','due_date':'1405/08/12'})
    def test_server_reset_removes_old_messages_files_and_groups_only_once(self):
        scope='__shared_chat__';room=self.s.workspace_group_create(self.staff,scope,'گروه قبلی',[self.other['id']])
        self.s.chat_send(self.staff,scope,room['room'],text='قدیمی',attachments=[{'name':'a.txt','data':base64.b64encode(b'old').decode()}])
        file_id=self.s.chat_list(self.staff,scope,room['room'])['items'][0]['files'][0]['id'];file_path=self.s.files/(file_id+'.bin')
        old_id=uuid.uuid4().hex;old_file=uuid.uuid4().hex;old_path=self.s.files/(old_file+'.bin');old_path.write_bytes(b'legacy')
        with self.s.db(True) as c:
            c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('chat_reset_v9_empty','1')")
            c.execute('INSERT INTO chat_messages(id,company_id,room,author,kind,text,payload,created) VALUES(?,?,?,?,?,?,?,?)',(old_id,'mana','general',self.staff['id'],'text','قدیمی','{}','2026-01-01'))
            c.execute('INSERT INTO chat_files VALUES(?,?,?,?,?,?)',(old_file,old_id,'old.txt','text/plain',6,'hash'))
        note=self.s.desk_note_save(self.staff,{'title':'یادداشت','body':'باقی بماند'})
        server=RunningServer(self.root/'company-server','127.0.0.1',0,background=False)
        client=Client('http://127.0.0.1:'+str(server.port))
        try:
            client.login('staff','1');self.assertEqual(client.request('chat/rooms'),[]);self.assertFalse(file_path.exists());self.assertFalse(old_path.exists())
            self.assertTrue(any(n['id']==note['id'] for n in server.store.desk_snapshot(server.store.user(self.staff['id']))['notes']))
            new=client.request('workspace/group',{'company':scope,'title':'گروه تازه','members':[self.other['id']]})
            client.request('chat/messages',{'company':scope,'room':new['room'],'text':'پیام تازه'})
            from ai_app_actions import collect,normalize_action
            snapshot=dict(actor=client.user,events=[],event_trash=[],overrides={},settings={},pages=[],client=client)
            context=collect(snapshot,'به گروه تازه پیام بفرست سلام');room_id=next(key for key,value in context['rooms'].items() if value['room']==new['room'])
            action=normalize_action({'type':'message_send','room_id':room_id,'changes':{'text':'سلام'}},context)
            self.assertEqual(action['room_id'],room_id)
        finally:client.logout();client.session.close();server.close()
        restarted=RunningServer(self.root/'company-server','127.0.0.1',0,background=False)
        try:self.assertEqual(restarted.store.chat_list(self.staff,scope,new['room'])['items'][0]['text'],'پیام تازه')
        finally:restarted.close()
    def test_deliberate_backup_restore_does_not_reset_restored_chat_again(self):
        from backup_bundle import create_bundle
        from server_restore import restore_closed_server
        from unittest.mock import patch
        scope='__shared_chat__';room=self.s.workspace_group_create(self.staff,scope,'گروه پشتیبان',[self.other['id']])['room'];self.s.chat_send(self.staff,scope,room,'پیام بازیابی‌شده',attachments=[{'name':'saved.txt','data':base64.b64encode(b'backup attachment').decode()}])
        fid=self.s.chat_list(self.staff,scope,room)['items'][0]['files'][0]['id'];snapshot=self.root/'before-reset.sqlite';self.s.backup_database(snapshot);archive=self.root/'before-reset.karname';create_bundle(archive,{'events':[],'settings':{}},{'server/company.sqlite':snapshot.read_bytes(),'server/files/'+fid+'.bin':(self.s.files/(fid+'.bin')).read_bytes()})
        self.s.reset_chat_once();self.assertEqual(self.s.chat_rooms(self.staff),[])
        with patch('network_tools.stop_autohost'):restore_closed_server(self.root,archive)
        restored=RunningServer(self.root/'company-server','127.0.0.1',0,background=False)
        try:
            actor=restored.store.user(self.staff['id']);message=restored.store.chat_list(actor,scope,room)['items'][0];self.assertEqual(message['text'],'پیام بازیابی‌شده');self.assertEqual(base64.b64decode(restored.store.chat_download(actor,message['files'][0]['id'])['data']),b'backup attachment')
        finally:restored.close()

