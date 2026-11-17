import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QTableWidget,QComboBox,QLineEdit,QPushButton,QMessageBox
import test_v6_ui as fixtures


class FinanceSplitUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_split_payment_through_native_forms(self):
        buyer=self.store.save_record(self.admin,'client',{'title':'مشتری'},'mana')
        base={'title':'فروش','client_id':buyer['id'],'date':'1405/08/01','document_type':'فاکتور فروش','status':'issued','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[]}
        self.store.save_record(self.admin,'invoice',dict(base,number='1'),'mana');self.store.save_record(self.admin,'invoice',dict(base,number='2'),'mana')
        self.pump(lambda:not self.win.org.busy);self.win.org.revision=None;self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'));panel.finance.reload()
        def execute(dialog):
            if dialog.windowTitle()=='تخصیص مبلغ به فاکتورها':
                table=dialog.findChild(QTableWidget,'FinanceAllocationTable');self.assertEqual(table.rowCount(),2);table.cellWidget(0,2).setText('600');table.cellWidget(1,2).setText('400');dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click();return dialog.result()
            self.assertEqual(dialog.windowTitle(),'ثبت دریافت / پرداخت');combo=dialog.findChild(QComboBox,'FinanceCustomer');combo.setCurrentIndex(combo.findData(buyer['id']));dialog.findChild(QLineEdit,'FinanceAmount').setText('1100');dialog.findChild(QLineEdit,'FinanceReason').setText('واریز نمونه');dialog.findChild(QPushButton,'FinanceAllocate').click();return QDialog.Accepted
        with patch.object(QDialog,'exec',new=execute),patch.object(QMessageBox,'warning',side_effect=lambda *a: (_ for _ in ()).throw(AssertionError(str(a[-1])))):
            panel.finance.transaction(False)
        data=self.store.finance_list(self.admin,'mana');self.assertEqual(len(data['transactions'][0]['allocations']),2);self.assertEqual(data['balances'][buyer['id']],'900')
    def test_ai_draft_does_not_preselect_payment_method_or_save_on_cancel(self):
        panel=self.win.clients;panel.refresh_data();panel.company.setCurrentIndex(panel.company.findData('mana'))
        def execute(dialog):
            self.assertEqual(dialog.windowTitle(),'پیش‌نویس مالی کارنامه');method=next(c for c in dialog.findChildren(QComboBox) if c.findText('انتخاب روش پرداخت')>=0);self.assertEqual(method.currentData(),'');self.assertEqual(dialog.findChild(QLineEdit,'FinanceAmount').text(),'300');return QDialog.Rejected
        with patch.object(QDialog,'exec',new=execute):panel.finance.transaction(False,prefill={'direction':'expense','amount':'300','date':'1405/08/02','reason':'اجاره'})
        self.assertFalse(self.store.finance_list(self.admin,'mana')['transactions'])
