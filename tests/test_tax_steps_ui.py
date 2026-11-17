import os,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QPushButton,QTableWidget
from PySide6.QtCore import QTimer,Qt
import test_v6_ui as fixtures

class TaxStepsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.V6UiTests.setUpClass();cls.app=fixtures.V6UiTests.app
    setUp=fixtures.V6UiTests.setUp
    tearDown=fixtures.V6UiTests.tearDown
    pump=fixtures.V6UiTests.pump
    def test_click_map_step_completes_and_returns(self):
        record=self.client.request('records',dict(kind='tax_case',company='mana',payload=dict(title='گام آزمایشی',tax_type='حقوق',period='1405/08',status='draft')))
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel=self.win.tax_center;panel.company.setCurrentIndex(panel.company.findData('mana'));panel.workflow.setCurrentText('حقوق');panel.map_case.setCurrentIndex(panel.map_case.findData(record['id']))
        def complete():
            d=self.app.activeModalWidget()
            if d:next(b for b in d.findChildren(QPushButton) if 'تأیید این مرحله' in b.text()).click()
        QTimer.singleShot(100,complete);panel.open_map_step(0)
        saved=self.client.request('record',id=record['id']);self.assertTrue(saved['payload']['workflow_done'][0])
    def test_web_bridge_step_saves_real_record_and_refreshes_progress(self):
        import json
        from react_tax_bridge import ReactTaxBridge
        record=self.client.request('records',dict(kind='tax_case',company='mana',payload=dict(title='آزمون نقشه',tax_type='حقوق',period='1405/08',status='draft')))
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel=self.win.tax_center;panel.company.setCurrentIndex(panel.company.findData('mana'));panel.workflow.setCurrentText('حقوق');panel.map_case.setCurrentIndex(panel.map_case.findData(record['id']))
        bridge=ReactTaxBridge(panel);states=[];results=[];bridge.changed.connect(lambda value:states.append(json.loads(value)));bridge.completed.connect(lambda key,value:results.append(json.loads(value)))
        def complete():
            d=self.app.activeModalWidget()
            if d:next(b for b in d.findChildren(QPushButton) if 'تأیید این مرحله' in b.text()).click()
        QTimer.singleShot(100,complete);bridge.request('step','step',json.dumps({'index':0}));self.pump(lambda:not self.win.org.busy);bridge.publish()
        self.assertTrue(results[-1]['ok']);self.assertTrue(self.client.request('record',id=record['id'])['payload']['workflow_done'][0]);self.assertTrue(states[-1]['steps'][0]['done']);bridge.close()
    def test_map_changes_with_tax_type_and_tracks_selected_case(self):
        from tax_workflows import WORKFLOWS
        record=self.client.request('records',dict(kind='tax_case',company='mana',payload=dict(title='بیمه نمونه',tax_type='بیمه کارکنان',period='1405/08',status='draft')))
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel=self.win.tax_center;panel.company.setCurrentIndex(panel.company.findData('mana'));panel.workflow.setCurrentText('بیمه کارکنان')
        self.assertEqual(panel.main_roadmap.steps,WORKFLOWS['بیمه کارکنان']);self.assertGreater(panel.map_case.findData(record['id']),0)
        panel.workflow.setCurrentText('حقوق');self.assertEqual(panel.main_roadmap.steps,WORKFLOWS['حقوق']);self.assertEqual(panel.map_case.findData(record['id']),-1)
    def test_tax_due_date_appears_in_shared_calendar(self):
        record=self.client.request('records',dict(kind='tax_case',company='mana',payload=dict(title='موعد آزمایشی مالیات',tax_type='حقوق',period='1405/08',status='draft',due_date='1405/08/25')))
        self.win.org.sync();self.pump(lambda:not self.win.org.busy)
        event=next(e for e in self.win.shared_events if e.get('shared_id')==record['id'])
        self.assertEqual(event['date_jalali'],'1405/08/25');self.assertEqual(event['category'],'مالیات')
    def test_category_and_overview_show_the_same_case(self):
        self.client.request('records',dict(kind='tax_case',company='mana',payload=dict(title='پرونده نمونه',tax_type='حقوق',period='1405/08',status='draft')))
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel=self.win.tax_center;panel.company.setCurrentIndex(panel.company.findData('mana'));panel.kind.setCurrentText('همه تکالیف');panel.render()
        self.assertTrue(any(r['payload']['title']=='پرونده نمونه' for r in panel.visible))
        table,records=panel.category_tables['حقوق'];self.assertTrue(any(r['payload']['title']=='پرونده نمونه' for r in records));self.assertGreater(table.rowCount(),0)
        panel.progress_filter.setCurrentText('کامل');self.assertFalse(any(r['payload']['title']=='پرونده نمونه' for r in panel.visible))
        panel.progress_filter.setCurrentText('ناقص');self.assertTrue(any(r['payload']['title']=='پرونده نمونه' for r in panel.visible))
    def test_next_step_is_saved_in_company_record(self):
        record=self.client.request('records',dict(kind='tax_case',company='mana',payload=dict(title='بیمه آبان',tax_type='بیمه کارکنان',period='1405/08',status='draft',insured_names='کارمند نمونه')))
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel=self.win.tax_center;panel.company.setCurrentIndex(panel.company.findData('mana'));panel.render();panel.cases.setCurrentCell(0,0);seen=[]
        def advance():
            d=self.app.activeModalWidget()
            if d:
                button=next(x for x in d.findChildren(QPushButton) if 'تأیید این مرحله' in x.text());button.click();seen.append(True);d.accept()
        QTimer.singleShot(100,advance);panel.case_steps();self.assertTrue(seen)
        saved=self.client.request('record',id=record['id']);self.assertTrue(saved['payload']['workflow_done'][0]);self.assertFalse(saved['payload']['workflow_done'][1])
    def test_insured_person_review_is_saved_for_the_month(self):
        record=self.client.request('records',dict(kind='tax_case',company='mana',payload=dict(title='بیمه آبان',tax_type='بیمه کارکنان',period='1405/08',status='draft',insured_names='کارمند نمونه')))
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);panel=self.win.tax_center;panel.company.setCurrentIndex(panel.company.findData('mana'));panel.render();panel.cases.setCurrentCell(0,0);seen=[]
        def save():
            d=self.app.activeModalWidget()
            if d:
                table=d.findChild(QTableWidget);table.item(0,1).setCheckState(Qt.Checked);next(x for x in d.findChildren(QPushButton) if x.text()=='ذخیره فهرست ماه').click();seen.append(True)
        QTimer.singleShot(100,save);panel.insured_people();self.assertTrue(seen)
        saved=self.client.request('record',id=record['id']);self.assertEqual(saved['payload']['insured_entries'],[dict(name='کارمند نمونه',reviewed=True)])
