import os,sys,tempfile,unittest,json,hashlib,zipfile,subprocess,threading,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backup_bundle import create_bundle,verify_bundle
from backup_schedule import create_scheduled

class BackupTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.data=dict(events=[],settings={})
    def tearDown(self):self.tmp.cleanup()
    def test_encrypted_file_has_no_plaintext_temporary_archive(self):
        import backup_crypto
        secret='very-private-marker';original=backup_crypto.seal
        def checked(raw,password):
            temp=list(self.root.glob('.karname-*.tmp'));self.assertEqual(len(temp),1);self.assertNotIn(secret.encode(),temp[0].read_bytes());return original(raw,password)
        with patch.object(backup_crypto,'seal',side_effect=checked):create_bundle(self.root/'secure.karname',self.data,{'sample.txt':secret.encode()},password='test-password')
        self.assertNotIn(secret.encode(),(self.root/'secure.karname').read_bytes());self.assertEqual(verify_bundle(self.root/'secure.karname','test-password')[1]['sample.txt'],secret.encode());self.assertFalse(list(self.root.glob('.karname-*.tmp')))
    def test_password_change_same_day_survives_retention_and_second_copy(self):
        clock=datetime(2026,10,20,tzinfo=timezone.utc);a=self.root/'main';b=self.root/'second';first=create_scheduled(a,self.data,{},'before',1,1,b,clock);second=create_scheduled(a,dict(events=[{'title':'after'}],settings={}),{},'after',1,1,b,clock);self.assertNotEqual(first[0],second[0]);self.assertTrue(Path(second[0]).exists());self.assertEqual(verify_bundle(second[0],'after')[0]['events'][0]['title'],'after');self.assertTrue((b/Path(second[0]).name).exists());self.assertEqual(len(list(a.glob('*daily*.karname'))),1);third=create_scheduled(a,self.data,{},'after',1,1,b,clock);self.assertEqual(second,third)
    def test_damaged_today_backup_does_not_block_new_one(self):
        clock=datetime(2026,10,20,tzinfo=timezone.utc);a=self.root/'main';first=create_scheduled(a,self.data,{},'pass',3,3,clock=clock);Path(first[0]).write_bytes(b'corrupt');second=create_scheduled(a,self.data,{},'pass',3,3,clock=clock);self.assertNotEqual(first[0],second[0]);self.assertTrue(verify_bundle(second[0],'pass'))
    def test_automatic_backup_requires_encryption(self):
        with self.assertRaises(ValueError):create_scheduled(self.root,self.data,{},'')
        self.assertFalse(list(self.root.glob('*.karname')))
    def test_full_encrypted_server_restore_preserves_old_folder(self):
        from org_store import Store
        from server_restore import restore_closed_server
        store=Store(self.root/'company-server');admin=store.bootstrap('admin','x','مدیر');store.desk_note_save(admin,dict(title='قبل',body=''));db=self.root/'backup.sqlite';store.backup_database(db);path=self.root/'snapshot.karname';create_bundle(path,self.data,{'server/company.sqlite':db.read_bytes()},password='secret');store.desk_note_save(admin,dict(title='بعد',body=''));counts,previous=restore_closed_server(self.root,path,password='secret');self.assertEqual(counts['users'],1);self.assertTrue(previous.is_dir());self.assertEqual(len(Store(self.root/'company-server').desk_snapshot(admin)['notes']),1);self.assertEqual(len(Store(previous).desk_snapshot(admin)['notes']),2)

