import os,sys,unittest
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtWidgets import QApplication
from customers_ui import InvoiceDialog
import test_v6_ui as fixtures
from unittest.mock import patch

class InventoryUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    @patch('PySide6.QtWidgets.QMessageBox.warning',side_effect=lambda *a: (_ for _ in ()).throw(AssertionError(str(a[-1]))))
    def test_tables_and_invoice_preserve_product_link(self,_warning):
        p=self.win.clients;p.refresh_data();p.company.setCurrentIndex(p.company.findData('mana'))
        group=self.store.inventory_group(self.admin,'mana','اصلی')['id'];sub=self.store.inventory_group(self.admin,'mana','فرعی',group)['id'];pid=self.store.inventory_product(self.admin,'mana',{'name':'نمونه','code':'123','group_id':sub,'purchase_price':'50','sale_price':'100'})['id']
        p.inventory.reload();self.assertEqual(p.inventory.table.rowCount(),1)
        self.store.finance_bank_add(self.admin,'mana','حساب نمونه');p.finance.reload();self.assertEqual(p.finance.tables['banks'].rowCount(),1)
        d=InvoiceDialog(p);d.table.setRowCount(0);d.add_line({'description':'نمونه','quantity':'2','unit_price':'100','product_id':pid,'unit_cost_snapshot':'50'})
        values=d.values();self.assertEqual(values['lines'][0]['product_id'],pid);self.assertIn('۱۰۰',d.table.item(0,9).text());d.deleteLater()
    def test_picker_filters_groups_search_and_multiple_selection(self):
        from customers_ui import ProductPicker
        from PySide6.QtCore import QItemSelectionModel
        data={'groups':[{'id':'main','name':'اصلی','parent_id':None},{'id':'sub','name':'فرعی','parent_id':'main'},{'id':'other','name':'دیگر','parent_id':None}], 'products':[{'id':'a','active':1,'name':'کالای الف','code':'1000','group_id':'sub','sale_price':'100','balance':'-1'},{'id':'b','active':1,'name':'کالای ب','code':'1001','group_id':'sub','sale_price':'200','balance':'2'},{'id':'c','active':0,'name':'غیرفعال','code':'1002','group_id':'sub','sale_price':'0','balance':'0'}]}
        picker=ProductPicker(self.win.clients,data);picker.group.setCurrentIndex(picker.group.findData('main'));self.assertEqual(picker.table.rowCount(),2)
        picker.search.setText('1001');self.assertEqual(picker.table.rowCount(),1);self.assertEqual(picker.table.item(0,1).text(),'کالای ب')
        picker.search.clear();selection=picker.table.selectionModel()
        for row in (0,1):selection.select(picker.table.model().index(row,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
        picker.accept_selection();self.assertEqual({p['id'] for p in picker.selected_products},{'a','b'});picker.deleteLater()
    def test_hidden_columns_preserve_widths(self):
        panel=self.win.clients;panel.refresh_data();dialog=InvoiceDialog(panel);dialog.more_columns.setChecked(True);dialog.table.setColumnWidth(9,222);dialog.more_columns.setChecked(False);dialog.save_widths();other=InvoiceDialog(panel);other.more_columns.setChecked(True);self.assertEqual(other.table.columnWidth(9),222);dialog.deleteLater();other.deleteLater()
    def test_invoice_widths_remain_readable_after_resize(self):
        panel=self.win.clients;panel.refresh_data();dialog=InvoiceDialog(panel);dialog.resize(850,600);dialog.show();self.app.processEvents();dialog.table.setColumnWidth(3,175);dialog.resize(800,580);self.app.processEvents();self.app.processEvents();self.assertEqual(dialog.table.columnWidth(3),175);self.assertGreaterEqual(dialog.table.columnWidth(1),85);dialog.save_widths();other=InvoiceDialog(panel);self.assertEqual(other.table.columnWidth(3),175);dialog.deleteLater();other.deleteLater()
    def test_invoice_empty_row_typing_and_enter_navigation(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QLineEdit
        panel=self.win.clients;panel.refresh_data();dialog=InvoiceDialog(panel);dialog.show();self.app.processEvents();self.assertTrue(dialog.is_empty_row(0));dialog.table.setCurrentCell(0,0);dialog.table.setFocus()
        with patch.object(dialog,'choose_product') as choose:QTest.keyClicks(dialog.table,'a');choose.assert_called_once_with('a')
        dialog.add_line({'description':'نمونه','quantity':'1','unit_price':'100','product_id':'demo'});self.assertEqual(dialog.table.rowCount(),1);dialog.table.setCurrentCell(0,1);dialog.table.editItem(dialog.table.item(0,1));self.app.processEvents();editor=dialog.table.findChild(QLineEdit);self.assertIsNotNone(editor);editor.selectAll();QTest.keyClicks(editor,'2');QTest.keyClick(editor,Qt.Key_Return);self.app.processEvents();self.assertEqual(dialog.table.item(0,1).text(),'2');self.assertEqual(dialog.table.currentColumn(),3);self.assertEqual(dialog.table.rowCount(),1);self.assertEqual(dialog.values()['totals']['total'],'200')
        dialog.table.closePersistentEditor(dialog.table.item(0,3));dialog.table.setCurrentCell(0,5);dialog.table.editItem(dialog.table.item(0,5));self.app.processEvents();editor=QApplication.focusWidget();QTest.keyClick(editor,Qt.Key_Return);self.app.processEvents();self.assertEqual(dialog.table.rowCount(),2);self.assertTrue(dialog.is_empty_row(dialog.table.currentRow()));dialog.deleteLater()
    def test_sale_opens_financial_stage_by_default_and_quote_does_not(self):
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'));dialog=InvoiceDialog(panel);self.assertEqual(dialog.number.text(),'۱۰۰');self.assertEqual(dialog.kind.currentData(),'فاکتور فروش');self.assertEqual(dialog.status.currentData(),'issued');self.assertIn('امور مالی',dialog.next_button.text());dialog.kind.setCurrentIndex(dialog.kind.findData('پیش‌فاکتور'));self.assertEqual(dialog.status.currentData(),'draft');self.assertIn('پیش‌نمایش',dialog.next_button.text());dialog.deleteLater()
    def test_clicking_continue_opens_finance_as_child_of_invoice(self):
        from PySide6.QtCore import QTimer
        from settlement_ui import SettlementDialog
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'));buyer=self.store.save_record(self.admin,'client',{'title':'مشتری'},'mana');panel.records.append(buyer)
        group=self.store.inventory_group(self.admin,'mana','اصلی')['id'];sub=self.store.inventory_group(self.admin,'mana','فرعی',group)['id'];pid=self.store.inventory_product(self.admin,'mana',{'name':'کالا','code':'1000','group_id':sub,'purchase_price':'50','sale_price':'100'})['id']
        dialog=InvoiceDialog(panel,selected=buyer);dialog.add_line({'description':'کالا','quantity':'1','unit_price':'100','product_id':pid});dialog.show();self.app.processEvents();seen=[]
        def inspect():
            active=self.app.activeModalWidget()
            if isinstance(active,SettlementDialog):seen.append(active.parent() is dialog);active.reject()
        watchdog=QTimer();watchdog.setSingleShot(True);watchdog.timeout.connect(lambda:self.app.activeModalWidget().reject() if self.app.activeModalWidget() else None);watchdog.start(3000);QTimer.singleShot(300,inspect)
        with patch('PySide6.QtWidgets.QMessageBox.warning',side_effect=lambda *a: (_ for _ in ()).throw(AssertionError(str(a[-1])))):dialog.next_button.click()
        watchdog.stop();self.assertEqual(seen,[True]);self.assertEqual(dialog.result(),0);dialog.deleteLater()
    def test_invalid_invoice_displays_explanation(self):
        panel=self.win.clients;panel.refresh_data();dialog=InvoiceDialog(panel)
        with patch('PySide6.QtWidgets.QMessageBox.warning') as warning:dialog.next_button.click()
        self.assertTrue(warning.called);self.assertTrue(dialog.error.text());dialog.deleteLater()
    def test_quote_skips_financial_stage(self):
        from PySide6.QtWidgets import QDialog,QMessageBox
        from settlement_ui import SettlementDialog
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'));buyer=self.store.save_record(self.admin,'client',{'title':'مشتری'},'mana');panel.records.append(buyer)
        group=self.store.inventory_group(self.admin,'mana','اصلی')['id'];sub=self.store.inventory_group(self.admin,'mana','فرعی',group)['id'];pid=self.store.inventory_product(self.admin,'mana',{'name':'کالا','code':'1000','group_id':sub,'purchase_price':'50','sale_price':'100'})['id']
        dialog=InvoiceDialog(panel,selected=buyer);dialog.kind.setCurrentIndex(dialog.kind.findData('پیش‌فاکتور'));dialog.add_line({'description':'کالا','quantity':'1','unit_price':'100','product_id':pid})
        with patch.object(SettlementDialog,'exec',side_effect=AssertionError('پیش‌فاکتور نباید دریافت داشته باشد')),patch.object(QDialog,'exec',return_value=QDialog.Rejected) as preview,patch.object(QMessageBox,'warning',side_effect=lambda *a: (_ for _ in ()).throw(AssertionError(str(a[-1])))):dialog.next_button.click()
        self.assertTrue(preview.called);dialog.deleteLater()
    def test_real_invoice_flow_finance_preview_and_save(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog,QMessageBox
        from settlement_ui import SettlementDialog
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'));buyer=self.store.save_record(self.admin,'client',{'title':'مشتری'},'mana');panel.records.append(buyer)
        group=self.store.inventory_group(self.admin,'mana','اصلی')['id'];sub=self.store.inventory_group(self.admin,'mana','فرعی',group)['id'];pid=self.store.inventory_product(self.admin,'mana',{'name':'کالا','code':'1000','group_id':sub,'purchase_price':'50','sale_price':'100'})['id']
        dialog=InvoiceDialog(panel,selected=buyer);dialog.add_line({'description':'کالا','quantity':'2','unit_price':'100','product_id':pid});dialog.show();self.app.processEvents();seen=[]
        def advance():
            active=self.app.activeModalWidget()
            if isinstance(active,SettlementDialog):
                seen.append('finance');active.lines=[{'kind':'cash','amount':'100'}];active.confirm()
            elif isinstance(active,QDialog) and active.windowTitle()=='پیش‌نمایش و تأیید فاکتور':seen.append('preview');active.accept()
        timer=QTimer();timer.setInterval(100);timer.timeout.connect(advance);timer.start();guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(lambda:self.app.activeModalWidget().reject() if self.app.activeModalWidget() else None);guard.start(5000)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(QMessageBox,'warning',side_effect=lambda *a: (_ for _ in ()).throw(AssertionError(str(a[-1])))):dialog.next_button.click()
        timer.stop();guard.stop();self.assertEqual(seen,['finance','preview']);self.assertEqual(dialog.result(),QDialog.Accepted);saved=panel.save('invoice',dialog.payload);self.assertEqual(saved['payload']['settlement_summary']['received'],'100');self.assertEqual(saved['payload']['settlement_summary']['uncollected'],'100');dialog.deleteLater()
    def test_company_logo_is_embedded_in_invoice(self):
        from PySide6.QtGui import QTextDocument,QImage
        from PySide6.QtCore import QUrl
        from invoice_pdf import set_invoice_document
        p={'title':'آزمایش','number':'1','date':'1405/08/01','seller_name':'مانا','lines':[{'description':'کالا','quantity':'1','unit_price':'100'}]}
        doc=QTextDocument();set_invoice_document(doc,p);mark=doc.resource(QTextDocument.ImageResource,QUrl('karname-company-logo'));self.assertIsInstance(mark,QImage);self.assertFalse(mark.isNull())
    def test_invoice_preview_uses_page_navigation_without_scrollbars(self):
        from PySide6.QtWidgets import QScrollArea,QScrollBar
        from invoice_pdf import InvoicePreview
        payload={'title':'آزمایش','number':'100','date':'1405/08/01','seller_name':'مانا','lines':[{'description':'خدمت '+str(i),'quantity':'1','unit_price':'100'} for i in range(75)]}
        preview=InvoicePreview(payload);preview.resize(850,580);preview.show();self.app.processEvents();self.assertGreater(preview.page_count,1);self.assertFalse(preview.findChildren(QScrollArea));self.assertFalse(preview.findChildren(QScrollBar));preview.move(1);self.assertEqual(preview.page.page,1);preview.move(-1);self.assertEqual(preview.page.page,0);preview.deleteLater()
    def test_invoice_pdf_is_valid_landscape(self):
        import tempfile
        from pypdf import PdfReader
        from invoice_pdf import export
        payload={'title':'آزمایش','number':'100','date':'1405/08/01','seller_name':'مانا','lines':[{'description':'خدمت','quantity':'2','unit_price':'100'}]}
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'invoice.pdf';export(target,payload);pdf=PdfReader(target);self.assertGreaterEqual(len(pdf.pages),1);page=pdf.pages[0];self.assertGreater(float(page.mediabox.width),float(page.mediabox.height))
    def test_invoice_discount_and_charge_are_recomputed_in_form(self):
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'));dialog=InvoiceDialog(panel)
        dialog.add_line({'description':'کالا','quantity':'1','unit_price':'1000','discount':'0','discount_rate':'10','tax_rate':'10'})
        dialog.discount_mode.setCurrentIndex(dialog.discount_mode.findData('percent'));dialog.discount_value.setText('10');dialog.additional_charge.setText('50');dialog.charge_tax_rate.setText('20')
        payload=dialog.values();self.assertEqual(payload['lines'][0]['discount'],'100');self.assertEqual(payload['lines'][0]['invoice_discount_share'],'90');self.assertEqual(payload['totals']['total'],'951');dialog.table.setRowCount(0);dialog.add_line(payload['lines'][0]);self.assertEqual(dialog.table.item(0,4).text(),'0');self.assertEqual(dialog.table.item(0,10).text(),'10');self.assertEqual(dialog.values()['totals']['total'],'951');dialog.deleteLater()
    def test_create_sale_through_dialog_and_save(self):
        from PySide6.QtWidgets import QDialog
        from settlement_ui import SettlementDialog
        p=self.win.clients;p.refresh_data();p.company.setCurrentIndex(p.company.findData('mana'))
        buyer=self.store.save_record(self.admin,'client',{'title':'مشتری'},'mana');p.records.append(buyer)
        group=self.store.inventory_group(self.admin,'mana','اصلی')['id'];sub=self.store.inventory_group(self.admin,'mana','فرعی',group)['id'];pid=self.store.inventory_product(self.admin,'mana',{'name':'نمونه','code':'123','group_id':sub,'purchase_price':'50','sale_price':'100'})['id']
        d=InvoiceDialog(p,selected=buyer);d.table.setRowCount(0);d.add_line({'description':'نمونه','quantity':'2','unit_price':'100','product_id':pid,'unit_cost_snapshot':'50'});d.kind.setCurrentText('فاکتور فروش');d.status.setCurrentIndex(d.status.findData('issued'))
        def confirm_settlement(dialog):dialog.lines=[{'kind':'cash','amount':'100'}];return QDialog.Accepted
        with patch.object(QDialog,'exec',return_value=QDialog.Accepted),patch.object(SettlementDialog,'exec',confirm_settlement):d.validate()
        self.assertEqual(d.result(),QDialog.Accepted);saved=p.save('invoice',d.payload);self.assertIsNotNone(saved);self.assertEqual(self.store.inventory_list(self.admin,'mana')['products'][0]['balance'],'-2');self.assertEqual(saved['payload']['settlement_summary']['unallocated'],'100');d.deleteLater()
    def test_numeric_editor_and_column_size_are_preserved(self):
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtTest import QTest
        p=self.win.clients;p.refresh_data();d=InvoiceDialog(p);d.add_line({'description':'کالا','quantity':'1','unit_price':'100','product_id':'demo'});d.show();self.app.processEvents()
        d.table.setCurrentCell(0,1);d.table.editItem(d.table.item(0,1));self.app.processEvents();editor=d.table.findChild(QLineEdit);self.assertIsNotNone(editor)
        editor.selectAll();QTest.keyClicks(editor,'123x45');self.assertEqual(editor.text(),'12345');d.table.closePersistentEditor(d.table.item(0,1))
        d.table.setColumnWidth(0,280);d.save_widths();other=InvoiceDialog(p);self.assertEqual(other.table.columnWidth(0),280);other.deleteLater();d.deleteLater()
    def test_invoice_column_save_stops_after_close_and_reports_disk_error(self):
        p=self.win.clients;p.refresh_data();d=InvoiceDialog(p)
        with patch.object(self.win,'persist') as persist:
            d.save_widths();persist.assert_not_called();d.show();self.app.processEvents();d.table.setColumnWidth(0,280);d.accept();persist.assert_called_once();d.save_widths();persist.assert_called_once();self.assertFalse(d.width_timer.isActive())
        d.deleteLater();other=InvoiceDialog(p);other.show();self.app.processEvents();old=self.win.data['settings'].get('invoice_column_widths');other.table.setColumnWidth(0,310)
        with patch.object(self.win,'persist',side_effect=OSError('disk')):other.save_widths()
        self.assertEqual(self.win.data['settings'].get('invoice_column_widths'),old);self.assertIn('ذخیره',other.error.text());other.width_timer.stop();other.deleteLater()
    def test_group_buttons_store_parent_and_child(self):
        from PySide6.QtWidgets import QInputDialog
        p=self.win.clients;p.refresh_data();p.company.setCurrentIndex(p.company.findData('mana'));inventory=p.inventory;inventory.reload()
        with patch.object(QInputDialog,'getText',return_value=('گروه آزمایشی',True)):inventory.group(False)
        self.assertTrue(any(g['name']=='گروه آزمایشی' and not g['parent_id'] for g in inventory.data['groups']))
        with patch.object(QInputDialog,'getItem',return_value=('گروه آزمایشی',True)),patch.object(QInputDialog,'getText',return_value=('فرعی آزمایشی',True)):inventory.group(True)
        self.assertTrue(any(g['name']=='فرعی آزمایشی' and g['parent_id'] for g in inventory.data['groups']))
    def test_new_product_form_shows_automatic_code(self):
        from PySide6.QtWidgets import QDialog,QLineEdit
        p=self.win.clients;p.refresh_data();p.company.setCurrentIndex(p.company.findData('mana'));group=self.store.inventory_group(self.admin,'mana','گروه')['id'];self.store.inventory_group(self.admin,'mana','فرعی',group);p.inventory.reload();seen=[]
        def inspect(d):
            seen.extend((w.text(),w.isReadOnly()) for w in d.findChildren(QLineEdit));return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect):p.inventory.product(False)
        self.assertIn(('خودکار از ۱۰۰۰',True),seen)
    def test_multiple_checks_in_financial_stage(self):
        from PySide6.QtWidgets import QMessageBox,QDialog
        from settlement_ui import SettlementDialog
        p=self.win.clients;p.refresh_data();p.company.setCurrentIndex(p.company.findData('mana'))
        a=self.store.finance_check_add(self.admin,'mana','11','بانک','30','1405/08/10')['id'];b=self.store.finance_check_add(self.admin,'mana','12','بانک','40','1405/08/11')['id']
        d=SettlementDialog(p,{'totals':{'total':'100'},'document_type':'فاکتور فروش'});d.lines=[{'kind':'cash','amount':'10'},{'kind':'check','amount':'30','check_id':a},{'kind':'check','amount':'40','check_id':b}]
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.confirm()
        self.assertEqual(d.result(),QDialog.Accepted);self.assertEqual(d.summary['pending_checks'],'70');self.assertEqual(d.summary['unallocated'],'20');d.deleteLater()
    def test_add_cash_in_settlement_form(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog,QLineEdit,QDialogButtonBox
        from settlement_ui import SettlementDialog
        p=self.win.clients;p.refresh_data();p.company.setCurrentIndex(p.company.findData('mana'));dialog=SettlementDialog(p,{'totals':{'total':'100'},'document_type':'فاکتور فروش'});dialog.show()
        def fill():
            active=self.app.activeModalWidget()
            if not isinstance(active,QDialog):return
            active.findChild(QLineEdit).setText('60');active.findChild(QDialogButtonBox).accepted.emit()
        guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(lambda:self.app.activeModalWidget().reject() if self.app.activeModalWidget() else None);guard.start(1500);QTimer.singleShot(100,fill);dialog.add();guard.stop();self.assertEqual(dialog.lines,[{'kind':'cash','amount':'60'}]);dialog.deleteLater()
