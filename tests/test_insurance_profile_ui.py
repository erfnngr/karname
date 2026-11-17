import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QWidget,QComboBox
from org_ui import RecordDialog

class InsuranceProfileUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_profile_selectors_follow_selected_company(self):
        panel=QWidget();panel.company=QComboBox();panel.company.addItem('شرکت اول','mana');panel.kind=QComboBox();panel.people=[]
        panel.records=[{'kind':'employee','company_id':'mana','id':'a','title':'اول'},
                       {'kind':'employee','company_id':'arka','id':'b','title':'دوم'},
                       {'kind':'insurance_workshop','company_id':'arka','id':'w','title':'کارگاه دوم'}]
        form=RecordDialog(panel,'insurance_employee',company_id='arka')
        self.assertEqual(form.widgets['employee_id'][0].findData('a'),-1)
        self.assertGreater(form.widgets['employee_id'][0].findData('b'),0)
        self.assertGreater(form.widgets['workshop_id'][0].findData('w'),0)
        form.close();panel.close()
