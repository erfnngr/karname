import os,unittest
from types import SimpleNamespace
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from payroll_ui import PayrollPanel,payroll_identity

class PayrollDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_period_and_company_identity_and_reuse(self):
        self.assertEqual(payroll_identity(dict(company='مانا',code='۱۰۰',period='۱۴۰۵/۸')),payroll_identity(dict(company='مانا',code='100',period='1405/08')))
        old=[dict(name='نفر الف',company='مانا',code='100',period='1405/9',base='900'),dict(name='نفر الف',company='مانا',code='100',period='1405/10',base='1000'),dict(name='نفر دیگر',company='آرکا',code='100',period='1405/11',base='5000')]
        owner=SimpleNamespace(data={'payroll_slips':old},persist=lambda:None,statusBar=lambda:SimpleNamespace(showMessage=lambda *args:None))
        panel=PayrollPanel(owner);panel.fields['company'].setText('مانا');panel.fields['code'].setText('۱۰۰');panel.fields['period'].setText('1405/11');panel.load_person_defaults()
        self.assertEqual(panel.fields['base'].text(),'1000');self.assertEqual(panel.fields['period'].text(),'1405/11')
        panel.fields['period'].setText('۱۴۰۵/۱۰');panel.save_slip()
        self.assertEqual(len(owner.data['payroll_slips']),3);self.assertTrue(any(x['company']=='آرکا' for x in owner.data['payroll_slips']))
        panel.close()
