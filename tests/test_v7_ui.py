import os,sys,time,copy,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QLabel,QDialog
from PySide6.QtCore import QObject,QEvent
import test_v6_ui as fixtures
from calendar_labels import OccasionLabel
from desk_ui import NoteDialog,LeaveDialog,PersonalEditor
from storage import parse_j

class V7UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.strays=[];target=self.strays
        class Observer(QObject):
            def eventFilter(self,obj,event):
                if event.type()==QEvent.Show and isinstance(obj,QLabel) and obj.isWindow():target.append(obj.objectName())
                return False
        self.observer=Observer();self.app.installEventFilter(self.observer);fixtures.V6UiTests.setUp(self);self.win.desk.timer.stop()
    def tearDown(self):self.app.removeEventFilter(self.observer);fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_calendar_never_shows_temporary_top_level_labels(self):
        self.assertFalse(self.strays)
        for i in range(3):self.win.refresh();self.app.processEvents()
        self.assertFalse(self.strays);self.assertIsNotNone(self.win.footer.parent());self.assertIsNotNone(self.win.side_caption.parent())
    def test_calendar_titles_and_selected_day_occasions(self):
        self.win.selected=parse_j('1405/08/05');self.win.year=1405;self.win.month=8;self.win.tabs.setCurrentWidget(self.win.calendar_page);self.win.refresh();self.app.processEvents();self.assertIn('میراث دیداری',self.win.selected_occasions.text());labels=self.win.calendar_page.findChildren(OccasionLabel);self.assertTrue(any('میراث دیداری' in l.full for l in labels));self.assertTrue(all(l.parent() is not None for l in labels));self.assertTrue(any(l.text() and l.text()!='•' for l in labels))
    def test_occasions_search_other_month_and_only_official_red(self):
        panel=self.win.occasions_panel;panel.year.setValue(1405);panel.month.setCurrentIndex(0);panel.query.setText('یلدا');self.assertTrue(panel.rendered_items);self.assertTrue(all('یلدا' in x['title'] for x in panel.rendered_items));self.assertFalse(panel.month.isEnabled());panel.query.setText('کدنویسی');self.assertTrue(panel.rendered_items);self.assertFalse(panel.rendered_items[0]['holiday']);self.assertNotIn('#FFECEF',panel.items.itemAt(0).widget().styleSheet());panel.query.setText('فاطمه');self.assertTrue(panel.rendered_items[0]['holiday']);self.assertIn('#FFECEF',panel.items.itemAt(0).widget().styleSheet());panel.query.clear();self.assertTrue(panel.month.isEnabled())
    def test_note_form_calendar_completion_and_private_snapshot(self):
        desk=self.win.desk;desk.sync();self.pump(lambda:not desk.busy);d=NoteDialog(self.win);d.title.setText('قرار شخصی من');d.body.setPlainText('یادداشت خصوصی');d.calendar.setChecked(True);d.day.setText('1405/08/05');d.leads.setText('۵، ۰');d.validate();self.assertEqual(d.result(),QDialog.Accepted);desk.mutation('desk/note',dict(payload=d.payload));self.pump(lambda:not desk.busy);self.assertTrue(any(e['title']=='قرار شخصی من' for e in self.win.display_events()));event=next(e for e in self.win.desk_events if e['title']=='قرار شخصی من');self.win.set_done(event,True);self.pump(lambda:not desk.busy);self.assertTrue(self.server.store.desk_snapshot(self.admin)['notes'][0]['completed']);self.win.tabs.setCurrentWidget(desk);desk.tabs.setCurrentIndex(1);self.app.processEvents();desk.notes.setCurrentCell(0,0);desk.note_calendar();self.assertIs(self.win.tabs.currentWidget(),self.win.calendar_page);self.assertEqual(self.win.selected,parse_j('1405/08/05'));d.deleteLater()
    def test_leave_form_prefills_user_and_managers_receive_notification(self):
        # Finish the startup fetch before submitting a new request, so the
        # explicit sync below cannot be coalesced into an older in-flight read.
        self.pump(lambda:not self.win.desk.busy)
        staff=self.store.user(self.store.login('staff','ک')['user']['id']);d=LeaveDialog(self.win,self.store.companies(self.admin));self.assertEqual(d.name.text(),'مدیر نمونه');self.assertTrue(d.name.isReadOnly());d.kind.setCurrentText('استحقاقی');d.start.setText('1405/08/10');d.end.setText('1405/08/11');d.validate();self.assertEqual(d.result(),QDialog.Accepted);self.store.desk_leave_save(staff,'mana',d.payload)
        with patch.object(self.win,'popup') as popup:
            self.win.desk.sync();self.pump(lambda:not self.win.desk.busy);self.assertEqual(len(self.win.desk.review_rows),1);self.assertTrue(self.win.desk.tabs.isTabVisible(self.win.desk.review_index));self.assertEqual(popup.call_count,1);self.assertTrue(callable(popup.call_args.kwargs['on_shown']))
        d.deleteLater()
    def test_personal_editor_saves_only_this_account(self):
        editor=PersonalEditor(self.win);editor.personal.calendar_name.setText('تقویم شخصی');editor.terms.setText('#بیمه');editor.save();self.assertEqual(self.store.own_profile(self.admin)['preferences']['calendar_name'],'تقویم شخصی');staff=self.store.user(self.store.login('staff','ک')['user']['id']);self.assertFalse(self.store.own_profile(staff)['preferences']);self.assertEqual(self.win.calendar_button.accessibleName(),'تقویم شخصی');editor.deleteLater()
    def test_automatic_desk_state_does_not_request_backup(self):
        from backup_bundle import fingerprint
        a=copy.deepcopy(self.win.data);a.pop('desk_cache',None);b=copy.deepcopy(a);b['desk_cache']=dict(user_id=self.admin['id'],companies=[{'id':'mana','name':'مانا'}],notes=[],leaves=[],incoming=[],notifications=[{'id':'notice','shown':None}]);self.assertEqual(fingerprint(a),fingerprint(b));b['desk_cache']['notes']=[{'title':'اطلاعات شخصی'}];self.assertNotEqual(fingerprint(a),fingerprint(b))

if __name__=='__main__':unittest.main(verbosity=2)
