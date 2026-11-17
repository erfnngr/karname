import os,sys,unittest,time,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
import test_v6_ui as fixtures
from customers_ui import CustomerDialog,InvoiceDialog,TaxJobDialog
from customer_data import invoice

class CustomerUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_quote_conversion_creates_new_sale_without_changing_original(self):
        panel=self.win.clients;original={'id':'quote','payload':{'document_type':'پیش‌فاکتور','client_id':'buyer','due_date':'1405/09/01','notes':'یادداشت','lines':[{'description':'کالا','quantity':'2','unit_price':'10'}]}}
        with patch.object(panel,'ready',return_value=True),patch.object(panel,'selected',return_value=original),patch('customers_ui.InvoiceDialog') as factory,patch.object(panel,'save',return_value={'id':'new','payload':{'title':'saved'}}) as save,patch.object(panel,'invoice_output'):
            dialog=factory.return_value;dialog.exec.return_value=QDialog.Accepted;dialog.discount_mode.findData.return_value=0;dialog.payload={'document_type':'فاکتور فروش'};panel.convert_quote()
            dialog.add_line.assert_called_once_with(original['payload']['lines'][0]);save.assert_called_once_with('invoice',dialog.payload)
            self.assertEqual(original['payload']['document_type'],'پیش‌فاکتور')
    def create_customer(self):
        panel=self.win.clients;self.pump(lambda:not self.win.org.busy);panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'));record=panel.save('client',dict(title='شرکت مشتری نمونه',customer_type='حقوقی',national_id='00123456789',economic_code='123456789012',postal_code='1234567890',address='نشانی نمونه',fiscal_year='1405'));self.assertIsNotNone(record);self.pump(lambda:not self.win.org.busy);return record
    def test_customer_form_saves_full_identity_and_searches_economic_code(self):
        record=self.create_customer();panel=self.win.clients;panel.refresh_data();self.assertEqual(panel.tables['client'].rowCount(),1);panel.search.setText('123456789012');self.assertEqual(panel.tables['client'].rowCount(),1);d=CustomerDialog(panel,record);self.assertEqual(d.fields['national_id'][0].text(),'00123456789');d.fields['contact'][0].setText('مسئول نمونه');d.validate();self.assertEqual(d.result(),QDialog.Accepted);saved=panel.save('client',d.payload,record);self.assertEqual(saved['payload']['contact'],'مسئول نمونه');d.deleteLater()
    def test_invoice_prefills_buyer_computes_and_server_saves_snapshot(self):
        record=self.create_customer();panel=self.win.clients;main=self.store.inventory_group(self.admin,'mana','گروه اصلی')['id'];sub=self.store.inventory_group(self.admin,'mana','گروه فرعی',main)['id'];product=self.store.inventory_product(self.admin,'mana',dict(group_id=sub,name='خدمات نمونه',code='1000',sale_price='1250000'))['id']
        d=InvoiceDialog(panel,selected=record);self.assertIn('123456789012',d.preview.text());d.add_line(dict(product_id=product,description='خدمات نمونه',quantity='2',unit_price='1250000',discount='500000',tax_rate='10'))
        with patch.object(QDialog,'exec',return_value=QDialog.Accepted),patch.object(QMessageBox,'warning') as warning:
            d.validate();warning.assert_not_called()
        self.assertEqual(d.result(),QDialog.Accepted);saved=panel.save('invoice',d.payload);self.assertIsNotNone(saved);self.assertEqual(saved['payload']['totals']['total'],'2200000');self.assertEqual(saved['payload']['customer_snapshot']['national_id'],'00123456789');d.deleteLater()
    def test_tax_job_reuses_period_and_appears_in_calendar(self):
        record=self.create_customer();panel=self.win.clients;d=TaxJobDialog(panel,selected=record);self.assertEqual(d.period.text(),'1405');self.assertIn('123456789012',d.preview.text());d.due.setText('1405/08/20');d.validate();saved=panel.save('tax_job',d.payload);self.assertIsNotNone(saved);self.pump(lambda:not self.win.org.busy);self.assertTrue(any(e.get('shared_id')==saved['id'] and e['category']=='مالیات' for e in self.win.shared_events));d.deleteLater()
    def test_invoice_pdf_uses_saved_snapshot_and_keeps_persian_text(self):
        from invoice_pdf import export
        from pypdf import PdfReader
        record=self.create_customer();p=invoice(dict(title='نمونه',number='INV-1',client_id=record['id'],date='1405/08/06',lines=[dict(description='خدمت آزمایشی',quantity='1',unit_price='100000',tax_rate='0')],customer_snapshot=record['payload'],seller_name='شرکت مانا'));target=self.root/'invoice.pdf';export(target,p);reader=PdfReader(target);self.assertGreater(target.stat().st_size,1000);self.assertEqual(len(reader.pages),1);self.assertTrue(reader.pages[0].extract_text())
    def test_theme_toggle_is_persisted_and_restricted_page_shortcuts_do_not_bypass_permissions(self):
        from navigation_shortcuts import activate,toggle_theme
        from main_ui import apply_preferences
        import storage
        before=self.win.data['settings']['theme'];self.assertTrue(toggle_theme(self.win));self.assertNotEqual(storage.load_data()['settings']['theme'],before);self.assertTrue(toggle_theme(self.win));self.assertEqual(storage.load_data()['settings']['theme'],before);self.assertTrue(activate(self.win,'clients'));self.assertIs(self.win.tabs.currentWidget(),self.win.clients)
        staff=self.store.user(self.store.login('staff','ک')['user']['id']);staff['memberships'][0]['permissions'].update({'module.clients.view':False,'module.settings.edit':False});self.win.session_user=staff;apply_preferences(self.win);self.assertFalse(activate(self.win,'clients'));before=self.win.data['settings']['theme'];self.assertFalse(toggle_theme(self.win));self.assertEqual(self.win.data['settings']['theme'],before)
    def test_host_control_uses_current_shared_setting_and_can_disable_it(self):
        from enhancement_settings import EnhancementSettings
        (self.root/'company-host-autostart.json').write_text('{"enabled":true}','utf-8');self.win.data['settings']['host_auto']=False;panel=EnhancementSettings(self.win);self.assertTrue(panel.host_auto.isChecked());panel.host_auto.setChecked(False)
        with patch('network_tools.set_autohost') as change:panel.commit();change.assert_called_once_with(self.root,False)
        panel.deleteLater()

if __name__=='__main__':unittest.main(verbosity=2)
