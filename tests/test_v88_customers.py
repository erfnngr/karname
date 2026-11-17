import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtWidgets import QApplication,QMessageBox
import test_v6_ui as fixtures
from org_store import DomainError

class DeleteCustomerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_confirmation_delete_invoice_preservation_and_restore(self):
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'))
        record=panel.save('client',{'title':'مشتری آزمایشی'});self.assertIsNotNone(record);self.pump(lambda:not self.win.org.busy)
        invoice=self.store.save_record(self.admin,'invoice',dict(title='فاکتور آزمایشی',client_id=record['id'],number='TEST-001',date='1405/08/09',lines=[dict(description='خدمت',quantity='1',unit_price='100')]),'mana')
        self.win.tabs.setCurrentWidget(panel);self.app.processEvents();panel.refresh_data();row=next(i for i,r in enumerate(panel.visible['client']) if r['id']==record['id']);panel.tables['client'].setCurrentCell(row,0)
        self.assertIsNotNone(panel.selected('client'),'selected row should identify a customer')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):panel.delete_selected_customer()
        self.assertEqual(self.store.record(record['id'])['id'],record['id'])
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(QMessageBox,'warning') as warning:panel.delete_selected_customer();warning.assert_not_called()
        with self.assertRaises(DomainError):self.store.record(record['id'])
        self.assertEqual(self.store.record(invoice['id'])['payload']['customer_snapshot']['title'],'مشتری آزمایشی')
        trashed=next(r for r in self.store.workspace_trash(self.admin) if r['id']==record['id'])
        self.store.workspace_trash(self.admin,kind='record',id=record['id'],version=trashed['version'],restore=True)
        self.assertEqual(self.store.record(record['id'])['title'],'مشتری آزمایشی')
    def test_staff_without_delete_access_is_denied_by_server(self):
        record=self.store.save_record(self.admin,'client',{'title':'نمونه'},'mana')
        staff=self.store.user(self.store.login('staff','ک')['user']['id'])
        with self.assertRaises(DomainError):self.store.delete_record(staff,record['id'],record['version'])
        self.assertEqual(self.store.record(record['id'])['id'],record['id'])
    def test_invoice_delete_is_confirmed_and_can_be_restored(self):
        from customers_ui import InvoiceDialog
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'))
        customer=panel.save('client',{'title':'مشتری آزمایشی'});self.pump(lambda:not self.win.org.busy)
        invoice=panel.save('invoice',dict(title='فاکتور آزمایشی',client_id=customer['id'],number='TEST-002',date='1405/08/09',lines=[dict(description='خدمت',quantity='1',unit_price='100')]));self.pump(lambda:not self.win.org.busy)
        self.win.tabs.setCurrentWidget(panel);panel.pages.setCurrentIndex(1);self.app.processEvents();panel.refresh_data()
        row=next(i for i,r in enumerate(panel.visible['invoice']) if r['id']==invoice['id']);panel.tables['invoice'].setCurrentCell(row,0)
        self.assertIsNotNone(panel.selected('invoice'))
        dialog=InvoiceDialog(panel,invoice)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.delete_invoice()
        self.assertTrue(dialog.delete_requested);dialog.deleteLater()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):panel.delete_selected_invoice()
        self.assertEqual(self.store.record(invoice['id'])['id'],invoice['id'])
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(QMessageBox,'warning') as warning:panel.delete_selected_invoice();warning.assert_not_called()
        with self.assertRaises(DomainError):self.store.record(invoice['id'])
        self.assertEqual(self.store.record(customer['id'])['id'],customer['id'])
        trashed=next(r for r in self.store.workspace_trash(self.admin) if r['id']==invoice['id'])
        self.store.workspace_trash(self.admin,kind='record',id=invoice['id'],version=trashed['version'],restore=True)
        self.assertEqual(self.store.record(invoice['id'])['payload']['number'],'TEST-002')

if __name__=='__main__':unittest.main()
