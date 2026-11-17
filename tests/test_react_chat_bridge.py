import unittest
from react_chat_bridge import request_for

class BridgePolicyTests(unittest.TestCase):
    def test_allowlisted_chat_requests(self):
        self.assertEqual(request_for('messages', {'company':'x','room':'y'})[:2], ('chat/messages', False))
        self.assertEqual(request_for('send', {'company':'x','room':'y','text':'سلام'})[:2], ('chat/messages', True))
    def test_unrelated_or_extra_requests_are_rejected(self):
        with self.assertRaises(ValueError):request_for('finance', {})
        with self.assertRaises(ValueError):request_for('messages', {'token':'secret'})
        with self.assertRaises(ValueError):request_for('message_action', {'id':'x','action':'unknown'})

class BridgeIntegrationTests(unittest.TestCase):
    def test_real_server_permissions_and_idempotent_send(self):
        import tempfile,time,json,uuid
        from pathlib import Path
        from PySide6.QtWidgets import QApplication
        from unittest.mock import patch
        from org_store import Store
        from org_http import RunningServer
        from org_client import Client
        from react_chat_bridge import ReactChatBridge
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp));admin=store.bootstrap('admin','1','مدیر');staff=store.save_user(admin,dict(username='staff',password='1',fullname='کارمند',memberships=[dict(company_id='mana',role='employee')]));outsider=store.save_user(admin,dict(username='other',password='1',fullname='دیگری',memberships=[dict(company_id='mana',role='employee')]))
            server=RunningServer(Path(tmp),'127.0.0.1',0);room=server.store.workspace_group_create(admin,'__shared_chat__','گروه',[staff['id']])['room']
            try:
                client=Client('http://127.0.0.1:'+str(server.port));client.login('staff','1');bridge=ReactChatBridge(lambda:client);results={};bridge.completed.connect(lambda key,raw:results.update({key:json.loads(raw)}))
                def call(key,action,payload):
                    bridge.request(key,action,json.dumps(payload));end=time.time()+10
                    while key not in results and time.time()<end:app.processEvents();time.sleep(.01)
                    self.assertIn(key,results);return results[key]
                identity=call('identity','identity',{});self.assertTrue(identity['ok']);self.assertEqual(identity['value']['id'],staff['id']);self.assertNotIn('token',identity['value'])
                companies=call('companies','companies',{});self.assertTrue(companies['ok'],companies);self.assertTrue(all(set(company)=={'id','name'} for company in companies['value']))
                self.assertFalse(call('identity-extra','identity',{'token':'x'})['ok'])
                saved=call('saved-chat-create','saved_chat',{});saved_again=call('saved-chat-again','saved_chat',{})
                self.assertTrue(saved['ok'],saved);self.assertEqual(saved['value']['room'],saved_again['value']['room']);self.assertEqual(saved['value']['room'],'saved:'+staff['id'])
                with patch('storage.app_dir',return_value=Path(tmp)),patch('chat_delivery.load',return_value={'drafts':{},'outbox':[]}),patch('chat_delivery.save'):
                    base={'company':'__shared_chat__','room':room,'files':[],'reply_to':None}
                    newest=call('draft-new','draft_save',dict(base,text='جدید',version=20));self.assertTrue(newest['value']['saved'])
                    stale=call('draft-old','draft_save',dict(base,text='قدیمی',version=10));self.assertFalse(stale['value']['saved'])
                    loaded=call('draft-get','draft_get',{'company':'__shared_chat__','room':room});self.assertEqual(loaded['value']['text'],'جدید')
                    payload={'company':'__shared_chat__','room':room,'text':'جدید','request_id':uuid.uuid4().hex}
                    envelope={'payload':payload,'draft_version':21}
                    queued=call('queue-new','queue_enqueue',envelope);self.assertTrue(queued['ok'],queued)
                    stale=call('draft-after-send','draft_save',dict(base,text='قدیمی',version=19));self.assertFalse(stale['value']['saved'])
                    loaded=call('draft-after-queue','draft_get',{'company':'__shared_chat__','room':room});self.assertFalse(loaded['value'].get('text'))
                    again=call('queue-again','queue_enqueue',envelope);self.assertEqual(again['value']['id'],queued['value']['id'])
                    changed={'payload':dict(payload,text='متن دیگر'),'draft_version':22}
                    self.assertFalse(call('queue-conflict','queue_enqueue',changed)['ok'])
                from PySide6.QtWidgets import QDialog
                with patch('chat_ui.ScheduleDialog') as chooser:
                    chooser.return_value.exec.return_value=QDialog.Accepted;chooser.return_value.due_at='2030-01-01T10:00:00+03:30'
                    choice=call('choose','choose_schedule',{});self.assertEqual(choice['value']['due_at'],'2030-01-01T10:00:00+03:30')
                with patch('chat_ui.MessageDialog') as chooser:
                    chooser.return_value.exec.return_value=QDialog.Accepted;chooser.return_value.title.text.return_value='پرسش';chooser.return_value.payload={'options':['آری','خیر']}
                    choice=call('choose-poll','choose_poll',{});self.assertEqual(choice['value']['payload']['options'],['آری','خیر']);chooser.assert_called_with('poll')
                body={'company':'__shared_chat__','room':room,'text':'پیام نمونه','request_id':str(uuid.uuid4())}
                first=call('a','send',body);self.assertTrue(first['ok'],first);self.assertTrue(call('b','send',body)['ok']);data=call('c','messages',{'company':'__shared_chat__','room':room})
                self.assertTrue(data['ok']);self.assertEqual(len(data['value']['items']),1)
                message_id=data['value']['items'][0]['id']
                opened=[];bridge.native_reminder=lambda message:opened.append(message)
                reminder=call('reminder-open','native_reminder',{'company':'__shared_chat__','room':room,'id':message_id});self.assertTrue(reminder['ok'],reminder);self.assertEqual(opened[0]['text'],'پیام نمونه')
                tasks=[];bridge.native_task=lambda message:tasks.append(message)
                task=call('task-open','native_task',{'company':'__shared_chat__','room':room,'id':message_id});self.assertTrue(task['ok'],task);self.assertEqual(tasks[0]['text'],'پیام نمونه')
                self.assertTrue(call('save-message','message_action',{'id':message_id,'action':'save'})['ok'])
                self.assertEqual(len(call('saved-filter','messages',{'company':'__shared_chat__','room':room,'saved':'1'})['value']['items']),1)
                self.assertFalse(call('pin-denied','message_action',{'id':message_id,'action':'pin'})['ok'])
                pin_admin=Client('http://127.0.0.1:'+str(server.port));pin_admin.login('admin','1');pin_admin.request('chat/action',{'id':message_id,'action':'pin'});pin_admin.logout()
                self.assertEqual(len(call('pinned-filter','messages',{'company':'__shared_chat__','room':room,'pinned':'1'})['value']['items']),1)
                found=call('search-match','messages',{'company':'__shared_chat__','room':room,'q':'نمونه'});self.assertTrue(found['ok']);self.assertEqual(len(found['value']['items']),1)
                missing=call('search-missing','messages',{'company':'__shared_chat__','room':room,'q':'ناموجود'});self.assertTrue(missing['ok']);self.assertEqual(len(missing['value']['items']),0)
                response=call('thread-reply','send',{'company':'__shared_chat__','room':room,'text':'پاسخ بحث','reply_to':message_id,'request_id':uuid.uuid4().hex});self.assertTrue(response['ok'],response)
                discussion=call('thread-list','messages',{'company':'__shared_chat__','room':room,'thread':message_id});self.assertTrue(discussion['ok'],discussion);self.assertEqual(len(discussion['value']['items']),2)
                mention=call('mention','send',{'company':'__shared_chat__','room':room,'text':'@admin لطفاً بررسی کنید','request_id':uuid.uuid4().hex});self.assertTrue(mention['ok'],mention)
                mentioned=call('mention-list','messages',{'company':'__shared_chat__','room':room,'q':'لطفاً بررسی'});self.assertEqual(mentioned['value']['items'][0]['mentions'],[admin['id']])
                import base64
                attachment={'company':'__shared_chat__','room':room,'text':'','attachments':[{'name':'sample.txt','data':base64.b64encode(b'test').decode()}],'request_id':str(uuid.uuid4())}
                sent=call('file-send','send',attachment);self.assertTrue(sent['ok'],sent);with_files=call('file-list','messages',{'company':'__shared_chat__','room':room});file=with_files['value']['items'][-1]['files'][0];self.assertEqual(file['name'],'sample.txt');download=call('file-get','file',{'id':file['id']});self.assertTrue(download['ok'],download);self.assertEqual(base64.b64decode(download['value']['data']),b'test')
                from datetime import datetime,timezone,timedelta
                schedule={'company':'__shared_chat__','room':room,'text':'پیام آینده','due_at':(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),'request_id':uuid.uuid4().hex}
                first_schedule=call('schedule1','schedule',schedule);again_schedule=call('schedule2','schedule',schedule);self.assertTrue(first_schedule['ok'],first_schedule);self.assertEqual(first_schedule['value']['id'],again_schedule['value']['id']);listed=call('schedule-list','scheduled',{'company':'__shared_chat__','room':room});self.assertEqual(len(listed['value']),1);self.assertTrue(call('schedule-cancel','schedule_cancel',{'id':first_schedule['value']['id'],'expected_due_at':listed['value'][0]['due_at']})['ok'])
                poll=call('poll','send',{'company':'__shared_chat__','room':room,'text':'سوال','kind':'poll','payload':{'options':['آری','خیر']},'request_id':str(uuid.uuid4())});self.assertTrue(poll['ok'],poll);vote=call('vote','message_action',{'id':poll['value']['id'],'action':'vote','option':0});self.assertTrue(vote['ok'],vote)
                meeting=call('meeting','send',{'company':'__shared_chat__','room':room,'text':'جلسه نمونه','kind':'meeting','payload':{'at':(datetime.now(timezone.utc)+timedelta(hours=3)).isoformat(),'location':'دفتر'},'request_id':str(uuid.uuid4())});self.assertTrue(meeting['ok'],meeting)
                for index in range(55):
                    client.request('chat/messages',{'company':'__shared_chat__','room':room,'text':f'پیام تاریخچه {index}','request_id':uuid.uuid4().hex})
                latest=call('history-latest','messages',{'company':'__shared_chat__','room':room});self.assertTrue(latest['ok'],latest);self.assertTrue(latest['value']['has_more'])
                old=call('history-older','messages',{'company':'__shared_chat__','room':room,'before':latest['value']['items'][0]['seq']});self.assertTrue(old['ok'],old)
                self.assertTrue(old['value']['items']);self.assertLess(old['value']['items'][-1]['seq'],latest['value']['items'][0]['seq'])
                self.assertFalse(set(x['id'] for x in old['value']['items']) & set(x['id'] for x in latest['value']['items']))
                sender=Client('http://127.0.0.1:'+str(server.port));sender.login('admin','1')
                sender.request('chat/messages',{'company':'__shared_chat__','room':room,'text':'پیام خوانده نشده','request_id':uuid.uuid4().hex})
                sender.logout()
                rooms_before=call('rooms-unread','rooms',{});self.assertTrue(rooms_before['ok'],rooms_before)
                found_room=next(r for r in rooms_before['value'] if r['room']==room and r['company']=='__shared_chat__');self.assertGreater(found_room['unread'],0)
                last=call('read-last','messages',{'company':'__shared_chat__','room':room})['value']['items'][-1]['seq']
                marked=call('read-mark','state',{'company':'__shared_chat__','room':room,'seq':last});self.assertTrue(marked['ok'],marked)
                rooms_after=call('rooms-read','rooms',{});found_room=next(r for r in rooms_after['value'] if r['room']==room and r['company']=='__shared_chat__');self.assertEqual(found_room['unread'],0)
                self.assertTrue(call('mute','state',{'company':'__shared_chat__','room':room,'muted':True})['ok'])
                muted=call('rooms-muted','rooms',{});self.assertTrue(next(r for r in muted['value'] if r['room']==room)['muted'])
                bridge.close();client.logout();other=Client('http://127.0.0.1:'+str(server.port));other.login('other','1');bridge=ReactChatBridge(lambda:other);bridge.completed.connect(lambda key,raw:results.update({key:json.loads(raw)}))
                bridge.native_task=lambda message: self.fail('unauthorized message reached task handler')
                self.assertFalse(call('task-denied','native_task',{'company':'__shared_chat__','room':room,'id':message_id})['ok'])
                denied=call('d','messages',{'company':'__shared_chat__','room':room});self.assertFalse(denied['ok']);self.assertFalse(call('file-denied','file',{'id':file['id']})['ok']);self.assertFalse(call('delete-denied','message_action',{'id':sent['value']['id'],'action':'delete'})['ok']);bridge.close();other.logout()
                creator=Client('http://127.0.0.1:'+str(server.port));creator.login('admin','1');bridge=ReactChatBridge(lambda:creator);bridge.completed.connect(lambda key,raw:results.update({key:json.loads(raw)}))
                group={'company':'__shared_chat__','title':'گروه تازه','members':[staff['id']],'request_id':uuid.uuid4().hex}
                made=call('e','group',group);again=call('f','group',group);self.assertTrue(made['ok'],made);self.assertTrue(again['ok'],again);self.assertEqual(made['value']['room'],again['value']['room']);self.assertTrue(call('hide-group','hide_room',{'company':'__shared_chat__','room':made['value']['room']})['ok']);self.assertFalse(any(r['room']==made['value']['room'] for r in call('rooms-after-hide','rooms',{})['value']));bridge.close();creator.logout()
            finally:server.close()
