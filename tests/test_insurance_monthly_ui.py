import os,unittest
from unittest.mock import patch
from types import SimpleNamespace
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtCore import Qt
from insurance_monthly_ui import InsuranceListEditor

class MonthlyUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_existing_draft_is_preserved_and_new_spouse_field_is_blank(self):
        panel=QWidget();panel.owner=SimpleNamespace(session_user=None,org=SimpleNamespace(records=[
            {'kind':'insurance_workshop','company_id':'mana','id':'w','title':'کارگاه','payload':{}},
            {'kind':'insurance_employee','company_id':'mana','id':'p','title':'کارمند','payload':{'workshop_id':'w'}}]))
        row={'profile_id':'p','days':'30','daily_wage':'1000','daily_seniority':'20','insured_benefits':'500','non_insured_benefits':'0','unemployment_applies':True}
        record={'payload':{'title':'آبان','period':'1405/08','list_no':'1','workshop_id':'w','rows':[row]}}
        editor=InsuranceListEditor(panel,'mana',record);self.assertEqual(editor.table.item(0,0).checkState(),Qt.Checked)
        result=editor.draft_values()['rows'][0];self.assertEqual(result['daily_wage'],'1000');self.assertEqual(result['spouse_benefit'],'');self.assertEqual(result['insured_benefits'],'500');self.assertIs(result['unemployment_applies'],True)
        editor.search.setText('غیرمرتبط');self.assertTrue(editor.table.isRowHidden(0));self.assertEqual(len(editor.draft_values()['rows']),1)
        editor.search.clear();self.assertFalse(editor.table.isRowHidden(0))
        editor.close();panel.close()
    def test_switching_workshops_preserves_unsaved_rows(self):
        panel=QWidget();panel.owner=SimpleNamespace(session_user=None,org=SimpleNamespace(records=[
            {'kind':'insurance_workshop','company_id':'mana','id':'w1','title':'اول','payload':{}},
            {'kind':'insurance_workshop','company_id':'mana','id':'w2','title':'دوم','payload':{}},
            {'kind':'insurance_employee','company_id':'mana','id':'p1','title':'نفر اول','payload':{'workshop_id':'w1'}},
            {'kind':'insurance_employee','company_id':'mana','id':'p2','title':'نفر دوم','payload':{'workshop_id':'w2'}}]))
        editor=InsuranceListEditor(panel,'mana');editor.workshop.setCurrentIndex(editor.workshop.findData('w1'))
        editor.table.item(0,0).setCheckState(Qt.Checked);editor.table.item(0,2).setText('1234')
        editor.workshop.setCurrentIndex(editor.workshop.findData('w2'));editor.workshop.setCurrentIndex(editor.workshop.findData('w1'))
        self.assertEqual(editor.table.item(0,2).text(),'1234');self.assertEqual(editor.table.item(0,0).checkState(),Qt.Checked)
        editor.close();panel.close()
    def test_payroll_link_preserves_manually_entered_values(self):
        panel=QWidget();panel.owner=SimpleNamespace(session_user=None,org=SimpleNamespace(records=[
            {'kind':'insurance_workshop','company_id':'mana','id':'w','title':'کارگاه','payload':{}},
            {'kind':'employee','company_id':'mana','id':'e','title':'کارمند','payload':{'employee_code':'001'}},
            {'kind':'insurance_employee','company_id':'mana','id':'p','title':'کارمند','payload':{'workshop_id':'w','employee_id':'e'}},
            {'kind':'payroll_batch','company_id':'mana','id':'a'*32,'version':1,'title':'حقوق','payload':{'period':'1405/08','slips':[{'code':'001','days':'30','period_days':'30','base':'3000','seniority':'900'}]}}]))
        record={'payload':{'title':'آبان','period':'1405/08','list_no':'1','workshop_id':'w','rows':[{'profile_id':'p','days':'29','daily_wage':'200','daily_seniority':'30'}]}}
        editor=InsuranceListEditor(panel,'mana',record)
        with patch('PySide6.QtWidgets.QInputDialog.getItem',side_effect=lambda *args:(args[3][0],True)),patch('insurance_monthly_ui.QMessageBox.information'):
            editor.suggest_payroll()
        row=editor.draft_values()['rows'][0]
        self.assertEqual(row['payroll_batch_id'],'a'*32);self.assertEqual(row['days'],'29');self.assertEqual(row['daily_wage'],'200')
        editor.close();panel.close()
