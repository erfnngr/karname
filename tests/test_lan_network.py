import os,sys,json,tempfile,threading,time,unittest,copy,ssl
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from org_store import Store,DomainError
from org_http import make_certificate,RunningServer
from org_client import Client
from lmstudio_client import LMClient,LMError
from lan_discovery import load_profile,offer,parse_offer,discover,resolve,trust_file
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from test_lmstudio import FakeLM

class LANTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.cert,cls.key,cls.fp=make_certificate(cls.root,['192.168.100.36'])
        cls.profile=dict(preferred_ip='127.0.0.1',port=8843,model='bonsai2',fingerprint=cls.fp,certificate=cls.cert.read_text('ascii'))
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)
    def tearDown(self):self.folder.cleanup()
    def test_profile_is_validated_and_test_folder_never_uses_bundled_company(self):
        with patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':str(self.path)}):self.assertIsNone(load_profile(self.path))
        (self.path/'network-defaults.json').write_text(json.dumps(self.profile),'utf-8');self.assertEqual(load_profile(self.path)['fingerprint'],self.fp)
        bad=dict(self.profile,fingerprint='0'*64);(self.path/'network-defaults.json').write_text(json.dumps(bad),'utf-8');self.assertIsNone(load_profile(self.path))
    def test_signed_discovery_rejects_tampering_replay_and_public_addresses(self):
        key=serialization.load_pem_private_key(self.key.read_bytes(),None);nonce='ab'*16;raw=offer(key,self.fp,nonce,8843)
        self.assertEqual(parse_offer(raw,nonce,'192.168.100.36',self.profile)['url'],'https://192.168.100.36:8843')
        for n,ip in (('cd'*16,'192.168.100.36'),(nonce,'8.8.8.8')):self.assertIsNone(parse_offer(raw,n,ip,self.profile))
        tampered=json.loads(raw);tampered['payload']['port']=8845;self.assertIsNone(parse_offer(json.dumps(tampered).encode(),nonce,'192.168.100.36',self.profile));self.assertIsNone(parse_offer(b'X'*5000,nonce,'192.168.100.36',self.profile))
    def test_real_udp_discovery_has_no_username_password_or_session(self):
        from lan_discovery import Responder
        responder=Responder(self.cert,self.key,8843,discovery_port=0,host='127.0.0.1')
        try:
            values=discover(self.profile,.2,targets=[(None,'127.0.0.1')],discovery_port=responder.discovery_port);self.assertEqual(len(values),1);self.assertEqual(values[0]['fingerprint'],self.fp);self.assertEqual(set(values[0]),{'url','fingerprint','model'})
        finally:responder.close()
    def start(self,host='127.0.0.1'):
        Store(self.path/'server').bootstrap('admin','Fixture-Password-123','مدیر نمونه');return RunningServer(self.path/'server',host,0,True,self.cert,self.key,discovery=True,discovery_port=0)
    def test_pinned_certificate_survives_address_change_and_wrong_identity_fails(self):
        server=self.start('0.0.0.0');url='https://127.0.0.2:'+str(server.port)
        try:
            c=Client(url,str(self.cert),self.fp);self.assertTrue(c.request('status')['secure']);c.login('admin','Fixture-Password-123');self.assertEqual(c.user['username'],'admin');c.session.close()
            c=Client(url,str(self.cert),'0'*64)
            with self.assertRaises(DomainError):c.request('status')
            c.session.close()
            c=Client(url,str(self.cert))
            with self.assertRaises(DomainError):c.request('status')
            c.session.close()
        finally:server.close()
    def test_resolve_verifies_signed_offer_and_https_before_returning(self):
        server=self.start();profile=dict(self.profile,port=server.port)
        real=discover
        try:
            with patch('lan_discovery.discover',side_effect=lambda p,t:real(p,.2,[(None,'127.0.0.1')],server.discovery.discovery_port)):
                result=resolve(self.path,profile);self.assertEqual(result['url'],'https://127.0.0.1:'+str(server.port));self.assertTrue(Path(result['certificate']).is_file())
            profile['preferred_ip']='127.0.0.2'
            with patch('lan_discovery.discover',return_value=[]):
                with self.assertRaises(ValueError):resolve(self.path,profile,.01)
        finally:server.close()
    def test_discovery_recovers_new_address_when_preferred_address_is_old(self):
        server=self.start();profile=dict(self.profile,preferred_ip='192.168.100.99',port=8843)
        real=discover
        try:
            with patch('lan_discovery.discover',side_effect=lambda p,t:real(p,.2,[(None,'127.0.0.1')],server.discovery.discovery_port)):
                result=resolve(self.path,profile);self.assertEqual(result['url'],'https://127.0.0.1:'+str(server.port))
        finally:server.close()

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.model_patch=patch('ai_gateway.GEMMA_MODEL','local-chat');self.model_patch.start();self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root);self.admin=self.store.bootstrap('admin','Fixture-Password-123','مدیر');self.server=RunningServer(self.root,'127.0.0.1',0);self.client=Client('http://127.0.0.1:'+str(self.server.port));self.client.login('admin','Fixture-Password-123')
        FakeLM.requests=[];FakeLM.mode='stream';self.fake=ThreadingHTTPServer(('127.0.0.1',0),FakeLM);threading.Thread(target=self.fake.serve_forever,daemon=True).start();self.server.server.ai_backend='http://127.0.0.1:'+str(self.fake.server_port)+'/v1'
    def tearDown(self):self.client.session.close();self.server.close();self.fake.shutdown();self.fake.server_close();self.temp.cleanup();self.model_patch.stop()
    def test_authenticated_gateway_filters_models_and_streams_actual_chunks(self):
        c=LMClient.company(self.client,3)
        try:
            self.assertEqual(c.models(),['local-chat']);parts=[];answer=c.chat('local-chat',[dict(role='user',content='سلام')],parts.append);self.assertEqual(answer,'سلام از مدل محلی');self.assertEqual(parts,['سلام',' از مدل محلی']);self.assertNotIn('Authorization',FakeLM.requests[0]);self.assertTrue(c.company_mode)
        finally:c.close()
    def test_gateway_requires_account_and_current_assistant_permission(self):
        import requests
        session=requests.Session();session.trust_env=False
        self.assertEqual(session.get(self.client.url+'/api/ai/models').status_code,401);session.close()
        self.store.save_user(self.admin,dict(username='staff',password='Fixture-Password-123',fullname='کارمند',memberships=[dict(company_id='mana',role='employee',permissions={'module.assistant.use':False})]));staff=Client(self.client.url);staff.login('staff','Fixture-Password-123');c=LMClient.company(staff)
        try:
            with self.assertRaises(LMError):c.models()
            self.assertFalse(FakeLM.requests)
        finally:c.close();staff.session.close()
    def test_gateway_does_not_accept_tools_or_remote_target(self):
        for extra in ({'tools':[]},{'url':'https://example.com'}):
            with self.assertRaises(DomainError):self.client.request('ai/chat/completions',dict(model='local-chat',messages=[dict(role='user',content='سلام')],**extra))
        self.assertFalse(FakeLM.requests)
    def test_gateway_uses_json_fallback_and_bounds_payload(self):
        FakeLM.mode='json';c=LMClient.company(self.client)
        try:self.assertEqual(c.chat('local-chat',[dict(role='user',content='سلام')],lambda _:None),'پاسخ محلی')
        finally:c.close()
        with self.assertRaises(DomainError):self.client.request('ai/chat/completions',dict(model='local-chat',messages=[dict(role='user',content='x'*17000)]))
    def test_gateway_preserves_long_assistant_context_for_network_users(self):
        c=LMClient.company(self.client,3);system='s'*17000+'END'
        try:self.assertEqual(c.chat('local-chat',[dict(role='system',content=system),dict(role='user',content='سلام')],lambda _:None),'سلام از مدل محلی')
        finally:c.close()
        self.assertEqual(FakeLM.requests[-1]['messages'][0]['content'],system)
        with self.assertRaises(DomainError):self.client.request('ai/chat/completions',dict(model='local-chat',messages=[dict(role='system',content='x'*32001)]))
    def test_busy_gateway_releases_slots_and_can_be_used_again(self):
        slots=self.server.server.ai_slots
        for _ in range(3):self.assertTrue(slots.acquire(False))
        c=LMClient.company(self.client)
        try:
            with self.assertRaises(LMError):c.models()
            for _ in range(3):slots.release()
            self.assertEqual(c.models(),['local-chat'])
        finally:c.close()

if __name__=='__main__':unittest.main(verbosity=2)
