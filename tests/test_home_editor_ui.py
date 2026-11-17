import copy,unittest
from PySide6.QtCore import Qt,QMimeData,QPoint,QPointF
from PySide6.QtGui import QDragEnterEvent,QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QGridLayout,QMessageBox,QLabel,QFrame
from unittest.mock import patch
import test_v6_ui as fixtures
from home_editor import EditableCard,ResizeHandle,MIME

class HomeEditorUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.V6UiTests.setUpClass();cls.app=fixtures.V6UiTests.app
    setUp=fixtures.V6UiTests.setUp
    tearDown=fixtures.V6UiTests.tearDown
    pump=fixtures.V6UiTests.pump
    def test_drag_resize_remove_cancel_and_save_are_account_scoped(self):
        self.win.tabs.setCurrentWidget(self.win.home);self.win.data['settings'].update(theme_preset='glass_mist',weather_enabled=False);self.win.refresh();self.app.processEvents()
        before=copy.deepcopy(self.win.data.get('preferences',{}));self.win.home.edit_layout();editor=self.win.home.home_editor;self.app.processEvents();self.assertTrue(editor.isVisible())
        source,target=editor.order[0],editor.order[-1];target_card=next(w for w in editor.findChildren(EditableCard) if w.key==target and w.isVisible())
        mime=QMimeData();mime.setData(MIME,source.encode());enter=QDragEnterEvent(QPoint(8,8),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier);QApplication.sendEvent(target_card,enter)
        drop=QDropEvent(QPointF(8,8),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier);QApplication.sendEvent(target_card,drop);QTest.qWait(50);self.assertEqual(editor.order[-2],source)
        target_card=next(w for w in editor.findChildren(EditableCard) if w.key==target and w.isVisible());enter=QDragEnterEvent(QPoint(8,8),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier);QApplication.sendEvent(target_card,enter)
        drop=QDropEvent(QPointF(target_card.width()-2,8),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier);QApplication.sendEvent(target_card,drop);QTest.qWait(50);self.assertEqual(editor.order[-1],source)
        grip=next(w for w in editor.findChildren(ResizeHandle) if w.key==source and w.isVisible());QTest.mousePress(grip,Qt.LeftButton,pos=QPoint(5,5));QTest.mouseRelease(grip,Qt.LeftButton,pos=QPoint(65,65));QTest.qWait(50)
        self.assertEqual(editor.widths[source],2);self.assertEqual(editor.heights[source],2)
        editor.remove_card(source);QTest.qWait(50);self.assertNotIn(source,editor.order);editor.cancel();self.assertEqual(self.win.data.get('preferences',{}),before)
        self.win.home.edit_layout();editor=self.win.home.home_editor;editor.move_card(editor.order[0],editor.order[-1]);editor.resize_card('calendar',1,0);QTest.qWait(50);expected=list(editor.order);editor.save();self.app.processEvents()
        self.assertFalse(editor.isVisible());self.assertEqual(self.win.data['preferences']['home_widgets'],expected)
        profile=self.store.own_profile(self.admin);self.assertEqual(profile['preferences']['home_widgets'],expected);self.assertEqual(profile['preferences']['home_widget_sizes']['calendar'],2)
        other=self.store.user(self.store.login('staff','ک')['user']['id']);self.assertNotIn('home_widgets',self.store.own_profile(other)['preferences'])
    def test_default_home_can_be_customized_without_creating_duplicate_quote(self):
        self.win.data['settings'].update(theme_preset='default',weather_enabled=False);self.win.tabs.setCurrentWidget(self.win.home);self.win.refresh();self.app.processEvents();self.win.home.edit_layout();editor=self.win.home.home_editor
        self.assertIn('today',editor.order);editor.remove_card('attendance');QTest.qWait(40);editor.save();self.app.processEvents()
        prefs=self.win.data['preferences'];self.assertTrue(prefs['home_custom_on_default']);self.assertNotIn('attendance',prefs['home_widgets']);self.assertTrue(self.win.home.theme_dashboard.isVisible())
        board=self.win.home.theme_dashboard;self.assertEqual(len([w for w in board.findChildren(QGridLayout) if w.count()>0]),1)
    def test_window_resize_preserves_unsaved_edits(self):
        self.win.tabs.setCurrentWidget(self.win.home);self.win.home.edit_layout();editor=self.win.home.home_editor;original=list(editor.order);editor.remove_card(original[0]);QTest.qWait(40)
        changed=list(editor.order);editor.resize(700,300);self.app.processEvents();QTest.qWait(40)
        self.assertEqual(editor.order,changed);self.assertTrue(editor.isVisible());self.assertTrue(any(w.isVisible() for w in editor.findChildren(EditableCard)));editor.cancel()
    def test_failed_server_save_restores_local_preferences(self):
        import storage
        self.win.tabs.setCurrentWidget(self.win.home);self.win.home.edit_layout();editor=self.win.home.home_editor;before=copy.deepcopy(self.win.data.get('preferences',{}));editor.remove_card(editor.order[0]);QTest.qWait(40)
        with patch('personalization_ui.request_wait',side_effect=RuntimeError('اتصال آزمایشی ناموفق')),patch.object(QMessageBox,'warning') as warning:editor.save()
        self.assertTrue(editor.isVisible());self.assertEqual(self.win.data.get('preferences',{}),before);self.assertEqual(storage.load_data().get('preferences',{}),before);warning.assert_called_once();editor.cancel()
    def test_settings_layout_applies_to_default_and_keeps_four_column_width(self):
        from PySide6.QtWidgets import QDialog
        from settings_ui import SettingsDialog
        self.win.data['settings']['theme_preset']='default';dialog=SettingsDialog(self.win);dialog.widgets_custom.setChecked(True)
        for row in range(dialog.home_widgets.count()):
            item=dialog.home_widgets.item(row);item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in ('today','calendar') else Qt.Unchecked)
        dialog.home_columns.setValue(4);dialog.home_widget_sizes['calendar'].setCurrentIndex(dialog.home_widget_sizes['calendar'].findData(4));dialog.validate()
        self.assertEqual(dialog.result(),QDialog.Accepted);prefs=self.win.data['preferences'];self.assertTrue(prefs['home_custom_on_default']);self.assertEqual(prefs['home_widget_sizes']['calendar'],4)
        self.win.refresh();self.app.processEvents();self.assertTrue(self.win.home.theme_dashboard.isVisible());dialog.deleteLater()
    def test_changing_account_discards_previous_users_unsaved_layout(self):
        self.win.tabs.setCurrentWidget(self.win.home);self.win.home.edit_layout();editor=self.win.home.home_editor;before=copy.deepcopy(self.win.data.get('preferences',{}));editor.remove_card(editor.order[0]);QTest.qWait(40)
        self.win.session_user=self.store.user(self.store.login('staff','ک')['user']['id'])
        with patch.object(QMessageBox,'warning') as warning:editor.save()
        self.assertFalse(editor.isVisible());self.assertEqual(self.win.data.get('preferences',{}),before);warning.assert_called_once()
    def test_offline_layout_is_queued_and_syncs_after_reconnect(self):
        self.pump(lambda:not self.win.org.busy);self.win.tabs.setCurrentWidget(self.win.home);self.win.home.edit_layout();editor=self.win.home.home_editor;editor.remove_card(editor.order[0]);QTest.qWait(40);expected=list(editor.order)
        client=self.win.org.client;self.win.org.client=None
        try:
            editor.save();self.assertEqual(self.win.data['pending_profile_restore']['preferences']['home_widgets'],expected)
        finally:self.win.org.client=client
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);self.assertNotIn('pending_profile_restore',self.win.data);self.assertEqual(self.store.own_profile(self.admin)['preferences']['home_widgets'],expected)
    def test_calendar_weekdays_fit_inside_compact_emerald_widget(self):
        self.win.resize(900,620);self.win.data['settings'].update(theme_preset='emerald_ivory',theme='dark',weather_enabled=False);self.win.refresh();self.win.tabs.setCurrentWidget(self.win.home);self.win.home.edit_layout();self.app.processEvents()
        editor=self.win.home.home_editor;card=next(w for w in editor.findChildren(EditableCard) if w.isVisible() and w.key=='calendar');weekdays=card.findChildren(QLabel,'CalendarWeekday')
        self.assertEqual(len(weekdays),7);self.assertTrue(all(len(w.text())==1 for w in weekdays));rects=[w.rect().translated(w.mapTo(card,w.rect().topLeft())) for w in weekdays]
        self.assertTrue(all(not rects[i].intersects(rects[j]) for i in range(7) for j in range(i+1,7)));editor.cancel()
    def test_editor_is_opened_from_settings_without_home_button(self):
        from settings_ui import SettingsDialog
        from PySide6.QtWidgets import QPushButton
        self.win.tabs.setCurrentWidget(self.win.calendar_page);dialog=SettingsDialog(self.win);dialog.show();self.app.processEvents();dialog.edit_home_layout.click();QTest.qWait(100)
        self.assertIs(self.win.tabs.currentWidget(),self.win.home);self.assertTrue(self.win.home.home_editor.isVisible());self.assertFalse(any(b.text()=='شخصی‌سازی صفحه اصلی' for b in self.win.home.findChildren(QPushButton)));self.win.home.home_editor.cancel();dialog.deleteLater()
    def test_custom_dashboard_cards_fit_on_laptop_in_every_theme(self):
        from appearance import apply_appearance
        from home_layout import initial_widgets
        self.win.resize(1024,700);self.win.tabs.setCurrentWidget(self.win.home)
        for theme in ('default','emerald_ivory','glass_mist','violet_modular','bento_grid'):
            self.win.data['settings'].update(theme_preset=theme,weather_enabled=False);self.win.data.setdefault('preferences',{}).update(home_widgets=initial_widgets(theme,False,True),home_custom_on_default=True,home_customize_v2=True,home_widget_sizes={},home_widget_row_sizes={})
            apply_appearance(self.win.data['settings']);self.win.refresh();self.win.sidebar.apply();self.app.processEvents();board=self.win.home.theme_dashboard
            rects=[w.rect().translated(w.mapTo(board,w.rect().topLeft())) for w in board.findChildren(QFrame,'DashboardCard') if w.isVisible()]
            self.assertTrue(rects,theme);self.assertTrue(all(board.rect().contains(r) for r in rects),theme)
            self.assertTrue(all(not rects[i].intersects(rects[j]) for i in range(len(rects)) for j in range(i+1,len(rects))),theme)

