import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from company_defaults import migrate_company_defaults
from planning import kind_for
from ai_app_actions import normalize_action, apply_one

class CompanyMigrationTests(unittest.TestCase):
    def test_preserves_personal_and_archives_only_builtin_arka(self):
        seed=json.loads((Path(__file__).resolve().parents[1]/'data/initial_events.json').read_text(encoding='utf-8'))
        custom=dict(id='custom',company='آرکا',title='یادآور شخصی',date_jalali='1405/08/01')
        seed['events'].append(custom);original=copy.deepcopy(seed)
        migrate_company_defaults(seed)
        self.assertEqual(seed['companies'][:3],['مانا','آیریا','آرکا'])
        self.assertIn(custom,seed['events'])
        self.assertTrue(all(kind_for(e) in ('vat','books') for e in seed['events'] if e['company']=='آرکا' and e.get('created_from_excel')))
        airia=[e for e in seed['events'] if e['company']=='آیریا']
        self.assertEqual(len(airia),sum(bool(kind_for(e)) and kind_for(e)!='rent' for e in original['events'] if e['company']=='آرکا' and e.get('created_from_excel')))
        self.assertTrue(all(kind_for(e)!='rent' for e in airia))
        self.assertTrue(seed['company_defaults_archive'])

class AssistantMessageTests(unittest.TestCase):
    def test_only_reviewed_room_is_sent(self):
        ctx={'actor':None,'rooms':{'r':{'company':'mana','room':'general','title':'مانا · عمومی','company_name':'مانا','room_name':'عمومی'}},'query':'ارسال پیام سلام به گروه عمومی شرکت مانا','public':{'pages':[]}}
        action=normalize_action({'type':'message_send','room_id':'r','changes':{'text':'سلام'}},ctx)
        class Owner:pass
        owner=Owner();owner.org=Owner();owner.org.client=object();calls=[]
        def request(path,payload=None,**kwargs):
            calls.append((path,payload))
            return [{'company':'mana','room':'general'}] if path=='chat/rooms' else {}
        self.assertIn('ارسال شد',apply_one(owner,action,ctx,None,request))
        self.assertEqual(calls[-1][1]['text'],'سلام')
        with self.assertRaises(ValueError):normalize_action({'type':'message_send','room_id':'other','changes':{'text':'سلام'}},ctx)
        with self.assertRaises(ValueError):normalize_action({'type':'message_send','room_id':'r','changes':{'text':'پیام ساختگی'}},ctx)
        wrong=copy.deepcopy(ctx);wrong['query']='ارسال پیام سلام به گروه مدیران شرکت مانا'
        with self.assertRaises(ValueError):normalize_action({'type':'message_send','room_id':'r','changes':{'text':'سلام'}},wrong)
        with self.assertRaises(PermissionError):apply_one(owner,action,ctx,None,lambda *a,**k:[])
    def test_real_server_deduplicates_retries(self):
        from org_http import RunningServer
        from org_client import Client
        from ai_app_actions import collect,execute
        with tempfile.TemporaryDirectory() as folder:
            server=RunningServer(folder,'127.0.0.1',0)
            try:
                server.store.bootstrap('admin','password','مدیر')
                client=Client('http://127.0.0.1:'+str(server.port));actor=client.login('admin','password')
                scope='__shared_chat__';room=server.store.workspace_group_create(actor,scope,'مشترک',[])['room']
                snapshot=dict(actor=actor,events=[],overrides={},settings={},pages=[],client=client)
                ctx=collect(snapshot,'ارسال پیام آزمایش به گروه مشترک شرکت مانا',True)
                key=next(k for k,r in ctx['rooms'].items() if r['company']==scope and r['room']==room)
                action=normalize_action({'type':'message_send','room_id':key,'changes':{'text':'آزمایش'}},ctx)
                class Obj:pass
                owner=Obj();owner.session_user=actor;owner.org=Obj();owner.org.client=client
                request=lambda path,payload=None,**query:client.request(path,payload,**query)
                self.assertTrue(execute(owner,[action],ctx,request)[0]['ok']);self.assertTrue(execute(owner,[action],ctx,request)[0]['ok'])
                self.assertEqual(len([m for m in server.store.chat_list(actor,scope,room)['items'] if m['text']=='آزمایش']),1)
            finally:server.close()

class CustomerNumberTests(unittest.TestCase):
    def test_numbers_start_at_100_and_are_not_reused_after_delete(self):
        from org_store import Store
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder);admin=store.bootstrap('admin','password','مدیر')
            first=store.save_record(admin,'client',{'title':'الف'},'mana')
            second=store.save_record(admin,'client',{'title':'ب'},'mana')
            self.assertEqual(first['payload']['customer_code'],'100');self.assertEqual(second['payload']['customer_code'],'101')
            store.delete_record(admin,second['id'],second['version'])
            third=store.save_record(admin,'client',{'title':'پ'},'mana');self.assertEqual(third['payload']['customer_code'],'102')

if __name__=='__main__':unittest.main()
