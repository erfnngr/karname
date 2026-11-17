import tempfile,unittest,uuid,time,base64
from datetime import datetime,timezone,timedelta
from pathlib import Path
from org_store import Store,DomainError

class ScheduledChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name));self.admin=self.store.bootstrap('admin','1','مدیر');self.staff_id=self.store.save_user(self.admin,dict(username='staff',password='1',fullname='همکار',memberships=[dict(company_id='mana',role='employee')]))['id'];self.staff=self.store.user(self.staff_id);self.store.reset_chat_once();self.scope='__shared_chat__';self.room=self.store.workspace_group_create(self.staff,self.scope,'گروه آزمون',[self.admin['id']])['room']
    def tearDown(self):self.tmp.cleanup()
    def schedule(self,actor=None,text='پیام نمونه'):
        self.due=datetime.now(timezone.utc)+timedelta(minutes=5);self.request_id=uuid.uuid4().hex;return self.store.chat_schedule(actor or self.staff,self.scope,self.room,text,self.due.isoformat(),self.request_id)
    def test_delivery_is_durable_idempotent_and_personal(self):
        item=self.schedule();retry=self.store.chat_schedule(self.staff,self.scope,self.room,'پیام نمونه',self.due.isoformat(),self.request_id);self.assertTrue(retry['duplicate']);self.assertEqual(item['id'],retry['id']);self.assertEqual(self.store.process_scheduled_chat(self.due-timedelta(seconds=2)),0);self.assertEqual(self.store.process_scheduled_chat(self.due+timedelta(seconds=1)),1);self.assertEqual(self.store.process_scheduled_chat(self.due+timedelta(seconds=2)),0);messages=self.store.chat_list(self.staff,self.scope,self.room)['items'];self.assertEqual(len(messages),1);self.assertEqual(messages[0]['author'],self.staff_id);self.assertEqual(messages[0]['text'],'پیام نمونه')
    def test_cancel_and_permission_revocation(self):
        item=self.schedule();self.assertEqual(len(self.store.chat_scheduled_list(self.staff,self.scope,self.room)),1);self.assertFalse(self.store.chat_scheduled_list(self.admin,self.scope,self.room))
        with self.assertRaises(DomainError):self.store.chat_scheduled_cancel(self.admin,item['id'])
        self.store.chat_scheduled_cancel(self.staff,item['id']);self.assertEqual(self.store.process_scheduled_chat(self.due+timedelta(seconds=1)),0)
        item=self.schedule();self.store.save_permissions(self.admin,self.staff_id,'mana',{'module.chat.send':False});self.assertEqual(self.store.process_scheduled_chat(self.due+timedelta(seconds=1)),0);self.assertEqual(self.store.chat_scheduled_list(self.staff,self.scope,self.room)[0]['status'],'failed')
    def test_reschedule_is_private_and_moves_delivery_time(self):
        item=self.schedule();original=self.due;later=original+timedelta(minutes=20)
        with self.assertRaises(DomainError):self.store.chat_scheduled_reschedule(self.admin,item['id'],later.isoformat())
        self.store.chat_scheduled_reschedule(self.staff,item['id'],later.isoformat());self.assertEqual(self.store.process_scheduled_chat(original+timedelta(seconds=1)),0);self.assertEqual(self.store.process_scheduled_chat(later+timedelta(seconds=1)),1)
        with self.assertRaises(DomainError):self.store.chat_scheduled_reschedule(self.staff,item['id'],(later+timedelta(hours=1)).isoformat())
    def test_expired_claim_recovers_without_duplicate(self):
        item=self.schedule();message=self.store.chat_send(self.staff,self.scope,self.room,text='پیام نمونه',request_id='scheduled-'+item['id'])
        with self.store.db(True) as c:c.execute("UPDATE chat_scheduled SET status='sending',lease_until=? WHERE id=?",((self.due-timedelta(seconds=1)).isoformat(timespec='seconds'),item['id']))
        self.assertEqual(self.store.process_scheduled_chat(self.due+timedelta(seconds=1)),1);self.assertEqual(len(self.store.chat_list(self.staff,self.scope,self.room)['items']),1)
    def test_host_background_worker_sends_without_client_polling(self):
        from org_http import RunningServer
        server=RunningServer(Path(self.tmp.name),'127.0.0.1',0)
        try:
            due=datetime.now(timezone.utc)+timedelta(seconds=2);self.store.chat_schedule(self.staff,self.scope,self.room,'خودکار',due.isoformat(),uuid.uuid4().hex);deadline=time.monotonic()+9
            while time.monotonic()<deadline:
                if self.store.chat_list(self.staff,self.scope,self.room)['items']:break
                time.sleep(.1)
            self.assertEqual(self.store.chat_list(self.staff,self.scope,self.room)['items'][0]['text'],'خودکار')
        finally:server.close()
    def test_host_database_backup_keeps_scheduled_messages(self):
        self.schedule();target=Path(self.tmp.name)/'restore';target.mkdir();self.store.backup_database(target/'company.sqlite');restored=Store(target);staff=restored.user(self.staff_id);self.assertEqual(restored.chat_scheduled_list(staff,self.scope,self.room)[0]['text'],'پیام نمونه');self.assertEqual(restored.process_scheduled_chat(self.due+timedelta(seconds=1)),1);self.assertEqual(len(restored.chat_list(staff,self.scope,self.room)['items']),1)
    def test_scheduled_attachment_is_preserved_and_sent_once(self):
        due=datetime.now(timezone.utc)+timedelta(minutes=5);request_id=uuid.uuid4().hex;file=dict(name='sample.pdf',data=base64.b64encode(b'example file').decode());item=self.store.chat_schedule(self.staff,self.scope,self.room,'',due.isoformat(),request_id,attachments=[file]);retry=self.store.chat_schedule(self.staff,self.scope,self.room,'',due.isoformat(),request_id,attachments=[file]);self.assertTrue(retry['duplicate']);listing=self.store.chat_scheduled_list(self.staff,self.scope,self.room);self.assertEqual(listing[0]['file_names'],['sample.pdf']);self.assertNotIn(file['data'],str(listing));self.assertFalse(self.store.chat_list(self.staff,self.scope,self.room)['items']);self.assertEqual(self.store.process_scheduled_chat(due+timedelta(seconds=1)),1);self.assertEqual(self.store.process_scheduled_chat(due+timedelta(seconds=2)),0);message=self.store.chat_list(self.staff,self.scope,self.room)['items'][0];self.assertEqual(base64.b64decode(self.store.chat_download(self.staff,message['files'][0]['id'])['data']),b'example file')
    def test_scheduled_attachment_rechecks_permission(self):
        due=datetime.now(timezone.utc)+timedelta(minutes=5);file=dict(name='a.txt',data=base64.b64encode(b'example').decode());self.store.chat_schedule(self.staff,self.scope,self.room,'پیام',due.isoformat(),uuid.uuid4().hex,attachments=[file]);self.store.save_permissions(self.admin,self.staff_id,'mana',{'module.chat.attach':False});self.assertEqual(self.store.process_scheduled_chat(due+timedelta(seconds=1)),0);self.assertEqual(self.store.chat_scheduled_list(self.staff,self.scope,self.room)[0]['status'],'failed');self.assertFalse(self.store.chat_list(self.staff,self.scope,self.room)['items'])
    def test_previous_scheduled_table_migrates_without_losing_entries(self):
        self.schedule()
        with self.store.db(True) as c:c.execute('ALTER TABLE chat_scheduled DROP COLUMN attachments')
        upgraded=Store(Path(self.tmp.name));self.assertEqual(upgraded.chat_scheduled_list(upgraded.user(self.staff_id),self.scope,self.room)[0]['text'],'پیام نمونه');self.assertEqual(upgraded.process_scheduled_chat(self.due+timedelta(seconds=1)),1)
    def test_restore_does_not_send_past_due_messages_automatically(self):
        from backup_bundle import create_bundle
        from server_restore import restore_closed_server
        from unittest.mock import patch
        old=self.schedule(text='قدیمی');new=self.schedule(text='آینده');past=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(timespec='seconds')
        with self.store.db(True) as c:c.execute('UPDATE chat_scheduled SET due_at=? WHERE id=?',(past,old['id']))
        snapshot=Path(self.tmp.name)/'snapshot.sqlite';self.store.backup_database(snapshot);archive=Path(self.tmp.name)/'backup.karname';create_bundle(archive,dict(events=[],settings={}),{'server/company.sqlite':snapshot.read_bytes()});root=Path(self.tmp.name)/'restored-host';root.mkdir()
        with patch('network_tools.stop_autohost'):restore_closed_server(root,archive)
        restored=Store(root/'company-server');staff=restored.user(self.staff_id);states={x['text']:x['status'] for x in restored.chat_scheduled_list(staff,self.scope,self.room)};self.assertEqual(states,{'قدیمی':'failed','آینده':'pending'});self.assertEqual(restored.process_scheduled_chat(),0)
