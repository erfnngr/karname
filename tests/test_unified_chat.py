import unittest
import test_v8 as fixtures
from org_store import DomainError

class UnifiedChatTests(unittest.TestCase):
    seed_chat=False
    setUp=fixtures.WorkspaceTests.setUp
    tearDown=fixtures.WorkspaceTests.tearDown
    make=fixtures.WorkspaceTests.make

    def test_no_default_rooms_and_cross_company_private_access(self):
        scope='__shared_chat__';self.assertEqual([r['room'] for r in self.s.chat_rooms(self.staff)],['saved:'+self.staff['id']])
        direct=self.s.workspace_direct(self.staff,scope,self.foreign['id']);self.assertEqual(direct['display_title'],self.foreign['fullname'])
        private=self.s.chat_send(self.staff,scope,direct['room'],text='خصوصی')
        self.assertEqual(self.s.chat_list(self.foreign,scope,direct['room'])['items'][-1]['id'],private['id'])
        with self.assertRaises(DomainError):self.s.chat_list(self.manager,scope,direct['room'])
        self.assertFalse(any(c['id']==scope for c in self.s.companies(self.admin)))
    def test_new_shared_group_has_only_selected_members(self):
        scope='__shared_chat__';room=self.s.workspace_group_create(self.staff,scope,'همکاری',[self.foreign['id']])['room']
        self.s.chat_send(self.staff,scope,room,text='سلام')
        self.assertEqual(self.s.chat_list(self.foreign,scope,room)['items'][0]['text'],'سلام')
        with self.assertRaises(DomainError):self.s.chat_list(self.other,scope,room)
        self.assertTrue(any(x['room']==room for x in self.s.chat_rooms(self.foreign)))
    def test_shared_message_can_become_task_in_authorized_company(self):
        scope='__shared_chat__';room=self.s.workspace_group_create(self.staff,scope,'کار',[self.other['id']])['room'];sent=self.s.chat_send(self.staff,scope,room,text='پیگیری پرونده')
        with self.assertRaises(DomainError):self.s.workspace_task_from_message(self.staff,sent['id'],{'title':'پیگیری'})
        result=self.s.workspace_task_from_message(self.staff,sent['id'],{'title':'پیگیری','company_id':'mana','due_date':'1405/08/12'})
        self.assertEqual(result['company_id'],'mana');self.assertEqual(result['payload']['source_message'],sent['id'])
        with self.assertRaises(DomainError):self.s.workspace_task_from_message(self.staff,sent['id'],{'title':'پیگیری','company_id':'arka','due_date':'1405/08/12'})
    def test_shared_rooms_and_assistant_over_real_http(self):
        from org_http import RunningServer
        from org_client import Client
        from ai_app_actions import collect,normalize_action
        server=RunningServer(self.root/'company-server','127.0.0.1',0);client=Client('http://127.0.0.1:'+str(server.port))
        try:
            client.login('staff','1');self.assertEqual([r['room'] for r in client.request('chat/rooms')],['saved:'+self.staff['id']])
            group=client.request('workspace/group',{'company':'__shared_chat__','title':'تیم پروژه','members':[self.foreign['id']]})
            sent=client.request('chat/messages',{'company':'__shared_chat__','room':group['room'],'text':'سلام'});self.assertTrue(sent['id'])
            snapshot=dict(actor=client.user,events=[],event_trash=[],overrides={},settings={},pages=[],client=client)
            context=collect(snapshot,'به تیم پروژه پیام بفرست سلام');room_id=next(key for key,room in context['rooms'].items() if room['room']==group['room'])
            action=normalize_action({'type':'message_send','room_id':room_id,'changes':{'text':'سلام'}},context);self.assertEqual(action['room_id'],room_id)
        finally:client.logout();client.session.close();server.close()

    def test_assistant_distinguishes_saved_direct_and_group_and_sends_privately(self):
        from org_http import RunningServer
        from org_client import Client
        from ai_app_actions import capture,collect,normalize_action,execute
        from test_ai_app_actions import owner_for
        server=RunningServer(self.root/'company-server','127.0.0.1',0);client=Client('http://127.0.0.1:'+str(server.port))
        try:
            client.login('staff','1');scope='__shared_chat__'
            group=client.request('workspace/group',{'company':scope,'title':'پروژه آزمون','members':[self.foreign['id']]})
            direct=client.request('workspace/direct',{'company':scope,'person':self.foreign['id']})
            owner=owner_for(client.user,client);query='به پیام های ذخیره شده پیام بده یادداشت نمونه'
            context=collect(capture(owner),query)
            expected={'saved:'+self.staff['id']:'saved',group['room']:'group',direct['room']:'private'}
            for room_id,room in context['rooms'].items():
                if room['room'] in expected:
                    self.assertEqual(next(item['kind'] for item in context['public']['rooms'] if item['id']==room_id),expected.pop(room['room']))
            self.assertFalse(expected)
            saved=next(key for key,room in context['rooms'].items() if room.get('saved'))
            action=normalize_action({'type':'message_send','room_id':saved,'changes':{'text':'یادداشت نمونه'}},context)
            result=execute(owner,[action],context,client.request)
            self.assertTrue(result[0]['ok'],str(result));self.assertEqual(self.s.chat_list(self.staff,scope,'saved:'+self.staff['id'])['items'][0]['text'],'یادداشت نمونه')
            with self.assertRaises(DomainError):self.s.chat_list(self.foreign,scope,'saved:'+self.staff['id'])
        finally:client.logout();client.session.close();server.close()

if __name__=='__main__':unittest.main()
