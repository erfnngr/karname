import sys,os,unittest,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
from PySide6.QtCore import QCoreApplication,QEvent
from access_ui import LoginDialog,AccessPanel,manager,user_profile,save_config
from org_store import Store
import storage

class AccessUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name);self.env=patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':str(self.root)});self.env.start();storage.set_profile(None)
    def tearDown(self):
        storage.set_profile(None);self.app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.env.stop();self.folder.cleanup()
    def pump(self,condition,seconds=12):
        end=time.monotonic()+seconds
        while not condition() and time.monotonic()<end:self.app.processEvents();time.sleep(.01)
        self.assertTrue(condition())
    def test_first_manager_setup_and_existing_login(self):
        dialog=LoginDialog(self.root);self.assertTrue(dialog.initial);dialog.first.setText('علی');dialog.last.setText('احمدی');dialog.username.setText('ali.ahmadi');dialog.password.setText('Account-Test-12345');dialog.confirm.setText('Account-Test-12345');dialog.submit();self.pump(lambda:dialog.result()==QDialog.Accepted);self.assertTrue(manager(dialog.session['user']));self.assertEqual(dialog.session['user']['first_name'],'علی');self.assertEqual(dialog.session['user']['last_name'],'احمدی');self.assertFalse(dialog.password.text());dialog.session['local_server'].close();dialog.deleteLater()
        login=LoginDialog(self.root);self.assertFalse(login.initial);login.username.setText('ali.ahmadi');login.password.setText('wrong');login.submit();self.pump(lambda:not login.busy);self.assertEqual(login.result(),0);self.assertIn('درست نیست',login.status.text());login.reject();login.deleteLater()
    def test_profile_migration_does_not_copy_private_data_to_staff(self):
        data=storage.load_data();data['events'].append(storage.new_event('شخصی','اطلاعات مدیر','1405/08/10'));storage.save_data(data);store=Store(self.root/'company-server');admin=store.bootstrap('admin','Account-Test-12345','مدیر اصلی');save_config(self.root,{'legacy_owner':admin['id']});user_profile(self.root,admin);self.assertTrue(any(e['title']=='اطلاعات مدیر' for e in storage.load_data()['events']));storage.set_profile(None)
        id=store.save_user(admin,dict(username='employee',password='Account-Test-12345',first_name='کارمند',last_name='نمونه',memberships=[dict(company_id='mana',role='employee')]))['id'];user_profile(self.root,store.user(id));self.assertEqual(storage.load_data()['events'],[]);self.assertTrue((self.root/'calendar.json').exists())
    def test_access_tabs_disabled_for_employee(self):
        store=Store(self.root/'company-server');admin=store.bootstrap('admin','Account-Test-12345','مدیر');id=store.save_user(admin,dict(username='employee',password='Account-Test-12345',fullname='کارمند نمونه',memberships=[dict(company_id='mana',role='employee')]))['id']
        class Fake:pass
        owner=Fake();owner.session_user=store.user(id);owner.org=Fake();owner.org.client=Fake();owner.org.client.user=owner.session_user;panel=AccessPanel(owner);self.assertFalse(panel.allowed);self.assertEqual(panel.tabs.tabText(0),'مدیران');self.assertEqual(panel.tabs.tabText(1),'کارکنان');self.assertTrue(all(not b.isEnabled() for b in panel.buttons));panel.deleteLater()
    def test_manager_access_form_creates_staff_and_separates_groups(self):
        from access_ui import UserDialog
        from org_http import RunningServer
        from org_client import Client
        store=Store(self.root/'company-server');store.bootstrap('admin','Account-Test-12345','مدیر اصلی');server=RunningServer(self.root/'company-server','127.0.0.1',0)
        try:
            client=Client('http://127.0.0.1:'+str(server.port));client.login('admin','Account-Test-12345')
            class Fake:pass
            owner=Fake();owner.org=Fake();owner.org.client=client;owner.session_user=client.user;panel=AccessPanel(owner);self.pump(lambda:bool(panel.people) and not panel.busy);dialog=UserDialog(panel,None,'employee');dialog.first.setText('سارا');dialog.last.setText('احمدی');dialog.username.setText('sara.ahmadi');dialog.password.setText('Staff-Test-Pass-12345');dialog.confirm.setText('Staff-Test-Pass-12345');dialog.scopes[0][1].setChecked(True);dialog.validate();self.assertEqual(dialog.result(),QDialog.Accepted);client.request('users',dialog.payload);panel.load();self.pump(lambda:not panel.busy);self.assertEqual(len(panel.visible['employee']),1);self.assertEqual(panel.visible['employee'][0]['last_name'],'احمدی');self.assertEqual(len(panel.visible['manager']),1);panel.deleteLater();dialog.deleteLater()
        finally:server.close()
    def test_home_quotes_and_backup_exit_success_failure_cancel(self):
        data=storage.load_data();data['settings'].update(news_enabled=False,reminder_enabled=False);storage.save_data(data)
        from app import TaxWindow
        from backup_bundle import verify_bundle
        win=TaxWindow();win.timer.stop();win.org.timer.stop();win.desk.timer.stop();win.news_panel.timer.stop();win.show();self.app.processEvents();self.assertTrue(win.home.quote_panel.isVisible());self.assertTrue(win.home.current_quote['source'].startswith('https://ganjoor.net/'));win.data['settings']['daily_quote_enabled']=False;win.refresh();self.assertFalse(win.home.quote_panel.isVisible());self.assertTrue(win.backup_state.dirty(win.data))
        with patch('app.QFileDialog.getSaveFileName',return_value=('','')):self.assertFalse(win.backup_now());self.assertTrue(win.backup_state.dirty(win.data))
        target=self.root/'verified.zip'
        with patch('app.QFileDialog.getSaveFileName',return_value=(str(target),'')):self.assertTrue(win.backup_now())
        self.assertFalse(win.backup_state.dirty(win.data));self.assertEqual(verify_bundle(target)[0]['settings']['daily_quote_enabled'],False)
        win._exit_approved=True
        if win.tray:win.tray.hide()
        win.hide();win.deleteLater();self.app.processEvents()
    def test_full_server_backup_is_only_for_global_manager(self):
        from org_http import RunningServer
        from org_client import Client
        from app import TaxWindow
        from backup_bundle import verify_bundle
        store=Store(self.root/'company-server');store.bootstrap('admin','Account-Test-12345','مدیر اصلی');server=RunningServer(self.root/'company-server','127.0.0.1',0)
        try:
            client=Client('http://127.0.0.1:'+str(server.port));client.login('admin','Account-Test-12345');staff=client.request('users',dict(username='staff',password='Account-Test-12345',first_name='کارمند',last_name='نمونه',memberships=[dict(company_id='mana',role='employee')]))
            data=storage.load_data();data['settings'].update(news_enabled=False,reminder_enabled=False);storage.save_data(data);win=TaxWindow(dict(user=client.user,client=client,local_server=server),self.root);win.timer.stop();win.org.timer.stop();win.desk.timer.stop();win.news_panel.timer.stop();self.app.processEvents();self.pump(lambda:not win.org.busy);self.assertTrue(win.can_backup_server());target=self.root/'full.zip'
            with patch('app.QFileDialog.getSaveFileName',return_value=(str(target),'')):self.assertTrue(win.backup_now())
            self.assertIn('server/company.sqlite',verify_bundle(target)[1]);employee=Client(client.url);employee.login('staff','Account-Test-12345');win.session_user=employee.user;win.auth_client=employee;win.org.client=employee;self.assertFalse(win.can_backup_server());target2=self.root/'staff.zip'
            with patch('app.QFileDialog.getSaveFileName',return_value=(str(target2),'')):self.assertTrue(win.backup_now())
            self.assertNotIn('server/company.sqlite',verify_bundle(target2)[1]);win.session_user=client.user;win.auth_client=client;win.org.client=client;other_id=store.save_user(client.user,dict(username='other.admin',password='Account-Test-12345',fullname='مدیر دیگر',global_role='group_admin'))['id'];
            from org_store import DomainError
            with self.assertRaises(DomainError):store.save_user(store.user(other_id),dict(id=client.user['id'],username='admin',fullname='مدیر قبلی',global_role='employee',memberships=[dict(company_id='mana',role='company_manager')]))
            self.assertTrue(win.can_backup_server());client.logout();self.assertFalse(win.can_backup_server());win._exit_approved=True
            if win.tray:win.tray.hide()
            win.hide();win.deleteLater();self.app.processEvents()
        finally:server.close()

if __name__=='__main__':unittest.main(verbosity=2)
