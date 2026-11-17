import json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
import test_v6_ui as fixtures
from org_client import Client
from org_store import DomainError

class HostRestartTests(unittest.TestCase):
    def test_only_previously_enabled_identity_matched_host_starts(self):
        from lan_discovery import start_configured_host,_HOST_START_TIMES
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'server-host.json').write_text(json.dumps({'enabled':True,'port':8843}),encoding='utf-8');profile={'port':8843};_HOST_START_TIMES.clear()
            with patch('lan_discovery.is_host',return_value=False),patch('network_tools.start_autohost') as start:
                self.assertFalse(start_configured_host(root,profile));start.assert_not_called()
            with patch('lan_discovery.is_host',return_value=True),patch('network_tools.autohost_enabled',return_value=False),patch('network_tools.start_autohost') as start:
                self.assertFalse(start_configured_host(root,profile));start.assert_not_called()
            with patch('lan_discovery.is_host',return_value=True),patch('network_tools.autohost_enabled',return_value=True),patch('lan_discovery.socket.create_connection',side_effect=OSError()),patch('network_tools.start_autohost',return_value=object()) as start:
                self.assertTrue(start_configured_host(root,profile));self.assertTrue(start_configured_host(root,profile));start.assert_called_once()
    def test_discovery_retries_after_start_and_does_not_silently_switch_host(self):
        from lan_discovery import resolve_with_autostart
        expected={'url':'https://127.0.0.1:8843','identity':'same-host'}
        with patch('lan_discovery.start_configured_host',return_value=True),patch('lan_discovery.resolve',side_effect=[ValueError('not ready'),expected]) as find,patch('lan_discovery.time.sleep'):
            self.assertEqual(resolve_with_autostart('unused',{'port':8843}),expected);self.assertEqual(find.call_count,2)

class OfflineManagerDeleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_manager_can_reauthenticate_then_delete_without_granting_staff_access(self):
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'))
        record=panel.save('client',{'title':'مشتری آزمایشی'});self.pump(lambda:not self.win.org.busy)
        manager=self.store.save_user(self.admin,dict(username='manager2',password='fixture',fullname='مدیر شرکت',memberships=[dict(company_id='mana',role='company_manager')]))
        client=Client(self.client.url);user=client.login('manager2','fixture');self.win.session_user=user;self.win.org.client=None;self.win.auth_client=None
        self.win.tabs.setCurrentWidget(panel);self.app.processEvents();panel.refresh_data()
        row=next(i for i,r in enumerate(panel.visible['client']) if r['id']==record['id']);panel.tables['client'].setCurrentCell(row,0)
        dialog=MagicMock();dialog.exec.return_value=QDialog.Accepted;dialog.session=dict(user=user,client=client,local_server=None)
        with patch('access_ui.LoginDialog',return_value=dialog),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(QMessageBox,'warning') as warning:
            panel.delete_selected_customer();warning.assert_not_called()
        with self.assertRaises(DomainError):self.store.record(record['id'])
        self.assertIs(self.win.org.client,client);self.assertEqual(self.win.session_user['id'],manager['id'])
        self.pump(lambda:not self.win.org.busy)
    def test_offline_relogin_never_performs_a_shared_delete(self):
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'))
        record=panel.save('client',{'title':'حذف نشود'});self.pump(lambda:not self.win.org.busy)
        self.win.tabs.setCurrentWidget(panel);self.app.processEvents();panel.refresh_data();row=next(i for i,r in enumerate(panel.visible['client']) if r['id']==record['id']);panel.tables['client'].setCurrentCell(row,0)
        self.win.org.client=None;self.win.auth_client=None
        dialog=MagicMock();dialog.exec.return_value=QDialog.Accepted;dialog.session=dict(user=self.win.session_user,client=None,local_server=None)
        with patch('access_ui.LoginDialog',return_value=dialog),patch.object(QMessageBox,'information') as info,patch.object(QMessageBox,'question') as question:
            panel.delete_selected_customer();info.assert_called_once();question.assert_not_called()
        self.assertEqual(self.store.record(record['id'])['id'],record['id'])

if __name__=='__main__':unittest.main()
