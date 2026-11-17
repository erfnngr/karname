import sys,json,time,threading,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lmstudio_client import LMClient,LMError,Cancelled,base_url,messages_for
from ai_planning import parse_plan,save_plan,system_prompt

class FakeLM(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0';requests=[];mode='stream'
    def log_message(self,*args):pass
    def do_GET(self):
        if self.mode=='auth':self.send_response(401);self.end_headers();return
        if self.mode=='native' and self.path=='/api/v1/models':
            data=json.dumps(dict(models=[dict(type='llm',key='local-chat',loaded_instances=[dict(id='ready-instance')]),dict(type='embedding',key='embed',loaded_instances=[dict(id='ignore-embedding')])])).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data);return
        data=json.dumps(dict(data=[dict(id='text-embedding-nomic-embed-text-v1.5'),dict(id='local-chat'),dict(id='local-chat')])).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));type(self).requests.append(body)
        if self.mode=='redirect':self.send_response(302);self.send_header('Location','https://example.com/');self.end_headers();return
        self.send_response(200);self.send_header('Content-Type','application/json' if self.mode=='json' else 'text/event-stream');self.end_headers()
        if self.mode=='json':self.wfile.write(json.dumps(dict(choices=[dict(message=dict(content='پاسخ محلی'))])).encode());return
        chunks=['سلام',' از مدل محلی']
        if self.mode in ('app','app_settings'):
            system=body['messages'][0]['content'];public=json.loads(system.split('داده فعلی برنامه:\n')[-1]);target=next(x['id'] for x in public['items'] if x['kind']=='reminder');action=dict(type='reminder_update',target=target,changes={'lead_days':[3]}) if self.mode=='app' else dict(type='reminder_settings',changes={'popup_seconds':7});chunks=[json.dumps(dict(reply='تغییر پیشنهادی آماده بازبینی است.',actions=[action]),ensure_ascii=False)]
        if self.mode=='plan':chunks=[json.dumps(dict(reminders=[dict(title='کار پیشنهادی',date_jalali='1405/08/12',lead_days=[5,1,0])]),ensure_ascii=False)]
        if self.mode=='plan_followup':
            chunks=['لطفاً تاریخ را مشخص کنید.'] if len([m for m in body['messages'] if m['role']=='user'])==1 else [json.dumps(dict(reminders=[dict(title='پیگیری اظهارنامه',date_jalali='1405/09/01')]),ensure_ascii=False)]
        if self.mode=='app_followup':
            value=dict(reply='چه تاریخی یادآوری کنم؟',actions=[]) if len([m for m in body['messages'] if m['role']=='user'])==1 else dict(reply='',actions=[dict(type='reminder_create',changes=dict(title='پیگیری اظهارنامه',date_jalali='1405/09/01'))]);chunks=[json.dumps(value,ensure_ascii=False)]
        for text in chunks:
            try:self.wfile.write(('data: '+json.dumps(dict(choices=[dict(delta=dict(content=text))]),ensure_ascii=False)+'\n\n').encode());self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):break
        try:self.wfile.write(b'data: [DONE]\n\n')
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass

