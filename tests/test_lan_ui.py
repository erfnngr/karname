import os,sys,json,tempfile,time,unittest,threading
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import QCoreApplication,QEvent
from access_ui import LoginDialog,config
from org_store import Store
from org_http import RunningServer,make_certificate
from org_client import Client
from test_lmstudio import FakeLM
from ai_chat_ui import LMStudioSettings,make_client
from lan_discovery import trust_file
import storage

class AutomaticNetworkUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.client_root=self.root/'client';self.client_root.mkdir();self.env=patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':str(self.client_root)});self.env.start();storage.set_profile(None)
        self.store=Store(self.root/'server');self.store.bootstrap('manager','Fixture-Password-123','مدیر نمونه');self.cert,self.key,self.fp=make_certificate(self.root/'identity',['192.168.100.36']);self.server=RunningServer(self.root/'server','127.0.0.1',0,True,self.cert,self.key)
        self.profile=dict(preferred_ip='127.0.0.1',port=self.server.port,model='local-chat',fingerprint=self.fp,certificate=self.cert.read_text('ascii'));(self.client_root/'network-defaults.json').write_text(json.dumps(self.profile),'utf-8');self.network=dict(url='https://127.0.0.1:'+str(self.server.port),certificate=trust_file(self.client_root,self.profile),fingerprint=self.fp,model='local-chat',identity=self.fp)
        self.resolve=patch('lan_discovery.resolve',return_value=self.network);self.resolve.start();self.dialogs=[]
    def tearDown(self):
        for d in self.dialogs:d.reject();d.deleteLater()
        self.app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.resolve.stop();self.server.close();storage.set_profile(None);self.env.stop();self.temp.cleanup()
    def pump(self,condition,seconds=12):
        end=time.monotonic()+seconds
        while not condition() and time.monotonic()<end:self.app.processEvents();time.sleep(.01)
        self.assertTrue(condition())
    def login(self):
        d=LoginDialog(self.client_root);self.dialogs.append(d);d.show();self.pump(lambda:d.network is not None);d.username.setText('manager');d.password.setText('Fixture-Password-123');d.submit();self.pump(lambda:d.result()==QDialog.Accepted);return d
    def test_first_launch_finds_company_without_manual_address_or_extra_account(self):
        d=LoginDialog(self.client_root);self.dialogs.append(d);d.show();self.pump(lambda:d.network is not None);self.assertEqual(d.mode.currentData(),'auto');self.assertFalse(d.initial);self.assertTrue(d.url.isHidden());self.assertTrue(d.cert.isHidden());self.assertFalse((self.client_root/'company-server/company.sqlite').exists());self.assertIn('پیدا شد',d.status.text())
    def test_auto_login_persists_mode_and_same_company_identity(self):
        d=self.login();self.assertEqual(d.session['user']['username'],'manager');self.assertEqual(d.session['client'].fingerprint,self.fp);saved=config(self.client_root);self.assertEqual(saved['mode'],'auto');self.assertEqual(saved['server_identity'],self.fp);self.assertNotIn('password',saved);self.assertFalse(d.session.get('local_server'));self.assertFalse(d.password.text());self.assertEqual(d.session['client'].cache.aad,('network://'+self.fp+'\nmanager').encode());d.session['client'].session.close()
    def test_host_absent_never_creates_a_local_admin_and_manual_mode_remains_editable(self):
        self.resolve.stop();self.resolve=patch('lan_discovery.resolve',side_effect=ValueError('میزبان شرکت پیدا نشد'));self.resolve.start();d=LoginDialog(self.client_root);self.dialogs.append(d);d.show();self.pump(lambda:not d.discovering and 'پیدا نشد' in d.status.text());self.assertFalse(d.initial);self.assertFalse((self.client_root/'company-server/company.sqlite').exists());d.mode.setCurrentIndex(d.mode.findData('remote'));self.app.processEvents();self.assertTrue(d.url.isVisible());self.assertFalse(d.url.isReadOnly());self.assertTrue(d.cert.isVisible())
    def test_automatic_ai_uses_authenticated_company_and_manual_override_is_available(self):
        from types import SimpleNamespace
        c=Client(self.network['url'],self.network['certificate'],self.fp);c.login('manager','Fixture-Password-123');owner=SimpleNamespace(base_dir=self.client_root,data={'settings':{}},session_user=c.user,auth_client=c)
        panel=LMStudioSettings(owner);self.assertTrue(panel.automatic.isChecked());self.assertFalse(panel.url.isEnabled());model_client=make_client(owner);self.assertTrue(model_client.company_mode);self.assertEqual(model_client.url,c.url+'/api/ai');model_client.close();panel.automatic.setChecked(False);panel.url.setText('http://192.168.100.8:1234');self.assertTrue(panel.url.isEnabled());values=panel.values();self.assertFalse(values['auto']);self.assertEqual(values['url'],'http://192.168.100.8:1234/v1');panel.deleteLater();c.session.close()
    def test_late_discovery_does_not_overwrite_manual_selection(self):
        d=LoginDialog(self.client_root);self.dialogs.append(d);d.mode.setCurrentIndex(d.mode.findData('remote'));d.url.setText('https://192.168.100.8:8843');d.network_found(self.network,None);self.assertEqual(d.url.text(),'https://192.168.100.8:8843')
    def test_existing_client_moves_to_auto_once_and_explicit_manual_choice_is_preserved(self):
        from access_ui import save_config
        save_config(self.client_root,dict(mode='local'));d=LoginDialog(self.client_root);self.dialogs.append(d);self.assertEqual(d.mode.currentData(),'auto');d.reject()
        save_config(self.client_root,dict(mode='local',network_mode_version=1));d=LoginDialog(self.client_root);self.dialogs.append(d);self.assertEqual(d.mode.currentData(),'local');d.reject()
        save_config(self.client_root,dict(mode='remote',url='https://192.168.100.8:8843'));d=LoginDialog(self.client_root);self.dialogs.append(d);self.assertEqual(d.mode.currentData(),'remote')

if __name__=='__main__':unittest.main(verbosity=2)
