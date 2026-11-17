import os,sys,tempfile,unittest,copy,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QMainWindow,QDialog
from attendance_ui import AttendancePanel,AttendancePolicyDialog

class FakeOrg:
    client=None
class AttendanceUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.owner=QMainWindow();self.owner.data={'settings':{'theme':'light'}};self.owner.org=FakeOrg();self.owner.session_user={'id':'staff','global_role':'group_admin','memberships':[]};self.owner._locking=False;self.panel=AttendancePanel(self.owner);self.owner.setCentralWidget(self.panel);self.panel.company.addItem('مانا','mana');self.panel.year.setValue(1405);self.panel.month.setCurrentIndex(7);self.panel.set_people({'is_manager':True,'people':[{'employee_code':'001','user_id':'staff','name':'همکار'}]})
        self.report=dict(company='mana',month='1405/08',person={'employee_code':'001','user_id':'staff','name':'همکار'},days=[dict(date='1405/08/01',weekday='جمعه',working_day=False,required_minutes=0,leave=[],entries=[],worked_minutes=0,approved_minutes=0,overtime_minutes=0,flags=[]),dict(date='1405/08/02',weekday='شنبه',working_day=True,required_minutes=480,leave=[],entries=[dict(id='record',version=1,check_in='09:00',check_out='18:00',minutes=540,status='approved',flags=[])],worked_minutes=540,approved_minutes=540,overtime_minutes=60,flags=[]),dict(date='1405/08/03',weekday='یکشنبه',working_day=True,required_minutes=480,leave=[],entries=[],worked_minutes=0,approved_minutes=0,overtime_minutes=0,flags=['no_record'])],totals=dict(worked_minutes=540,approved_minutes=540,overtime_minutes=60,days_with_records=1,missing_days=1,incomplete_days=0),note='پیش‌نویس برای بررسی')
    def tearDown(self):self.owner.deleteLater();self.app.processEvents()
    def test_report_sorted_table_filter_chart_and_safeguard(self):
        self.panel.show_report(self.report);self.owner.resize(1050,760);self.owner.show();self.app.processEvents();self.assertEqual(self.panel.table.rowCount(),3);self.assertEqual(self.panel.table.item(1,1).text(),'شنبه');self.assertIn('۰۹:۰۰',self.panel.summary.text());self.assertEqual(len(self.panel.chart.points),1);self.panel.filter.setCurrentIndex(self.panel.filter.findData('review'));self.assertEqual(self.panel.table.rowCount(),1);self.assertIn('تردد ثبت نشده',self.panel.table.item(0,6).text());self.assertTrue(self.panel.correction_button.isVisible());self.assertFalse(self.panel.chart.grab().isNull());self.owner.data['settings']['theme']='dark';self.panel.chart.update();self.app.processEvents();self.assertFalse(self.panel.chart.grab().isNull());self.assertEqual(len(self.panel.chart.points),1)
    def test_employee_cannot_access_manager_buttons(self):
        self.owner.show();self.panel.set_people({'is_manager':False,'people':[{'employee_code':'001','user_id':'staff','name':'همکار'}]});self.app.processEvents();self.assertTrue(self.panel.import_button.isHidden());self.assertTrue(self.panel.schedule_button.isHidden());self.assertTrue(self.panel.edit_button.isHidden());self.assertFalse(self.panel.correction_button.isHidden())
    def test_policy_defaults_and_date_exception_are_preserved(self):
        week={str(i):dict(working=i in (0,1,2,5,6),start='09:00',end='17:00',break_minutes=0) for i in range(7)};policy=dict(week=week,exceptions={},people={},exclude_official_holidays=True,overtime_rule='daily_excess');dialog=AttendancePolicyDialog(self.panel,'mana',policy,self.panel.people);self.assertEqual(dialog.week.item(5,1).checkState().value,0);self.assertEqual(dialog.week.item(6,1).checkState().value,0);dialog.add_exception();dialog.exceptions.item(0,0).setText('1405/08/10');captured={}
        def run(fn,done):
            class C:
                def request(self,path,payload):captured.update(payload);return {'ok':True}
            fn(C());return True
        with patch.object(self.panel,'run',side_effect=run):dialog.save()
        self.assertIn('1405/08/10',captured['payload']['exceptions']);self.assertFalse(captured['payload']['exceptions']['1405/08/10']['working']);dialog.deleteLater()
    def test_pdf_collection_contains_per_person_and_combined(self):
        from payroll_batch import export_collection
        from payroll_ui import DEFAULTS
        from pypdf import PdfReader
        slips=[dict(copy.deepcopy(DEFAULTS),name='کارمند نمونه',code='001',period='1405/08',base='10000000',days='30'),dict(copy.deepcopy(DEFAULTS),name='همکار نمونه',code='002',period='1405/08',base='20000000',days='30')]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'slips.zip';export_collection(path,dict(title='حقوق ماه',period='1405/08',slips=slips))
            with zipfile.ZipFile(path) as z:
                names=z.namelist();self.assertEqual(len([n for n in names if n.endswith('.pdf')]),3);self.assertIn('Karname-All-Payslips.pdf',names);import io;self.assertEqual(len(PdfReader(io.BytesIO(z.read('Karname-All-Payslips.pdf'))).pages),2)

if __name__=='__main__':unittest.main()
