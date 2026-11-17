import os,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QTableWidget
from PySide6.QtCore import QTimer
import test_v6_ui as fixtures

class QualityUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.V6UiTests.setUpClass();cls.app=fixtures.V6UiTests.app
    setUp=fixtures.V6UiTests.setUp
    tearDown=fixtures.V6UiTests.tearDown
    pump=fixtures.V6UiTests.pump
    def test_quality_report_shows_current_company_findings(self):
        panel=self.win.clients.finance
        panel.panel.company.setCurrentIndex(panel.panel.company.findData('mana'))
        self.store.save_record(self.admin,'client',{'title':'الف','phone':'123456'},'mana')
        self.store.save_record(self.admin,'client',{'title':'ب','phone':'123456'},'mana')
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel.panel.refresh_data()
        seen=[]
        def check():
            dialog=self.app.activeModalWidget()
            if dialog:
                tables=dialog.findChildren(QTableWidget);seen.append(tables[0].rowCount() if tables else -1);dialog.accept()
        QTimer.singleShot(50,check);panel.show_data_quality();self.assertTrue(seen);self.assertGreaterEqual(seen[0],2)
    def test_statement_shows_linked_visible_followup(self):
        panel=self.win.clients.finance;panel.panel.company.setCurrentIndex(panel.panel.company.findData('mana'))
        client=self.store.save_record(self.admin,'client',{'title':'مشتری نمونه'},'mana')
        self.store.save_record(self.admin,'task',{'title':'پیگیری پرداخت','due_date':'1405/08/21','status':'draft','related_customer_id':client['id']},'mana')
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel.panel.refresh_data()
        panel.balance_customers=[client['id']];panel.tables['balances'].setRowCount(1);panel.tables['balances'].setCurrentCell(0,0);seen=[]
        def check():
            dialog=self.app.activeModalWidget()
            if dialog:seen.append([t.rowCount() for t in dialog.findChildren(QTableWidget)]);dialog.accept()
        QTimer.singleShot(50,check);panel.show_statement();self.assertTrue(seen);self.assertIn(1,seen[0])
