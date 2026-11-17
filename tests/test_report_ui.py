import os,sys,unittest
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtWidgets import QApplication
from report_ui import ReportDialog
from org_reports import spreadsheet,pdf_report
import test_v6_ui as fixtures
from unittest.mock import patch
import jdatetime

class ReportUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_filter_columns_and_export(self):
        self.store.finance_transaction(self.admin,'mana',{'direction':'income','method':'cash','amount':'200','date':'1405/08/02','reason':'نمونه'})
        p=self.win.clients;p.refresh_data();p.company.setCurrentIndex(p.company.findData('mana'));d=ReportDialog(p);d.kind.setCurrentIndex(d.kind.findData('transaction'));d.start.setText('1405/08/01');d.end.setText('1405/08/05');next(check for key,_,check in d.checks if key=='reason').setChecked(False);rows=d.load_rows();self.assertEqual(len(rows),1);self.assertNotIn('علت',rows[0]);self.assertEqual(rows[0]['نوع'],'دریافت')
        from openpyxl import load_workbook
        x=self.root/'report.xlsx';pdf=self.root/'report.pdf';spreadsheet(x,rows);pdf_report(pdf,rows);book=load_workbook(x,read_only=True);self.assertIn('شماره سند',[x.value for x in next(book.active.rows)]);book.close();self.assertGreater(pdf.stat().st_size,1000);d.deleteLater()
    def test_ranges_across_year_boundary_and_leap_day(self):
        from storage import normalize
        from report_ui import JalaliDatePicker
        p=self.win.clients;d=ReportDialog(p)
        with patch('report_ui.today_j',return_value=jdatetime.date(1404,1,2)):
            d.period.setCurrentIndex(d.period.findData('previous'));self.assertEqual((normalize(d.start.text()),normalize(d.end.text())),('1403/12/01','1403/12/30'))
            d.period.setCurrentIndex(d.period.findData('month'));self.assertEqual((normalize(d.start.text()),normalize(d.end.text())),('1404/01/01','1404/01/31'))
            d.period.setCurrentIndex(d.period.findData('last30'));self.assertEqual((normalize(d.start.text()),normalize(d.end.text())),('1403/12/03','1404/01/02'))
            d.period.setCurrentIndex(d.period.findData('all'));self.assertFalse(d.start.text());self.assertFalse(d.end.text())
        picker=JalaliDatePicker('1403/12/30');self.assertEqual(normalize(picker.value()),'1403/12/30');picker.year.setValue(1404);self.assertEqual(normalize(picker.value()),'1404/12/29');picker.deleteLater();d.deleteLater()
    def test_invoice_list_no_pdf_button_but_report_pdf_available(self):
        from PySide6.QtWidgets import QPushButton
        p=self.win.clients;page=p.pages.widget(1);self.assertFalse(any(w.text()=='PDF' or w.accessibleName()=='PDF' for w in page.findChildren(QPushButton)))
        d=ReportDialog(p);self.assertTrue(any('PDF' in w.text() for w in d.findChildren(QPushButton)));d.deleteLater()