class UpdateTests(unittest.TestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import rsa,padding
        from cryptography.hazmat.primitives import hashes,serialization
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.private=rsa.generate_private_key(public_exponent=65537,key_size=2048);self.pub=self.root/'pub.pem';self.pub.write_bytes(self.private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo));self.exe=b'MZnew-binary-fixture';self.meta=dict(format='karname-update-v1',version='99.0',files={'Karname.exe':dict(sha256=hashlib.sha256(self.exe).hexdigest(),size=len(self.exe))});self.raw=json.dumps(self.meta).encode();self.signature=self.private.sign(self.raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256());self.pkg=self.root/'update.zip'
        with zipfile.ZipFile(self.pkg,'w') as z:z.writestr('update.json',self.raw);z.writestr('update.sig',self.signature);z.writestr('Karname.exe',self.exe)
    def tearDown(self):self.tmp.cleanup()
    def test_version_equal_with_extra_zeroes(self):
        from updater import version
        self.assertEqual(version('8.0'),version('8.0.0'));self.assertGreater(version('8.1'),version('8.0.99'))
    def test_stage_revalidates_and_tampering_never_launches_helper(self):
        from updater import stage_package,launch_helper
        stage,_=stage_package(self.pkg,self.root,self.pub);target=self.root/'Karname.exe';target.write_bytes(b'MZold');(stage/'Karname.exe').write_bytes(b'MZtampered')
        with patch('updater.subprocess.Popen') as launch:
            with self.assertRaises(ValueError):launch_helper(stage,target,self.root,self.pub)
            launch.assert_not_called()
        self.assertEqual(target.read_bytes(),b'MZold')
    def test_helper_updates_and_preserves_previous_binary_with_fixture_process(self):
        from updater import helper_script
        stage=self.root/'stage';stage.mkdir();target=self.root/'Karname.exe';old=b'MZold-fixture';target.write_bytes(old);(stage/'Karname.exe').write_bytes(self.exe);history=self.root/'history';expected=hashlib.sha256(self.exe).hexdigest();old_expected=hashlib.sha256(old).hexdigest();script=stage/'apply.ps1';script.write_text(helper_script(stage,target,999999,history,expected,old_expected),encoding='utf-8-sig');wrapper=self.root/'test.ps1';wrapper.write_text("function Start-Process { param($FilePath,$ArgumentList,$WindowStyle) }\n& '"+str(script).replace("'","''")+"'\n",encoding='utf-8-sig');r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(wrapper)],capture_output=True,timeout=20);self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace'));self.assertEqual(target.read_bytes(),self.exe);self.assertEqual((history/'Karname.exe').read_bytes(),old);self.assertTrue((history/'installed.ok').is_file())
    def test_helper_refuses_modified_incoming_file(self):
        from updater import helper_script
        stage=self.root/'stage';stage.mkdir();target=self.root/'Karname.exe';old=b'MZold-fixture';target.write_bytes(old);(stage/'Karname.exe').write_bytes(b'MZmodified');history=self.root/'history';script=stage/'apply.ps1';script.write_text(helper_script(stage,target,999999,history,hashlib.sha256(self.exe).hexdigest(),hashlib.sha256(old).hexdigest()),encoding='utf-8-sig');r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script)],capture_output=True,timeout=20);self.assertEqual(target.read_bytes(),old);self.assertFalse((history/'installed.ok').exists());self.assertTrue((stage/'update-error.txt').exists())
    def test_recovery_snapshot_path_and_integrity(self):
        from updater import stage_rollback
        history=self.root/'updates'/'previous-1';history.mkdir(parents=True);binary=b'MZold';(history/'Karname.exe').write_bytes(binary);(history/'installed.ok').write_text('ok');(history/'rollback.json').write_text(json.dumps(dict(format='karname-rollback-v1',sha256=hashlib.sha256(binary).hexdigest(),size=len(binary),version='8.0')));stage=stage_rollback(history,self.root);self.assertEqual((stage/'Karname.exe').read_bytes(),binary);(history/'Karname.exe').write_bytes(b'MZmodified')
        with self.assertRaises(ValueError):stage_rollback(history,self.root)

class HostTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_startup_config_is_tested_without_real_registry(self):
        import network_tools
        (self.root/'company-server').mkdir();(self.root/'company-server/server-cert.pem').write_text('fixture');(self.root/'server-host.json').write_text(json.dumps(dict(enabled=True,port=12345)))
        class Key:
            def __enter__(self):return self
            def __exit__(self,*x):pass
        class FakeRegistry:
            HKEY_CURRENT_USER=1;REG_SZ=1;values={}
            def CreateKey(self,*x):return Key()
            def SetValueEx(self,key,name,reserved,kind,value):self.values[name]=value
            def DeleteValue(self,key,name):self.values.pop(name,None)
        fake=FakeRegistry()
        with patch.dict(sys.modules,{'winreg':fake}):
            network_tools.set_autohost(self.root,True);self.assertTrue(fake.values);self.assertTrue(json.loads((self.root/'company-host-autostart.json').read_text())['enabled']);self.assertIn('--company-host',next(iter(fake.values.values())));network_tools.set_autohost(self.root,False);self.assertFalse(fake.values);self.assertTrue((self.root/'company-host.stop').exists());self.assertFalse(json.loads((self.root/'company-host-autostart.json').read_text())['enabled'])
    def test_diagnostics_loopback_and_bad_url(self):
        from org_http import RunningServer
        from network_tools import diagnose
        server=RunningServer(self.root/'server','127.0.0.1',0,background=False)
        try:
            steps=diagnose('http://127.0.0.1:'+str(server.port));self.assertTrue(all(x['ok'] for x in steps));self.assertFalse(diagnose('http://example.com:1234')[-1]['ok'])
        finally:server.close()
    def test_standalone_host_restarts_after_temporary_stop(self):
        import network_tools,org_http
        (self.root/'company-server').mkdir();(self.root/'server-host.json').write_text(json.dumps(dict(enabled=True,port=8843)));(self.root/'company-host-autostart.json').write_text(json.dumps(dict(enabled=True)));(self.root/'company-host.stop').write_text('old')
        started=threading.Event();closed=threading.Event()
        class FakeServer:
            def __init__(self,*args,**kwargs):self.port=8843;started.set()
            def close(self):closed.set()
        with patch.object(org_http,'RunningServer',FakeServer):
            t=threading.Thread(target=network_tools.run_host,args=(self.root,),daemon=True);t.start();self.assertTrue(started.wait(3));self.assertFalse((self.root/'company-host.stop').exists());(self.root/'company-host.stop').write_text('stop');t.join(4);self.assertFalse(t.is_alive());self.assertTrue(closed.is_set());self.assertFalse(json.loads((self.root/'company-host-status.json').read_text())['running'])
            started.clear();(self.root/'company-host-autostart.json').write_text(json.dumps(dict(enabled=False)));network_tools.run_host(self.root);self.assertFalse(started.is_set())

if __name__=='__main__':unittest.main()
