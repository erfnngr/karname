import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
import test_v6_ui as fixtures

class TrashUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_group_restore_and_delete_with_attachments_through_recycle_bin(self):
        import base64
        scope='__shared_chat__';staff=self.store.user(self.store.login('staff','ک')['user']['id']);group=self.store.workspace_group_create(self.admin,scope,'گروه آزمون',[staff['id']])['room']
        self.store.chat_send(self.admin,scope,group,'پیوست',attachments=[{'name':'a.txt','data':base64.b64encode(b'hello').decode()}]);fid=self.store.chat_list(self.admin,scope,group)['items'][0]['files'][0]['id'];file=self.store.files/(fid+'.bin')
        self.store.workspace_hide_room(self.admin,scope,group);panel=self.win.workspace;self.win.trash_button.click();self.pump(lambda:not panel.busy and any(r['id']==group for r in panel.trash))
        row=next(i for i,r in enumerate(panel.trash) if r['id']==group);panel.trash_table.item(row,0).setCheckState(Qt.Checked);panel.apply_trash();self.pump(lambda:not panel.busy)
        self.assertTrue(any(r['room']==group for r in self.store.chat_rooms(self.admin)));self.assertTrue(file.exists())
        self.store.workspace_hide_room(self.admin,scope,group);panel.refresh();self.pump(lambda:not panel.busy and any(r['id']==group for r in panel.trash));panel.trash_mode.setCurrentIndex(1)
        row=next(i for i,r in enumerate(panel.trash) if r['id']==group);panel.trash_table.item(row,0).setCheckState(Qt.Checked)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.apply_trash();self.pump(lambda:not panel.busy)
        self.assertFalse(file.exists());self.assertFalse(any(r['id']==group for r in self.store.workspace_trash(self.admin)));panel.recycle.close()
    def test_trash_opens_only_from_icon_and_local_restore_and_purge_work_offline(self):
        from datetime import datetime,timezone
        import storage
        panel=self.win.workspace;event=storage.new_event('شخصی','یادآور حذف‌شده',storage.jformat(storage.today_j()));self.win.data['event_trash']=[dict(event=event,deleted_at=datetime.now(timezone.utc).isoformat())];panel.owner.org.client=None
        self.assertEqual(panel.pages.indexOf(panel.recycle),-1);self.win.trash_button.click();self.app.processEvents();self.assertTrue(panel.recycle.isVisible());self.assertEqual(panel.trash_table.rowCount(),1)
        QTest.mouseClick(panel.trash_table.viewport(),Qt.LeftButton,pos=panel.trash_table.visualItemRect(panel.trash_table.item(0,1)).center());self.assertEqual(panel.trash_table.item(0,0).checkState(),Qt.Checked);panel.apply_trash();self.assertTrue(any(x['id']==event['id'] for x in self.win.events));self.assertEqual(panel.trash_table.rowCount(),0)
        self.win.data['event_trash']=[dict(event=event,deleted_at=datetime.now(timezone.utc).isoformat())];panel.refresh_local_trash();panel.trash_mode.setCurrentIndex(1);panel.trash_table.item(0,0).setCheckState(Qt.Checked)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.apply_trash()
        self.assertFalse(self.win.data['event_trash']);self.assertEqual(panel.trash_table.rowCount(),0);panel.recycle.close();self.win.org.client=self.client
    def test_shared_record_restore_and_permanent_delete_via_server(self):
        panel=self.win.workspace;record=self.store.save_record(self.admin,'client',{'title':'طرف حساب آزمایشی'},'mana');self.store.delete_record(self.admin,record['id'],record['version']);self.win.trash_button.click();self.pump(lambda:not panel.busy);self.assertEqual(panel.trash_table.rowCount(),1)
        panel.trash_table.item(0,0).setCheckState(Qt.Checked);panel.apply_trash();self.pump(lambda:not panel.busy);self.assertFalse(self.store.record(record['id'])['deleted']);self.assertEqual(panel.trash_table.rowCount(),0)
        current=self.store.record(record['id']);self.store.delete_record(self.admin,current['id'],current['version']);self.pump(lambda:not panel.busy);panel.refresh();self.pump(lambda:not panel.busy);panel.trash_mode.setCurrentIndex(1);panel.trash_table.item(0,0).setCheckState(Qt.Checked)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.apply_trash();self.pump(lambda:not panel.busy)
        with self.store.db() as c:self.assertIsNone(c.execute('SELECT id FROM records WHERE id=?',(record['id'],)).fetchone())
        panel.recycle.close()
    def test_product_and_note_restore_and_unused_product_purge(self):
        panel=self.win.workspace;group=self.store.inventory_group(self.admin,'mana','اصلی')['id'];sub=self.store.inventory_group(self.admin,'mana','فرعی',group)['id'];product=self.store.inventory_product(self.admin,'mana',dict(name='کالای آزمایشی',code='1000',group_id=sub))['id'];self.store.inventory_archive(self.admin,'mana',product,1);note=self.store.desk_note_save(self.admin,dict(title='یادداشت آزمایشی',body='نمونه'));self.store.desk_note_delete(self.admin,note['id'],1)
        self.win.trash_button.click();self.pump(lambda:not panel.busy and len(panel.trash)==2);self.assertEqual({r['trash_kind'] for r in panel.trash},{'note','product'})
        for row in range(panel.trash_table.rowCount()):panel.trash_table.item(row,0).setCheckState(Qt.Checked)
        panel.apply_trash();self.pump(lambda:not panel.busy);self.assertTrue(any(x['id']==product and x['active'] for x in self.store.inventory_list(self.admin,'mana')['products']));self.assertTrue(any(x['id']==note['id'] for x in self.store.desk_snapshot(self.admin)['notes']))
        product_row=next(x for x in self.store.inventory_list(self.admin,'mana')['products'] if x['id']==product);self.store.inventory_archive(self.admin,'mana',product,product_row['version']);self.pump(lambda:not panel.busy);panel.refresh();self.pump(lambda:not panel.busy);panel.trash_mode.setCurrentIndex(1);panel.trash_table.item(0,0).setCheckState(Qt.Checked)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.apply_trash();self.pump(lambda:not panel.busy)
        self.assertFalse(any(x['id']==product for x in self.store.inventory_list(self.admin,'mana')['products']));panel.recycle.close()
    def test_restore_request_is_compatible_with_older_host(self):
        from org_client import Client
        original=Client.request;calls=[]
        def old_host(client,path,payload=None,**query):
            if path=='workspace/trash' and payload is not None:
                calls.append(dict(payload))
                if 'company' in payload or 'purge' in payload:raise ValueError('unexpected keyword argument')
            return original(client,path,payload,**query)
        record=self.store.save_record(self.admin,'client',{'title':'آزمایشی'},'mana');self.store.delete_record(self.admin,record['id'],record['version']);panel=self.win.workspace
        with patch.object(Client,'request',old_host):
            self.win.trash_button.click();self.pump(lambda:not panel.busy and bool(panel.trash));panel.trash_table.item(0,0).setCheckState(Qt.Checked);panel.apply_trash();self.pump(lambda:not panel.busy)
        self.assertTrue(calls);self.assertFalse(self.store.record(record['id'])['deleted']);panel.recycle.close()