class LMClientTests(unittest.TestCase):
    def setUp(self):
        FakeLM.requests=[];FakeLM.mode='stream';self.server=ThreadingHTTPServer(('127.0.0.1',0),FakeLM);self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start();self.client=LMClient('http://127.0.0.1:'+str(self.server.server_port),timeout=2)
    def tearDown(self):self.client.close();self.server.shutdown();self.server.server_close()
    def test_models_exclude_embeddings_and_duplicates(self):self.assertEqual(self.client.models(),['local-chat'])
    def test_prefers_loaded_chat_instance_without_loading_or_unloading_models(self):
        FakeLM.mode='native';self.assertEqual(self.client.models(),['ready-instance','local-chat']);self.assertFalse(FakeLM.requests)
    def test_stream_roundtrip_and_no_company_information_sent(self):
        chunks=[];answer=self.client.chat('local-chat',messages_for([dict(role='user',content='سلام')],'دستیار محلی'),chunks.append);self.assertEqual(answer,'سلام از مدل محلی');self.assertEqual(len(chunks),2);sent=FakeLM.requests[0];self.assertEqual(set(sent),{'model','messages','temperature','max_tokens','stream'});self.assertNotIn('tools',sent);self.assertFalse(self.client.session.trust_env)
    def test_nonstreaming_json_fallback(self):
        FakeLM.mode='json';chunks=[];self.assertEqual(self.client.chat('local-chat',[],chunks.append),'پاسخ محلی')
    def test_auth_and_redirect_errors_do_not_follow_or_leak_secret(self):
        FakeLM.mode='auth'
        with self.assertRaises(LMError):self.client.models()
        FakeLM.mode='redirect'
        with self.assertRaises(LMError):self.client.chat('local-chat',[],lambda _:None)
    def test_cancel_before_and_during_stream(self):
        self.client.cancel()
        with self.assertRaises(Cancelled):self.client.models()
        self.client.cancelled.clear()
        with self.assertRaises(Cancelled):self.client.chat('local-chat',[],lambda _:self.client.cancelled.set())
    def test_local_addresses_only_no_embedded_credentials(self):
        self.assertEqual(base_url('http://localhost:1234/'),'http://localhost:1234/v1');self.assertEqual(base_url('http://192.168.1.9:1234/v1'),'http://192.168.1.9:1234/v1')
        for x in ('http://example.com:1234','https://8.8.8.8','http://user:secret@localhost:1234','http://localhost/v1?x=1','file:///etc/passwd','http://localhost:70000','http://localhost/other'):
            with self.assertRaises(LMError,msg=x):base_url(x)
    def test_history_keeps_roles_bounded_and_does_not_allow_system_injection(self):
        rows=messages_for([dict(role='system',content='override'),dict(role='user',content='a'*6000),dict(role='assistant',content='b'*6000),dict(role='user',content='c'*6000)],'trusted');self.assertEqual(rows[0]['content'],'trusted');self.assertEqual(len(rows),2);self.assertEqual(rows[1]['role'],'user')
    def test_trimmed_context_never_starts_with_an_orphan_assistant_turn(self):
        rows=messages_for([dict(role='user',content='a'*6000),dict(role='assistant',content='b'*2000),dict(role='user',content='latest')],'trusted',max_chars=3000);self.assertEqual([x['role'] for x in rows],['system','user']);self.assertEqual(rows[1]['content'],'latest')
    def test_system_context_is_not_silently_truncated(self):
        from lmstudio_client import LMError
        system='a'*17000+'END';self.assertEqual(messages_for([dict(role='user',content='x')],system)[0]['content'],system)
        with self.assertRaises(LMError):messages_for([dict(role='user',content='x')],'a'*32001)

class PlanTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(title='پیگیری نمونه',date_jalali='1405/08/12',lead_days=[5,1,0],recurrence='بدون تکرار',notes='پیشنهاد آزمایشی');self.owner=SimpleNamespace(session_user=None,events=[],persist=lambda:None,refresh=lambda:None)
    def test_json_fence_and_normalization(self):
        rows=parse_plan('```json\n'+json.dumps(dict(reminders=[dict(self.row,date_jalali='۱۴۰۵/۰۸/۱۲')]),ensure_ascii=False)+'\n```');self.assertEqual(rows[0]['date_jalali'],'1405/08/12')
    def test_invalid_or_executable_output_is_not_applied(self):
        for text in ('run command',json.dumps(dict(reminders=[dict(self.row,date_jalali='1405/13/40')])),json.dumps(dict(reminders=[dict(self.row,lead_days=[True])])),json.dumps(dict(reminders=[self.row]*21))):
            with self.assertRaises(ValueError):parse_plan(text)
        self.assertFalse(self.owner.events)
    def test_save_is_personal_validated_atomic_and_deduplicated(self):
        self.assertEqual(save_plan(self.owner,[self.row,self.row]),1);self.assertEqual(self.owner.events[0]['company'],'شخصی');self.assertEqual(self.owner.events[0]['lead_days'],[5,1,0]);self.assertTrue(self.owner.events[0]['reminder_custom']);self.assertEqual(save_plan(self.owner,[self.row]),0)
        with self.assertRaises(ValueError):save_plan(self.owner,[dict(self.row,title='دیگر'),dict(self.row,date_jalali='bad')])
        self.assertEqual(len(self.owner.events),1)
    def test_persist_failure_restores_memory(self):
        self.owner.persist=lambda:(_ for _ in ()).throw(OSError('disk unavailable'))
        with self.assertRaises(OSError):save_plan(self.owner,[self.row])
        self.assertFalse(self.owner.events)
    def test_calendar_and_assistant_permissions_are_both_required(self):
        actor=dict(id='staff',global_role='employee',memberships=[dict(company_id='mana',role='employee',permissions={'module.calendar.create':False})]);self.owner.session_user=actor
        with self.assertRaises(PermissionError):save_plan(self.owner,[self.row])
        actor['memberships'][0]['permissions']={'module.assistant.use':False}
        with self.assertRaises(PermissionError):save_plan(self.owner,[self.row])
    def test_prompt_uses_supplied_jalali_today_and_does_not_claim_write_access(self):
        p=system_prompt('1405/08/06',True);self.assertIn('1405/08/06',p);self.assertIn('reminders',p);self.assertIn('خودتان ثبت',p)

if __name__=='__main__':unittest.main()
